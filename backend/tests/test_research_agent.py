"""Synthetic labels below exercise software only; they are not scientific data."""
import csv
import io
import time

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.ai_research_agent.config import FREESOLV_TASK, TaskConfig, Provenance
from app.ai_research_agent.data_validation import read_measurements, validate_source
from app.ai_research_agent.data_discovery import discover, fetch_freesolv
from app.ai_research_agent.evaluation import scaffold_split
from app.ai_research_agent.molecular_features import prepare, vector, molecule
from app.ai_research_agent.training import train
from app.ai_research_agent.applicability_domain import fit_domain, assess
from app.ai_research_agent.model_registry import Registry, Approval, Review
from app.ai_research_agent.orchestrator import ResearchAgent
from app.ai_research_agent.security import safe_child, write_json


@pytest.fixture
def task():
    return TaskConfig(**FREESOLV_TASK)


@pytest.fixture
def provenance(task):
    return Provenance(source_url="https://example.org/test.csv", doi="test-fixture-not-science",
                      license="CC0-1.0", license_url="https://example.org/license",
                      source_version="test", retrieved_at="2026-11-04T00:00:00Z", curator="Test fixture",
                      experimental=True, endpoint=task.endpoint, units=task.units, context=task.context)


def test_discovery_does_not_claim_leads_are_verified():
    data = discover("unknown")
    assert {s["id"] for s in data["sources"]} == {"freesolv", "tdc_cyp", "tdc_hiv", "tdc_hepg2", "pubchem", "chembl", "zenodo"}
    assert "not verified" in data["message"]


@pytest.mark.parametrize("failure", [httpx.ConnectError("offline"), httpx.ReadTimeout("timeout")])
def test_discovery_network_failures_are_real_errors(monkeypatch, failure):
    import app.ai_research_agent.data_discovery as discovery
    def fail(*args):
        raise failure
    monkeypatch.setattr(discovery, "_fetch", fail)
    with pytest.raises(type(failure)):
        fetch_freesolv()


def test_freesolv_only_uses_experimental_column(monkeypatch):
    import app.ai_research_agent.data_discovery as discovery
    def fake(url):
        if "commits" in url:
            return b'{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}'
        if url.endswith("LICENSE"):
            return b"Creative Commons Attribution 4.0"
        return b"# header\nid; CCO; ethanol; -5.0; .6; 999.0; .1; 10.test/ref; calc; default uncertainty\n"
    monkeypatch.setattr(discovery, "_fetch", fake)
    text, meta, raw, license_data, evidence = fetch_freesolv()
    row = next(csv.DictReader(io.StringIO(text)))
    assert row["value"] == "-5.0" and "999.0" not in text
    assert meta["experimental"] and evidence["raw_sha256"]


@pytest.mark.parametrize("field,value", [("units", "mg/L"), ("endpoint", "other"), ("context", "incompatible protocol"), ("experimental", False)])
def test_incompatible_source_rejected(task, provenance, field, value):
    with pytest.raises(ValueError):
        validate_source(task, provenance.model_copy(update={field: value}))


def test_unknown_license_rejected(provenance):
    with pytest.raises(ValueError):
        Provenance(**dict(provenance.model_dump(), license="unknown"))


def test_invalid_labels_structures_and_duplicates():
    rows, issues = read_measurements("smiles,value\nCCO,1\nOCC,1\nbroken,2\nCCC,\nCCN,nan\nC.C,3\nCO,4\nCO,5\n", 60)
    X, y, groups, report = prepare(rows, issues)
    categories = {issue["category"] for issue in report["issues"]}
    assert {"structure_error", "missing_label", "measurement_error", "duplicate", "conflicting_duplicate"} <= categories
    assert X.shape == (1, 1030) and y.tolist() == [1]
    assert len(report["transformations"]) == 4


def test_input_limits():
    with pytest.raises(ValueError, match="row limit"):
        read_measurements("smiles,value\n" + "CCO,1\n" * 61, 60)


def test_scaffold_partition_has_no_leakage_and_is_reproducible():
    groups = np.array(["acyclic"] * 100 + [str(i // 4) for i in range(100)])
    y = np.arange(200)
    parts = scaffold_split(y, groups, 42)
    again = scaffold_split(y[::-1], groups, 42)
    assert all(np.array_equal(a, b) for a, b in zip(parts, again))  # labels cannot affect assignment
    sets = [set(groups[p]) for p in parts]
    assert not (sets[0] & sets[1] or sets[0] & sets[2] or sets[1] & sets[2])
    assert sorted(np.concatenate(parts)) == list(range(200))
    assert min(map(len, parts)) >= 10


def test_insufficient_data(task):
    with pytest.raises(ValueError, match="Insufficient data"):
        train(np.ones((20, 1030)), np.arange(20), np.arange(20), task)


def test_imbalanced_classes(task):
    task = task.model_copy(update={"kind": "classification"})
    with pytest.raises(ValueError, match="30 compounds"):
        train(np.ones((100, 1030)), np.array([0] * 95 + [1] * 5), np.arange(100), task)


@pytest.fixture(scope="module")
def trained_fixture():
    # Numerical synthetic features test the trainer, not any chemical endpoint.
    rng = np.random.default_rng(8)
    X = rng.integers(0, 2, (120, 1030)).astype(np.float32)
    y = X[:, -1] * 5 + rng.normal(0, .01, 120)
    task = TaskConfig(**FREESOLV_TASK)
    model, train_X, report = train(X, y, np.repeat(np.arange(30), 4), task)
    return model, train_X, report, task


def test_training_selection_and_holdout(trained_fixture):
    model, X, report, task = trained_fixture
    assert len(report["candidates"]) == 3
    assert report["beats_baseline"]
    assert report["test_used_for_selection"] is False
    assert set(report["test"]) == {"mae", "rmse", "r2"}


def test_registry_integrity_and_explicit_approval(tmp_path, trained_fixture):
    model, X, report, task = trained_fixture
    registry = Registry(tmp_path)
    meta = registry.register(dict(model=model, domain=fit_domain(X)), dict(task=task.model_dump(), evaluation=report))
    identifier = meta["id"]
    assert registry.load(identifier)["model"] is not None
    assert registry.metadata(identifier)["status"] == "experimental"
    approval = Approval(reviewer="Technical test", evidence="Synthetic technical fixture only; no scientific validity.", confirm_activation=True)
    with pytest.raises(ValueError, match="review"):
        registry.approve(identifier, approval)
    registry.review(identifier, Review(**approval.model_dump(exclude={"confirm_activation"})))
    with pytest.raises(ValueError, match="confirmation"):
        registry.approve(identifier, approval.model_copy(update={"confirm_activation": False}))
    assert registry.approve(identifier, approval)["status"] == "approved"
    # This synthetic numeric fixture has descriptor ranges 0..1; real ethanol
    # is deliberately outside them. Do not expose an uninterpretable value.
    prediction = registry.predict(identifier, "CCO")
    assert not prediction["applicability"]["in_domain"]
    assert prediction["value"] is None and prediction["quality"]["passed"]
    path = tmp_path / "models" / identifier / "model.joblib"
    path.write_bytes(path.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        registry.load(identifier)


def test_applicability_is_not_probability():
    x = vector(molecule("CCO"))
    domain = fit_domain(x.reshape(1, -1))
    assert assess(domain, x)["in_domain"]
    far = vector(molecule("c1ccccc1CCCCCCCCCCCCCCCC"))
    assert not assess(domain, far)["in_domain"]
    assert "not an activity probability" in assess(domain, far)["warning"]


def test_antidote_training_prohibited(task):
    task = task.model_copy(update={"domain": "antidote_catalog"})
    with pytest.raises(ValueError, match="not authorized"):
        train(np.ones((100, 1030)), np.arange(100), np.arange(100), task)


def test_import_and_cancel_spawned_worker(tmp_path, task, provenance):
    agent = ResearchAgent(tmp_path)
    identifier = agent.create(task)["id"]
    agent.import_csv(identifier, "smiles,value\nCCO,1\n", provenance)
    run = agent.start(identifier)
    state = agent.cancel(run["id"])
    agent.monitors[run["id"]].join(10)
    assert state["status"] == "cancelled"
    assert not agent.jobs[run["id"]].is_alive()
    assert Registry(tmp_path).list() == []


def test_worker_reports_insufficient_data_without_publishing(tmp_path, task, provenance):
    agent = ResearchAgent(tmp_path)
    identifier = agent.create(task)["id"]
    agent.import_csv(identifier, "smiles,value\nCCO,1\n", provenance)
    run = agent.start(identifier)
    agent.monitors[run["id"]].join(40)
    state = agent.run(run["id"])
    assert state["status"] == "failed" and "Insufficient data" in state["error"]
    assert state["preparation"]["accepted"] == 1
    assert Registry(tmp_path).list() == []


def test_restart_marks_interrupted_and_preserves_evidence(tmp_path):
    write_json(tmp_path / "runs" / "abc" / "state.json", dict(status="running", stage="training"))
    agent = ResearchAgent(tmp_path)
    assert agent.run("abc")["status"] == "interrupted"


def test_path_traversal_rejected(tmp_path):
    with pytest.raises(ValueError):
        safe_child(tmp_path, "../escape")


def test_api_opt_in_and_ui_contract(monkeypatch, tmp_path, task):
    from app.main import app
    from app.ai_research_agent import api
    monkeypatch.setattr(api, "agent", lambda: ResearchAgent(tmp_path))
    client = TestClient(app)
    monkeypatch.delenv("CHEMANALYZER_RESEARCH_ENABLED", raising=False)
    assert client.get("/api/research/status").json()["enabled"] is False
    assert client.post("/api/research/tasks", json=task.model_dump()).status_code == 403
    monkeypatch.setenv("CHEMANALYZER_RESEARCH_ENABLED", "1")
    response = client.post("/api/research/tasks", json=task.model_dump())
    assert response.status_code == 200
    assert client.get("/api/research/tasks").json()[0]["id"] == response.json()["id"]
    assert client.get("/health").json()["application"] == "ChemAnalyzer"
    assert client.post("/api/research/tasks", json=task.model_dump(), headers={"Origin": "https://foreign.example"}).status_code == 403


def test_classification_training(task):
    rng = np.random.default_rng(22)
    X = rng.integers(0, 2, (160, 1030)).astype(np.float32)
    y = X[:, -1].astype(int)
    task = task.model_copy(update={"kind": "classification"})
    model, _, report = train(X, y, np.repeat(np.arange(40), 4), task)
    assert set(report["test"]) == {"roc_auc", "pr_auc", "f1", "precision", "recall", "balanced_accuracy"}
    assert report["test"]["roc_auc"] > .8


def test_ram_limit_stops_worker(tmp_path, monkeypatch, task, provenance):
    from types import SimpleNamespace
    import psutil
    agent = ResearchAgent(tmp_path)
    identifier = agent.create(task)["id"]
    agent.import_csv(identifier, "smiles,value\nCCO,1\n", provenance)
    monkeypatch.setattr(psutil, "Process", lambda pid: SimpleNamespace(memory_info=lambda: SimpleNamespace(rss=10000 * 1024**2)))
    run = agent.start(identifier)
    agent.monitors[run["id"]].join(10)
    assert agent.run(run["id"])["stage"] == "resource_limit"
    assert not agent.jobs[run["id"]].is_alive()
    assert Registry(tmp_path).list() == []


def test_schedule_requires_exact_approved_data(tmp_path, task, provenance, monkeypatch):
    from app.ai_research_agent.scheduler import Schedule, Scheduler
    from app.ai_research_agent.security import read_json
    agent = ResearchAgent(tmp_path)
    identifier = agent.create(task)["id"]
    manifest = agent.import_csv(identifier, "smiles,value\nCCO,1\n", provenance)
    scheduler = Scheduler(agent)
    with pytest.raises(ValueError, match="checksum"):
        scheduler.save(Schedule(task_id=identifier, approved_dataset_sha256="0" * 64))
    scheduler.save(Schedule(task_id=identifier, enabled=True, approved_dataset_sha256=manifest["dataset_sha256"]))
    agent.import_csv(identifier, "smiles,value\nCCO,2\n", provenance)
    monkeypatch.setattr(agent, "start", lambda *args: pytest.fail("Changed data must not train"))
    scheduler.tick(now=1)
    state = read_json(tmp_path / "schedules" / identifier / "state.json")
    assert "require new explicit approval" in state["training"]


def test_scheduler_reports_offline_without_training(tmp_path, task, monkeypatch):
    from app.ai_research_agent.scheduler import Schedule, Scheduler
    from app.ai_research_agent.security import read_json
    import app.ai_research_agent.scheduler as module
    agent = ResearchAgent(tmp_path)
    identifier = agent.create(task)["id"]
    scheduler = Scheduler(agent)
    scheduler.save(Schedule(task_id=identifier, enabled=True, check_freesolv=True))
    def fail():
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(module, "fetch_freesolv", fail)
    scheduler.tick(now=1)
    state = read_json(tmp_path / "schedules" / identifier / "state.json")
    assert "offline" in state["error"]


def test_scheduler_new_approval_does_not_reuse_old_run(tmp_path, task, provenance, monkeypatch):
    from app.ai_research_agent.scheduler import Schedule, Scheduler
    agent = ResearchAgent(tmp_path)
    identifier = agent.create(task)["id"]
    manifest = agent.import_csv(identifier, "smiles,value\nCCO,2\n", provenance)
    scheduler = Scheduler(agent)
    scheduler.save(Schedule(task_id=identifier, enabled=True, approved_dataset_sha256=manifest["dataset_sha256"]))
    write_json(tmp_path / "schedules" / identifier / "state.json",
               dict(approved_dataset_sha256="0" * 64, run_id="old_completed", trained_sha256="0" * 64))
    started = []
    monkeypatch.setattr(agent, "start", lambda task_id: (started.append(task_id) or {"id": "new"}))
    monkeypatch.setattr(agent, "run", lambda run_id: pytest.fail("Old dataset run must not be reused"))
    scheduler.tick(now=1)
    assert started == [identifier]


def test_tampered_dataset_cannot_train_under_old_approval(tmp_path, task, provenance):
    agent = ResearchAgent(tmp_path)
    identifier = agent.create(task)["id"]
    manifest = agent.import_csv(identifier, "smiles,value\nCCO,1\n", provenance)
    path = tmp_path / "tasks" / identifier / manifest["version_id"] / "dataset.csv"
    path.write_text("smiles,value\nCCO,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        agent.start(identifier)
    assert agent.jobs == {}
