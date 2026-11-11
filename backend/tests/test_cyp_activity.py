"""CYP route admission tests; synthetic metadata are software fixtures only."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.chemistry import cyp_activity as cyp
from app.ai_research_agent.tdc_cyp import task_config
from app.main import app


def metadata(isoform="CYP1A2", **changes):
    meta = dict(id="fixture", status="experimental", trained_at="2026-11-11T00:00:00Z",
                task=task_config(isoform), quality=dict(passed=True),
                evaluation=dict(test=dict(balanced_accuracy=.75, roc_auc=.82, pr_auc=.8),
                                support=dict(train=dict(molecules=100), test=dict(molecules=40))))
    return dict(meta, **changes)


def registry(monkeypatch, models, in_domain=True):
    class FakeRegistry:
        def list(self):
            return models
        def predict(self, identifier, smiles):
            return dict(probability=.7 if in_domain else None,
                        applicability=dict(in_domain=in_domain, max_similarity=.8 if in_domain else .1))
    monkeypatch.setattr(cyp, "Registry", lambda root: FakeRegistry())


def test_cyp_models_are_separate_and_missing_isoforms_have_no_values(monkeypatch):
    registry(monkeypatch, [metadata()])
    response = TestClient(app).post("/api/molecules/cyp", json={"smiles": "CCO"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["predictions"]) == 5
    first = data["predictions"][0]
    assert first["isoform"] == "CYP1A2" and first["status"] == "ready" and first["probability"] == .7
    assert first["model_status"] == "experimental" and first["n_test"] == 40
    for prediction in data["predictions"][1:]:
        assert prediction["status"] == "not_trained" and prediction["probability"] is None


def test_failed_quality_and_wrong_context_cannot_supply_cyp_prediction(monkeypatch):
    wrong = metadata("CYP2C9")
    wrong["task"]["context"] = "Mixed clinical drug-interaction labels"
    registry(monkeypatch, [metadata(quality=dict(passed=False)), wrong])
    result = cyp.predict_cyp("CCO")
    assert result["predictions"][0]["status"] == "quality_failed"
    assert result["predictions"][1]["status"] == "not_trained"
    assert all(p["probability"] is None for p in result["predictions"])


def test_outside_domain_hides_probability_but_retains_test_evidence(monkeypatch):
    registry(monkeypatch, [metadata()], in_domain=False)
    prediction = cyp.predict_cyp("CCO")["predictions"][0]
    assert prediction["status"] == "out_of_domain" and prediction["probability"] is None
    assert prediction["metrics"]["balanced_accuracy"] == .75


def test_selection_does_not_cherry_pick_highest_test_score(monkeypatch):
    old, recent = metadata(id="old"), metadata(id="recent", trained_at="2026-11-11T01:00:00Z")
    old["evaluation"]["test"]["balanced_accuracy"] = .99
    registry(monkeypatch, [old, recent])
    assert cyp.predict_cyp("CCO")["predictions"][0]["model_id"] == "recent"


def test_invalid_or_mixture_structure_is_rejected():
    client = TestClient(app)
    for smiles in ("invalid", "CCO.Cl"):
        assert client.post("/api/molecules/cyp", json=dict(smiles=smiles)).status_code == 400
