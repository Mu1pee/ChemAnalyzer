"""Catalog/inference contract fixtures only; no biological training evidence."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.ai_research_agent.config import FREESOLV_TASK, TaskConfig
from app.ai_research_agent.model_registry import Registry, select_task_model
from app.chemistry import capabilities as catalog, cyp_activity as cyp, screening_activity as screening, qsar, specialized_activity
from app.main import app


def model(task=None, **changes):
    return dict(dict(id="fixture", status="experimental", trained_at="2026-11-13T00:00:00Z",
        task=task or cyp.task_config("CYP1A2"), quality=dict(passed=True),
        evaluation=dict(test=dict(balanced_accuracy=.75, roc_auc=.8, pr_auc=.7),
                        support=dict(train=dict(molecules=100), test=dict(molecules=40, positive=20, negative=20)))), **changes)


@pytest.fixture
def install(monkeypatch):
    monkeypatch.setenv("CHEMANALYZER_RESEARCH_ENABLED", "1")
    monkeypatch.setattr(qsar, "_load_models", lambda: ([], None, [dict(target_id="CHEMBL230")]))
    monkeypatch.setattr(specialized_activity, "_load_bundles", lambda: ({"antidote": [], "growth_regulating": []}, None))
    def configure(models, broken=()):
        class SoftwareRegistry:
            def __init__(self): self.checked = []
            def list(self): return deepcopy(models)
            def verify_artifact(self, identifier):
                self.checked.append(identifier)
                if identifier in broken: raise ValueError("fixture checksum mismatch")
                return deepcopy(next(m for m in models if m["id"] == identifier))
            def predict(self, identifier, smiles):
                self.verify_artifact(identifier)
                return dict(probability=.7, applicability=dict(in_domain=True, max_similarity=.8))
        registry = SoftwareRegistry()
        for module in (catalog, cyp, screening): monkeypatch.setattr(module, "Registry", lambda root: registry)
        return registry
    return configure


def modules():
    response = TestClient(app).get("/api/molecules/capabilities")
    assert response.status_code == 200
    return {module["id"]: module for module in response.json()["modules"]}


@pytest.mark.parametrize("field,value", [("context", "different assay conditions"), ("domain", "growth"),
    ("units", "nM"), ("kind", "regression")])
@pytest.mark.parametrize("module,key", [("cyp", "CYP1A2"), ("hiv", "hiv")])
def test_passing_wrong_scientific_contract_is_unavailable_in_catalog_and_inference(install, field, value, module, key):
    task = cyp.task_config(key) if module == "cyp" else screening.TASKS[key]()
    task[field] = value
    registry = install([model(task)])
    state = modules()[module]
    assert not state["available"] and state["status"] == "incompatible"
    predictions = cyp.predict_cyp("CCO") if module == "cyp" else screening.predict_screening("CCO")
    assert predictions["predictions"][0]["status"] == "not_trained"
    assert predictions["predictions"][0]["probability"] is None and registry.checked == []


@pytest.mark.parametrize("status,quality,expected", [("archived", True, "archived"), ("experimental", False, "quality_failed")])
def test_archived_or_failed_models_cannot_make_a_module_available(install, status, quality, expected):
    registry = install([model(status=status, quality=dict(passed=quality))])
    capability = modules()["cyp"]
    assert capability["status"] == expected and not capability["available"] and registry.checked == []
    assert cyp.predict_cyp("CCO")["predictions"][0]["probability"] is None


def test_partial_cyp_counts_only_exact_admitted_isoforms_and_freesolv_contract(install):
    hydration = TaskConfig(**FREESOLV_TASK).model_dump()
    install([model(), model(hydration, id="freesolv"), model(screening.TASKS["hepg2"](), id="hepg2")])
    result = modules()
    assert result["cyp"]["available"] and result["cyp"]["status"] == "partial"
    assert result["cyp"]["models_available"] == 1 and result["cyp"]["models_expected"] == 5
    assert result["hydration"]["available"] and result["hydration"]["states"][0]["domain"] == "qsar"
    assert result["hydration"]["states"][0]["kind"] == "regression"
    assert result["hepg2"]["available"] and not result["hiv"]["available"]
    assert result["targets"]["status"] == "quality_failed"
    assert result["antidote"]["status"] == result["growth"]["status"] == "not_trained"


def test_solubility_context_and_integrity_gate_are_shared_with_prediction(install, monkeypatch):
    task = screening.TASKS["solubility"]()
    install([model(task, id="kinetic-solubility")])
    monkeypatch.delenv("CHEMANALYZER_RESEARCH_ENABLED", raising=False)
    assert modules()["solubility"]["states"][0]["model_id"] == "kinetic-solubility"
    prediction = screening.predict_screening("CCO")["predictions"][-1]
    assert prediction["key"] == "solubility" and prediction["probability"] == .7
    assert "≤10" in prediction["title"] and "низкая растворимость" in prediction["context"]
    task["context"] = "Thermodynamic solubility, another pH or threshold"
    install([model(task, id="wrong-solubility")])
    assert not modules()["solubility"]["available"]
    assert screening.predict_screening("CCO")["predictions"][-1]["probability"] is None


def test_selection_matches_inference_and_never_uses_highest_test_score(install):
    old = model(id="old", trained_at="2026-11-12")
    old["evaluation"]["test"]["balanced_accuracy"] = .99
    recent = model(id="recent", trained_at="2026-11-13")
    install([old, recent])
    assert modules()["cyp"]["states"][0]["model_id"] == cyp.predict_cyp("CCO")["predictions"][0]["model_id"] == "recent"
    approved = model(id="approved", status="approved", trained_at="2026-11-01")
    install([old, recent, approved])
    assert modules()["cyp"]["states"][0]["model_id"] == "approved"
    approved["quality"]["passed"] = False
    install([old, recent, approved])
    assert modules()["cyp"]["states"][0]["model_id"] == "recent"


def test_selected_bad_artifact_is_an_error_without_falling_back_to_a_different_model(install):
    install([model(id="old", trained_at="2026-11-12"), model(id="broken", trained_at="2026-11-13")], broken={"broken"})
    assert modules()["cyp"]["status"] == "error"
    assert not modules()["cyp"]["available"]
    assert cyp.predict_cyp("CCO")["predictions"][0]["status"] == "error"


def test_disabled_training_lab_does_not_hide_available_local_inference(install, monkeypatch):
    monkeypatch.delenv("CHEMANALYZER_RESEARCH_ENABLED", raising=False)
    install([model()])
    assert modules()["cyp"]["available"]
    assert cyp.predict_cyp("CCO")["predictions"][0]["status"] == "ready"


def test_hydration_prediction_needs_enabled_lab_unlike_local_cyp(install, monkeypatch):
    install([model(), model(TaskConfig(**FREESOLV_TASK).model_dump(), id="freesolv")])
    monkeypatch.delenv("CHEMANALYZER_RESEARCH_ENABLED", raising=False)
    result = modules()
    assert not result["hydration"]["available"] and result["hydration"]["status"] == "disabled"
    assert result["cyp"]["available"]
    response = TestClient(app).post("/api/research/models/freesolv/predict", json=dict(smiles="CCO"))
    assert response.status_code == 403


def test_generic_growth_registry_record_cannot_enable_a_different_specialized_predictor(install):
    task = dict(domain="growth", kind="regression", units="ratio", endpoint="primary_root_length_relative_to_control",
                context="Arabidopsis thaliana hypothetical software-only context")
    install([model(task)])
    assert modules()["growth"]["status"] == "not_trained"


def test_artifact_checksum_is_checked_without_unpickling_during_catalog_review(tmp_path, monkeypatch):
    registry = Registry(tmp_path)
    meta = registry.register(dict(software_fixture=True), dict(task=cyp.task_config("CYP1A2"), evaluation={}))
    monkeypatch.setattr("app.ai_research_agent.model_registry.joblib.load", lambda *args: pytest.fail("No deserialization needed for a checksum check"))
    assert registry.verify_artifact(meta["id"])["id"] == meta["id"]
    (tmp_path / "models" / meta["id"] / "model.joblib").write_bytes(b"corrupted software fixture")
    with pytest.raises(ValueError, match="checksum"): registry.load(meta["id"])


def test_registry_failure_does_not_claim_untrained_or_suppress_other_storage(monkeypatch, install):
    class BrokenRegistry:
        def list(self): raise OSError("fixture unreadable storage")
    monkeypatch.setattr(catalog, "Registry", lambda root: BrokenRegistry())
    result = modules()
    assert result["cyp"]["status"] == "error" and result["hydration"]["status"] == "error"
    assert result["targets"]["status"] == "quality_failed" and result["antidote"]["status"] == "not_trained"
