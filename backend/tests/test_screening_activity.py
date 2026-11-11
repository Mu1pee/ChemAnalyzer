"""Admission and disclosure tests; fabricated metadata are software fixtures only."""
import pytest
from fastapi.testclient import TestClient

from app.chemistry import screening_activity as screening
from app.main import app


def metadata(key="hiv", **changes):
    return dict(dict(id="fixture", status="experimental", trained_at="2026-11-11T00:00:00Z",
                     task=screening.TASKS[key](), quality=dict(passed=True),
                     evaluation=dict(test=dict(balanced_accuracy=.65, roc_auc=.76, pr_auc=.32, recall=.32, precision=.49),
                                     support=dict(train=dict(molecules=100), test=dict(molecules=40, positive=10, negative=30)))), **changes)


def registry(monkeypatch, models, in_domain=True):
    class FakeRegistry:
        def list(self):
            return models
        def predict(self, identifier, smiles):
            return dict(probability=.7, applicability=dict(in_domain=in_domain, max_similarity=.8 if in_domain else .1))
    monkeypatch.setattr(screening, "Registry", lambda root: FakeRegistry())


def test_separate_endpoints_disclose_low_recall_and_class_counts(monkeypatch):
    registry(monkeypatch, [metadata()])
    response = TestClient(app).post("/api/molecules/screening", json=dict(smiles="CCO"))
    assert response.status_code == 200
    hiv, hepg2 = response.json()["predictions"]
    assert hiv["key"] == "hiv" and hiv["probability"] == .7 and hiv["metrics"]["recall"] == .32
    assert hiv["test_positive"] == 10 and hiv["test_negative"] == 30
    assert hepg2["key"] == "hepg2" and hepg2["status"] == "not_trained" and hepg2["probability"] is None


def test_wrong_assay_context_and_failed_quality_have_no_predictions(monkeypatch):
    wrong = metadata("hepg2")
    wrong["task"]["context"] = "HepG2: 72 hours or paracetamol rescue"
    registry(monkeypatch, [wrong, metadata(quality=dict(passed=False))])
    hiv, hepg2 = screening.predict_screening("CCO")["predictions"]
    assert hiv["status"] == "quality_failed" and hepg2["status"] == "not_trained"
    assert hiv["probability"] is None and hepg2["probability"] is None


def test_outside_domain_probability_is_hidden_even_if_predictor_returns_one(monkeypatch):
    registry(monkeypatch, [metadata()], in_domain=False)
    hiv = screening.predict_screening("CCO")["predictions"][0]
    assert hiv["status"] == "out_of_domain" and hiv["probability"] is None
    assert hiv["metrics"]["balanced_accuracy"] == .65


def test_latest_selected_without_test_score_cherry_picking(monkeypatch):
    old = metadata(id="old")
    old["evaluation"]["test"]["balanced_accuracy"] = .99
    registry(monkeypatch, [old, metadata(id="recent", trained_at="2026-11-11T01:00:00Z")])
    assert screening.predict_screening("CCO")["predictions"][0]["model_id"] == "recent"


def test_invalid_and_mixture_smiles_rejected():
    for smiles in ("invalid", "CCO.Cl"):
        assert TestClient(app).post("/api/molecules/screening", json=dict(smiles=smiles)).status_code == 400


@pytest.mark.parametrize("key", ["hiv", "hepg2"])
def test_source_routes_and_task_presets_do_not_fall_through_generic_action(monkeypatch, tmp_path, key):
    from app.ai_research_agent import api
    from app.ai_research_agent.config import TaskConfig
    from app.ai_research_agent.orchestrator import ResearchAgent
    agent = ResearchAgent(tmp_path)
    identifier = agent.create(TaskConfig(**screening.TASKS[key]()))["id"]
    monkeypatch.setattr(api, "agent", lambda: agent)
    monkeypatch.setattr(agent, "import_tdc_" + key, lambda identifier: {"source": key, "task_id": identifier})
    monkeypatch.setenv("CHEMANALYZER_RESEARCH_ENABLED", "1")
    client = TestClient(app)
    assert client.get("/api/research/status").json()["screening_tasks"][key]["endpoint"] == screening.TASKS[key]()["endpoint"]
    result = client.post(f"/api/research/tasks/{identifier}/tdc-{key}", json={})
    assert result.status_code == 200 and result.json()["source"] == key
