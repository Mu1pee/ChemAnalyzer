"""Release integration tests; fabricated rows below are test fixtures only."""
import hashlib
import json
import joblib

from app.chemistry import qsar
from training.train_assay import prepare


def record(**changes):
    return dict(target_chembl_id="CHEMBL230", assay_chembl_id="CHEMBL763870", standard_type="IC50",
                standard_relation="=", standard_units="nM", target_organism="Homo sapiens", assay_type="B",
                data_validity_comment=None, potential_duplicate=0, pchembl_value="6.5",
                canonical_smiles="CCO", activity_id=1, **changes)


def test_assay_curation_keeps_trace_and_excludes_conflicting_duplicates():
    rows = [record(), {**record(), "activity_id": 2, "pchembl_value": "4.0"},
            {**record(), "canonical_smiles": "c1ccccc1", "activity_id": 3}]
    accepted, excluded = prepare(rows, "CHEMBL230", "CHEMBL763870")
    assert len(accepted) == 1
    assert accepted[0]["activity_ids"] == [3]
    assert excluded["conflicting_compound"] == 1


def test_assay_curation_rejects_wrong_context_and_nonfinite_labels():
    rows = [{**record(), "target_organism": "Mus musculus"},
            {**record(), "standard_type": "Ki"}, {**record(), "pchembl_value": "nan"}]
    accepted, excluded = prepare(rows, "CHEMBL230", "CHEMBL763870")
    assert not accepted
    assert sum(excluded.values()) == 3


def save_bundle(root, name, model_id):
    root.mkdir()
    file = root / name
    joblib.dump({"meta": {"target_id": "CHEMBL230", "model_id": model_id,
                         "n_active": 50, "n_inactive": 50, "y_random_auc": .5,
                         "metrics": dict(roc_auc=.8, balanced_accuracy=.7, mcc=.4, n_evaluated=100)}}, file)
    entry = {"target_id": "CHEMBL230", "model_file": name,
             "artifact_sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
    (root / "manifest.json").write_text(json.dumps({"models": [entry]}))


def test_bundled_models_merge_without_overwriting_user_models(tmp_path, monkeypatch):
    user, bundle = tmp_path / "user", tmp_path / "bundle"
    save_bundle(user, "old.joblib", "user-model")
    save_bundle(bundle, "new.joblib", "new-model")
    original = (user / "manifest.json").read_bytes()
    monkeypatch.setattr(qsar, "MODELS_DIR", user)
    monkeypatch.setenv("CHEMANALYZER_BUNDLED_QSAR_DIR", str(bundle))
    qsar.reload_models()
    try:
        models, error = qsar._load_models()
        assert error is None
        assert {m["meta"]["model_id"] for m in models} == {"user-model", "new-model"}
        assert (user / "manifest.json").read_bytes() == original
    finally:
        qsar.reload_models()


def test_model_checksum_mismatch_is_rejected(tmp_path, monkeypatch):
    user = tmp_path / "models"
    save_bundle(user, "model.joblib", "one")
    (user / "model.joblib").write_bytes(b"invalid-model")
    monkeypatch.setattr(qsar, "MODELS_DIR", user)
    monkeypatch.delenv("CHEMANALYZER_BUNDLED_QSAR_DIR", raising=False)
    qsar.reload_models()
    try:
        models, error = qsar._load_models()
        assert not models
        assert "checksum" in error
    finally:
        qsar.reload_models()
