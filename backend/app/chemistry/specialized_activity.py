"""Experimental domain-specific activity models for Antidote-Prediction.

Models are not bundled by default. They must be trained from curated,
endpoint-specific experimental data using training/train_specialized.py.
The module deliberately reports `not_trained` instead of inventing a prediction.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from rdkit import Chem

from app import config
from app.model_quality import classification_reasons
from app.chemistry import fingerprints as fp
from app.chemistry import qsar_core as core

MODEL_DIR = config.models_dir() / "specialized_activity"
DOMAINS: dict[str, str] = {
    "antidote": "Антидотная активность",
    "growth_regulating": "Рострегулирующая активность",
}
NOT_TRAINED_MESSAGES = {
    "antidote": (
        "Модель антидотной активности не обучена. Добавьте проверенные "
        "экспериментальные данные для конкретного токсиканта и endpoint, "
        "затем запустите обучение."
    ),
    "growth_regulating": (
        "Модель рострегулирующей активности не обучена. Добавьте "
        "экспериментальные данные с указанием культуры, теста и endpoint, "
        "затем запустите обучение."
    ),
}
DISCLAIMER = (
    "Исследовательская оценка, а не медицинская, токсикологическая или "
    "агрономическая рекомендация. Прогноз применим только к конкретному "
    "endpoint и области применимости проверенной модели. Он не заменяет "
    "экспериментальное подтверждение."
)


def _empty_domain(domain: str, status: str = "not_trained", message: str | None = None) -> dict:
    return {
        "domain": domain,
        "title": DOMAINS[domain],
        "status": status,
        "models_available": 0,
        "predictions": [],
        "message": message or NOT_TRAINED_MESSAGES[domain],
    }


@lru_cache(maxsize=1)
def _load_bundles() -> tuple[dict[str, list[dict[str, Any]]], str | None]:
    manifest_path = MODEL_DIR / "manifest.json"
    grouped: dict[str, list[dict[str, Any]]] = {key: [] for key in DOMAINS}
    if not manifest_path.is_file():
        return grouped, None

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = manifest.get("models", [])
        if not isinstance(records, list):
            raise ValueError("Поле models в manifest.json должно быть списком.")
        import joblib

        missing_model_files: list[str] = []
        rejected: dict[str, list[str]] = {key: [] for key in DOMAINS}
        for record in records:
            if not isinstance(record, dict):
                continue
            domain = record.get("domain")
            filename = record.get("model_file")
            # Только имя файла, никаких путей из манифеста.
            if domain not in DOMAINS or not isinstance(filename, str):
                continue
            if (Path(filename).name != filename or "/" in filename or "\\" in filename
                    or not filename.endswith(".joblib")):
                continue
            model_path = MODEL_DIR / filename
            if not model_path.is_file():
                missing_model_files.append(filename)
                continue
            bundle = joblib.load(model_path)
            if not isinstance(bundle, dict) or not all(
                key in bundle for key in ("model", "train_packed", "train_popcount", "meta")
            ):
                continue
            meta = bundle["meta"]
            if not isinstance(meta, dict) or meta.get("domain") != domain:
                continue
            reasons = classification_reasons(meta.get("metrics"), min_mcc=0.10)
            if (meta.get("metrics") or {}).get("n_evaluated") != meta.get("n_train"):
                reasons.append("Incomplete out-of-fold evaluation")
            if min(meta.get("n_active", 0), meta.get("n_inactive", 0)) < 30:
                reasons.append("At least 30 compounds per class required")
            if reasons:
                rejected[domain] += reasons
                continue
            grouped[domain].append(bundle)
        for domain, reasons in rejected.items():
            if reasons and not grouped[domain]:
                # Domain-specific failure must not suppress a valid model in another domain.
                grouped[domain] = [{"rejected": "; ".join(dict.fromkeys(reasons))}]
        if missing_model_files:
            return grouped, "В manifest.json указаны отсутствующие файлы моделей: " + ", ".join(missing_model_files[:5])
    except Exception as error:
        return grouped, f"Не удалось загрузить модели Антидот-Прогноз: {error}"

    return grouped, None


def reload_models() -> None:
    """Очистить кэш после повторного обучения/обновления manifest.json."""
    _load_bundles.cache_clear()


def predict_specialized_activity(smiles: str) -> dict:
    mol = fp.mol_from_smiles(smiles)
    if mol is None:
        raise ValueError("Некорректный SMILES. Не удалось распознать структуру.")

    mol = fp.standardize(mol)
    canonical_smiles = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
    features = fp.fingerprint_array(mol).reshape(1, -1)
    packed = core.pack_bits(features)[0]
    models_by_domain, load_problem = _load_bundles()

    results: dict[str, dict] = {}
    for domain, title in DOMAINS.items():
        bundles = models_by_domain[domain]
        if load_problem:
            results[domain] = _empty_domain(domain, "error", load_problem)
            continue
        if not bundles:
            results[domain] = _empty_domain(domain)
            continue
        if "rejected" in bundles[0]:
            results[domain] = _empty_domain(domain, "error", "Модель не прошла контроль качества: " + bundles[0]["rejected"])
            continue

        predictions = []
        for bundle in bundles:
            model = bundle["model"]
            meta = bundle["meta"]
            train_packed = np.asarray(bundle["train_packed"], dtype=np.uint8)
            train_popcount = np.asarray(bundle["train_popcount"], dtype=np.int64)
            similarity = core.max_tanimoto(packed, train_packed, train_popcount)
            classes = list(getattr(model, "classes_", []))
            if 1 not in classes or 0 not in classes:
                continue
            probabilities = model.predict_proba(features)[0]
            probability = float(probabilities[classes.index(1)])
            in_domain = similarity >= float(meta.get("domain_edge_threshold", core.DOMAIN_EDGE))
            model_status = "ready" if in_domain else "out_of_domain"
            predictions.append({
                "endpoint": str(meta.get("endpoint", "Endpoint не указан")),
                "context": str(meta.get("context", "Контекст не указан")),
                "status": model_status,
                "probability": round(probability, 4) if in_domain else None,
                "predicted_label": (1 if probability >= float(meta.get("decision_threshold", 0.5)) else 0) if in_domain else None,
                "similarity": round(float(similarity), 4),
                "domain_label": core.domain_label(float(similarity)),
                "model_version": str(meta.get("model_version", "1.0")),
                "trained_at": meta.get("trained_at"),
                "n_train": int(meta.get("n_train", 0)),
                "n_active": int(meta.get("n_active", 0)),
                "n_inactive": int(meta.get("n_inactive", 0)),
                "metrics": meta.get("metrics", {}),
                "dataset_source": str(meta.get("dataset_source", "Не указан")),
                "message": None if in_domain else (
                    "Структура находится вне области применимости этой модели. "
                    "Вероятность не показывается как интерпретируемый прогноз."
                ),
            })

        predictions.sort(
            key=lambda item: (
                item["status"] != "ready",
                -float(item["similarity"]),
                item["endpoint"],
            )
        )
        results[domain] = {
            "domain": domain,
            "title": title,
            "status": "ready" if predictions else "error",
            "models_available": len(predictions),
            "predictions": predictions,
            "message": None if predictions else "Загруженные модели не содержат обеих меток классов.",
        }

    return {
        "input_smiles": smiles,
        "canonical_smiles": canonical_smiles,
        "antidote": results["antidote"],
        "growth_regulating": results["growth_regulating"],
        "disclaimer": DISCLAIMER,
    }
