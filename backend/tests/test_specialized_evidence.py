"""Software fixtures only: no biological training rows or deployable models."""
import copy
import hashlib
import json

import joblib
import numpy as np
import pytest
from pydantic import ValidationError

from app.chemistry import specialized_activity as sa
from app.chemistry.specialized_evidence import FEATURE_CONFIG, PROFILES, SpecializedProtocol, quality
from app.ai_research_agent.evaluation import scaffold_split
from app.model_quality import finite
from training import train_specialized as trainer


def protocol():
    context = "Software fixture; not experimental evidence or a biological result"
    endpoint = PROFILES["arabidopsis_primary_root"]["endpoint"]
    return dict(schema_version=2, profile_id="arabidopsis_primary_root", domain="growth_regulating",
                endpoint=endpoint, context=context, species="Arabidopsis thaliana", toxicant=None,
                conditions={key: "software fixture only" for key in PROFILES["arabidopsis_primary_root"]["conditions"]},
                label_definition="Software fixture labels with no biological meaning; never train a real model from them.",
                dataset_sha256="0" * 64,
                provenance=dict(source_url="https://example.org/software-fixture", doi="software-fixture-not-science",
                                license="CC0-1.0", license_url="https://example.org/fixture-license", source_version="software-fixture",
                                retrieved_at="2026-11-11T00:00:00Z", curator="Software fixture", experimental=True,
                                endpoint=endpoint, context=context, units="0/1"))


@pytest.mark.parametrize("change", [dict(species="Oryza sativa"), dict(toxicant="acetaminophen"),
                                    dict(endpoint="auxin_receptor_binding"), dict(conditions={})])
def test_other_species_endpoints_and_missing_protocol_conditions_are_rejected(change):
    with pytest.raises(ValidationError):
        SpecializedProtocol.model_validate(dict(protocol(), **change))


def test_antidote_requires_matching_toxicant_species_and_experimental_source():
    data = protocol()
    data.update(profile_id="apap_rescue", domain="antidote", endpoint=PROFILES["apap_rescue"]["endpoint"],
                species="test hepatocytes", toxicant="paracetamol",
                conditions={key: "software fixture only" for key in PROFILES["apap_rescue"]["conditions"]})
    data["conditions"]["species"] = data["species"]
    data["provenance"]["endpoint"] = data["endpoint"]
    assert SpecializedProtocol.model_validate(data).toxicant == "paracetamol"
    for mutation in (lambda d: d.update(toxicant="another toxicant"),
                     lambda d: d["provenance"].update(experimental=False),
                     lambda d: d["provenance"].update(license="not-verified"),
                     lambda d: d["provenance"].update(context="another protocol")):
        changed = copy.deepcopy(data)
        mutation(changed)
        with pytest.raises(ValueError):
            SpecializedProtocol.model_validate(changed)


def test_salts_rejected_and_acyclic_variants_share_a_group(tmp_path):
    path = tmp_path / "test.csv"
    path.write_text("smiles,label,endpoint,context,source,source_id\n"
                    "CCO,1,fixture,test context,software,fixture-1\n"
                    "CCN,0,fixture,test context,software,fixture-2\n"
                    "CCO.Cl,1,fixture,test context,software,fixture-3\n", encoding="utf-8")
    data, errors = trainer.read_dataset(path)
    assert not errors and data["report"]["invalid_rows"] == 1
    assert {row["scaffold"] for row in data["tasks"][0]["rows"]} == {"ACYCLIC"}


def task_fixture(monkeypatch):
    p = protocol()
    task = dict(endpoint=p["endpoint"], context=p["context"], protocol=p, rows=[
        dict(mol=i, smiles="SOFTWARE_FIXTURE", label=i % 2, scaffold=f"fixture_group_{i}", sources=["Software fixture only"])
        for i in range(200)])
    original_features = trainer.fp.fingerprint_array
    monkeypatch.setattr(trainer.fp, "fingerprint_array", lambda i:
                        np.array([i, i % 2] + [0] * 2046, dtype=np.uint8) if isinstance(i, int) else original_features(i))
    fitted = []
    class Estimator:
        classes_ = np.array([0, 1])
        def fit(self, X, y):
            self.fitted_indices = X[:, 0].astype(int).tolist()
            fitted.append(self)
            return self
        def predict(self, X):
            return X[:, 1].astype(int)
        def predict_proba(self, X):
            p = np.where(self.predict(X) == 1, .9, .1)
            return np.column_stack((1-p, p))
    monkeypatch.setattr(trainer, "create_model", lambda *args, **kwargs: Estimator())
    return task, fitted


def test_exact_evaluated_model_saved_without_refitting_on_validation_or_test(monkeypatch):
    task, fitted = task_fixture(monkeypatch)
    result, reason, report = trainer.fit_endpoint("growth_regulating", task, 30, .70, 42)
    assert reason is None and result and report["accepted"]
    _, bundle = result
    meta = bundle["meta"]
    assert len(fitted) == 3 and bundle["model"] is fitted[0]
    split = meta["evaluation"]["split"]
    assert all(set(model.fitted_indices) == set(split["train"]) for model in fitted)
    assert not set(split["train"]) & set(split["test"])
    assert not set(split["validation"]) & set(split["test"])
    assert meta["n_train"] == len(split["train"]) < len(task["rows"])
    assert meta["n_test"] == meta["metrics"]["n_evaluated"] == len(split["test"])
    assert bundle["train_packed"].shape[0] == meta["n_train"]
    assert meta["evaluation"]["test_used_for_selection"] is False and quality(meta)["passed"]


def test_failed_fixed_test_does_not_trigger_selection_or_refitting(monkeypatch):
    task, fitted = task_fixture(monkeypatch)
    groups = np.array([hashlib.sha1(row["scaffold"].encode()).hexdigest()[:16] for row in task["rows"]])
    y = np.array([row["label"] for row in task["rows"]])
    _, _, test = scaffold_split(y, groups, 42)
    for index in test:
        task["rows"][index]["label"] = 1-task["rows"][index]["label"]
    result, reason, report = trainer.fit_endpoint("growth_regulating", task, 30, .70, 42)
    assert result is None and not report["accepted"] and "Balanced accuracy" in reason
    assert report["evaluation"]["selected"] == "random_forest"
    assert len(fitted) == 3


def test_legacy_high_cv_scores_do_not_substitute_for_the_new_evidence():
    assert not quality(dict(metrics=dict(balanced_accuracy=.99, roc_auc=.99, mcc=.9)))["passed"]


def test_candidate_and_saved_forest_have_identical_parameters():
    assert trainer.create_model("random_forest", 42).get_params() == trainer.create_model("random_forest", 42, final=True).get_params()


def test_checksum_failure_is_detected_before_deserialization(monkeypatch, tmp_path):
    path = tmp_path / "old.joblib"
    path.write_bytes(b"not a model")
    (tmp_path / "manifest.json").write_text(json.dumps(dict(models=[dict(domain="antidote", model_file=path.name)])))
    monkeypatch.setattr(joblib, "load", lambda *args: pytest.fail("Unchecked artifact must never deserialize"))
    monkeypatch.setattr(sa, "MODEL_DIR", tmp_path)
    sa.reload_models()
    try:
        result = sa.predict_specialized_activity("CCO")
        assert result["antidote"]["status"] == "error"
        assert result["growth_regulating"]["status"] == "not_trained"
        assert path.read_bytes() == b"not a model"
    finally:
        sa.reload_models()


def test_enormous_numeric_metadata_are_rejected_without_overflow():
    assert finite(10**1000) is False


def test_overlapping_partitions_cannot_pass_using_high_reported_metrics(monkeypatch):
    task, _ = task_fixture(monkeypatch)
    result, _, _ = trainer.fit_endpoint("growth_regulating", task, 30, .70, 42)
    meta = copy.deepcopy(result[1]["meta"])
    meta["evaluation"]["split"]["test"][0] = meta["evaluation"]["split"]["train"][0]
    assert not quality(meta)["passed"]


def test_corrupt_antidote_artifact_does_not_disable_valid_growth_api_fields(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    task, _ = task_fixture(monkeypatch)
    result, _, _ = trainer.fit_endpoint("growth_regulating", task, 30, .70, 42)
    bundle = result[1]
    path = tmp_path / "growth-software-fixture.joblib"
    path.write_bytes(b"software test fixture; never a deployable artifact")
    records = [dict(domain="growth_regulating", model_file=path.name, artifact_sha256=hashlib.sha256(path.read_bytes()).hexdigest()),
               dict(domain="antidote", model_file="missing-antidote.joblib")]
    (tmp_path / "manifest.json").write_text(json.dumps(dict(models=records)), encoding="utf-8")
    monkeypatch.setattr(joblib, "load", lambda filename: bundle)
    monkeypatch.setattr(sa, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(sa.core, "max_tanimoto", lambda *args: .9)
    sa.reload_models()
    try:
        response = TestClient(app).post("/api/molecules/specialized-activity", json=dict(smiles="CCO"))
        assert response.status_code == 200
        data = response.json()
        assert data["antidote"]["status"] == "error"
        prediction = data["growth_regulating"]["predictions"][0]
        assert data["growth_regulating"]["status"] == "ready"
        assert prediction["quality"]["passed"] and prediction["n_test"] == bundle["meta"]["n_test"]
        assert prediction["test_positive"] + prediction["test_negative"] == prediction["n_test"]
        monkeypatch.setattr(sa.core, "max_tanimoto", lambda *args: .1)
        prediction = sa.predict_specialized_activity("CCO")["growth_regulating"]["predictions"][0]
        assert prediction["probability"] is None and prediction["predicted_label"] is None
    finally:
        sa.reload_models()


def test_protocol_checksum_must_match_the_read_csv_snapshot(monkeypatch, tmp_path):
    source = tmp_path / "data"
    source.mkdir()
    path = source / "growth_regulating.csv"
    p = protocol()
    path.write_text("smiles,label,endpoint,context,source,source_id\n"
                    f'CCO,1,{p["endpoint"]},{p["context"]},software-fixture,not-science\n', encoding="utf-8")
    path.with_suffix(".protocol.json").write_text(json.dumps(p), encoding="utf-8")
    models = tmp_path / "models"
    monkeypatch.setattr("sys.argv", ["trainer", "--domain", "growth_regulating", "--data-dir", str(source), "--models-dir", str(models)])
    assert trainer.main() == 1
    report = json.loads((models / "training_report.json").read_text(encoding="utf-8"))
    assert "CSV checksum" in report["rejected"][0]["reason"]
    assert not list(models.glob("*.joblib"))


@pytest.mark.parametrize("damaged", ["{invalid", "[]", '{"models":42}'])
def test_failed_retraining_preserves_damaged_manifest(monkeypatch, tmp_path, damaged):
    data = tmp_path / "data"
    data.mkdir()
    (data / "growth_regulating.csv").write_text("smiles,label,endpoint,context,source,source_id\n", encoding="utf-8")
    models = tmp_path / "models"
    models.mkdir()
    manifest = models / "manifest.json"
    manifest.write_text(damaged, encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["trainer", "--domain", "growth_regulating", "--data-dir", str(data), "--models-dir", str(models)])
    assert trainer.main() == 1
    assert manifest.read_text(encoding="utf-8") == damaged
    report = json.loads((models / "training_report.json").read_text(encoding="utf-8"))
    assert report["manifest_updated"] is False


def test_duplicate_headers_rejected_and_extra_fields_counted_as_invalid(tmp_path):
    path = tmp_path / "test.csv"
    path.write_text("smiles,label,endpoint,context,source,source_id,label\n", encoding="utf-8")
    _, errors = trainer.read_dataset(path)
    assert errors and "Duplicate" in errors[0]
    path.write_text("smiles,label,endpoint,context,source,source_id\nCCO,1,fixture,context,software,not-science,extra\n", encoding="utf-8")
    result, errors = trainer.read_dataset(path)
    assert not errors and result["report"]["rows_read"] == result["report"]["invalid_rows"] == 1
    assert result["tasks"] == []
