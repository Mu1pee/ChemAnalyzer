"""Regression checks for endpoint routing, evidence integrity and scheduling."""
from types import SimpleNamespace
import json

import pytest

from app.ai_research_agent.model_registry import Approval, Registry
from app.ai_research_agent.scheduler import Schedule, Scheduler
from app.ai_research_agent.security import checksum, read_json, write_json
from app.model_quality import held_out_quality


def evidence():
    return dict(test=dict(balanced_accuracy=.75, roc_auc=.8), beats_baseline=True,
                test_used_for_selection=False,
                support=dict(test=dict(molecules=40, scaffolds=5, negative=20, positive=20)))


def model_metadata(identifier, endpoint, context, status="validated"):
    return dict(id=identifier, status=status, task=dict(endpoint=endpoint, context=context, kind="classification"),
                evaluation=evidence())


def test_active_models_keep_distinct_endpoint_context_pairs(tmp_path, monkeypatch):
    registry = Registry(tmp_path)
    # These endpoint/context pairs previously hashed the same concatenation.
    for identifier, endpoint, context in (("first", "abc", "def"), ("second", "abcd", "ef")):
        write_json(tmp_path / "models" / identifier / "metadata.json", model_metadata(identifier, endpoint, context))
    monkeypatch.setattr(registry, "load", lambda identifier: {})
    monkeypatch.setattr(registry, "predict", lambda identifier, smiles: dict(model_id=identifier))
    approval = Approval(reviewer="Software fixture", evidence="Routing regression fixture only, not scientific evidence.",
                        confirm_activation=True)
    registry.approve("first", approval)
    registry.approve("second", approval)
    assert registry.predict_active("abc", "def", "CCO")["model_id"] == "first"
    assert registry.predict_active("abcd", "ef", "CCO")["model_id"] == "second"


def test_legacy_active_pointer_requires_matching_endpoint_context(tmp_path, monkeypatch):
    registry = Registry(tmp_path)
    write_json(tmp_path / "models" / "legacy" / "metadata.json", model_metadata("legacy", "abc", "def", "approved"))
    write_json(tmp_path / "models" / ("active_" + checksum(b"abcdef") + ".json"), dict(model_id="legacy"))
    monkeypatch.setattr(registry, "predict", lambda identifier, smiles: dict(model_id=identifier))
    assert registry.predict_active("abc", "def", "CCO")["model_id"] == "legacy"
    with pytest.raises(ValueError, match="no approved active model"):
        registry.predict_active("abcd", "ef", "CCO")


@pytest.mark.parametrize("field", ["molecules", "scaffolds", "positive", "negative"])
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "40", None, True, 40.5])
def test_invalid_support_counts_fail_quality_closed(field, bad):
    report = evidence()
    report["support"]["test"][field] = bad
    assert not held_out_quality("classification", report)["passed"]


def test_inconsistent_support_counts_fail_quality():
    report = evidence()
    report["support"]["test"]["molecules"] = 41
    assert not held_out_quality("classification", report)["passed"]
    report = evidence()
    report["support"]["test"]["scaffolds"] = 41
    assert not held_out_quality("classification", report)["passed"]


@pytest.mark.parametrize("kind,field", [(kind, field) for kind in ("classification", "regression")
                                      for field in (None, "test", "support", "baseline_test")
                                      if kind == "regression" or field != "baseline_test"])
@pytest.mark.parametrize("bad", ["invalid", [1], 42])
def test_malformed_evaluation_is_rejected_without_crashing(kind, field, bad):
    report = evidence()
    if field is None:
        report = bad
    else:
        report[field] = bad
    if kind == "regression" and field == "baseline_test":
        report["test"] = dict(r2=.7, mae=1)
    result = held_out_quality(kind, report)
    assert not result["passed"]
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("damaged", ["{invalid", "[]", '{"task": []}', '{"id":"bad","score":NaN}'])
def test_corrupt_record_is_visible_but_other_endpoint_keeps_working(tmp_path, monkeypatch, damaged):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.ai_research_agent import api
    from app.chemistry import screening_activity as screening
    registry = Registry(tmp_path)
    meta = model_metadata("good", "unused", "unused", "experimental")
    meta["task"] = screening.TASKS["hlm"]()
    meta["evaluation"]["support"]["train"] = dict(molecules=100)
    write_json(tmp_path / "models" / "good" / "metadata.json", meta)
    path = tmp_path / "models" / "bad" / "metadata.json"
    path.parent.mkdir(parents=True)
    path.write_text(damaged, encoding="utf-8")
    monkeypatch.setenv("CHEMANALYZER_RESEARCH_ENABLED", "1")
    monkeypatch.setattr(api, "agent", lambda: SimpleNamespace(root=tmp_path))
    monkeypatch.setattr(screening, "storage_root", lambda: tmp_path)
    def predict(self, identifier, smiles):
        assert identifier == "good"
        return dict(probability=.7, applicability=dict(in_domain=True, max_similarity=.8))
    monkeypatch.setattr(Registry, "predict", predict)
    client = TestClient(app)
    response = client.get("/api/research/models")
    assert response.status_code == 200
    entries = {entry["id"]: entry for entry in response.json()}
    assert entries["bad"]["status"] == "invalid" and not entries["bad"]["quality"]["passed"]
    assert entries["good"]["quality"]["passed"]
    result = client.post("/api/molecules/screening", json=dict(smiles="CCO"))
    assert result.status_code == 200
    hlm = result.json()["predictions"][2]
    assert hlm["status"] == "ready" and hlm["model_id"] == "good"
    assert path.read_text(encoding="utf-8") == damaged
    with pytest.raises(ValueError):
        registry.metadata("bad")


@pytest.mark.parametrize("damaged_file", ["policy.json", "state.json"])
def test_corrupt_schedule_does_not_stop_other_schedules(tmp_path, damaged_file, caplog):
    scheduler = Scheduler(SimpleNamespace(root=tmp_path))
    broken, healthy = "0" * 32, "1" * 32
    for identifier in (broken, healthy):
        write_json(tmp_path / "schedules" / identifier / "policy.json",
                   Schedule(task_id=identifier, enabled=True).model_dump())
    damaged = tmp_path / "schedules" / broken / damaged_file
    damaged.write_text("{invalid", encoding="utf-8")
    scheduler.tick(now=1)
    assert read_json(tmp_path / "schedules" / healthy / "state.json")["next_check"] == 86401
    assert damaged.read_text(encoding="utf-8") == "{invalid"
    assert "Unable to process research schedule" in caplog.text


def test_unwritable_schedule_does_not_stop_other_schedules(tmp_path, monkeypatch, caplog):
    import app.ai_research_agent.scheduler as module
    scheduler = Scheduler(SimpleNamespace(root=tmp_path))
    broken, healthy = "0" * 32, "1" * 32
    for identifier in (broken, healthy):
        write_json(tmp_path / "schedules" / identifier / "policy.json",
                   Schedule(task_id=identifier, enabled=True).model_dump())
    def selective_write(path, value):
        if path.parent.name == broken:
            raise PermissionError("File locked")
        write_json(path, value)
    monkeypatch.setattr(module, "write_json", selective_write)
    scheduler.tick(now=1)
    assert read_json(tmp_path / "schedules" / healthy / "state.json")["next_check"] == 86401
    assert "File locked" in caplog.text
