"""Tests for the Antidote-Prediction module without bundled/fake models."""
import csv
from pathlib import Path

import pytest
from rdkit import Chem

from app.chemistry import specialized_activity as sa
from training import train_specialized as trainer


def test_no_models_returns_explicit_not_trained(monkeypatch, tmp_path):
    monkeypatch.setattr(sa, "MODEL_DIR", tmp_path)
    sa.reload_models()
    result = sa.predict_specialized_activity("CCO")
    assert result["canonical_smiles"] == "CCO"
    assert result["antidote"]["status"] == "not_trained"
    assert result["growth_regulating"]["status"] == "not_trained"
    assert result["antidote"]["predictions"] == []
    assert "не обучена" in result["antidote"]["message"]
    sa.reload_models()


def test_invalid_smiles_is_rejected():
    with pytest.raises(ValueError, match="Некорректный SMILES"):
        sa.predict_specialized_activity("definitely not a smiles")


def test_csv_template_is_valid_and_empty():
    path = trainer.DATA_DIR / "antidote.csv"
    loaded, errors = trainer.read_dataset(path)
    assert errors == []
    assert loaded["tasks"] == []
    assert loaded["report"]["rows_read"] == 0


def test_dataset_rejects_missing_provenance_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("smiles,label,endpoint\nCCO,1,test\n", encoding="utf-8")
    _, errors = trainer.read_dataset(path)
    assert errors and "source" in errors[0]


def test_training_refuses_too_small_sample():
    mol = Chem.MolFromSmiles("CCO")
    task = {
        "endpoint": "test endpoint",
        "context": "test context",
        "rows": [
            {"smiles": "CCO", "mol": mol, "label": 1, "scaffold": "CCO", "sources": ["test — doi:test"]},
            {"smiles": "CCN", "mol": Chem.MolFromSmiles("CCN"), "label": 0, "scaffold": "CCN", "sources": ["test — doi:test"]},
        ],
    }
    result, reason, report = trainer.fit_endpoint(
        "antidote", task, min_per_class=30, min_auc=0.70, seed=42
    )
    assert result is None
    assert reason and "нужно не менее 30" in reason
    assert report["accepted"] is False


def test_model_manifest_does_not_trust_paths(monkeypatch, tmp_path):
    (tmp_path / "manifest.json").write_text(
        '{"models":[{"domain":"antidote","model_file":"../outside.joblib"}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(sa, "MODEL_DIR", tmp_path)
    sa.reload_models()
    result = sa.predict_specialized_activity("CCO")
    assert result["antidote"]["status"] == "not_trained"
    sa.reload_models()


def test_manifest_with_missing_model_reports_load_error(monkeypatch, tmp_path):
    (tmp_path / "manifest.json").write_text(
        '{"models":[{"domain":"antidote","model_file":"antidote-missing.joblib"}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(sa, "MODEL_DIR", tmp_path)
    sa.reload_models()
    result = sa.predict_specialized_activity("CCO")
    assert result["antidote"]["status"] == "error"
    assert "отсутствующие файлы моделей" in result["antidote"]["message"]
    sa.reload_models()


def test_specialized_api_endpoint_returns_explicit_not_trained_status():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        response = client.post("/api/molecules/specialized-activity", json={"smiles": "CCO"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["antidote"]["status"] == "not_trained"
    assert payload["growth_regulating"]["status"] == "not_trained"
    assert "экспериментальное подтверждение" in payload["disclaimer"]
