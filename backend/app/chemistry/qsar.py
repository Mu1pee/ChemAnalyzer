"""Предсказание активности обученными QSAR-моделями (models/*.joblib).

Если моделей нет (обучение ещё не запускали), приложение работает как
раньше, а вкладка показывает подсказку, как их обучить.
"""

import json
import hashlib
import os
from functools import lru_cache
from pathlib import Path
import numpy as np

from app import config

from app.chemistry import fingerprints as fp
from app.chemistry import qsar_core as core
from app.chemistry.qsar_evidence import admission, describe_model
from app.model_quality import finite

MODELS_DIR: Path = config.models_dir()
TOP_N = 12

NOT_TRAINED_MESSAGE = (
    "Нет QSAR-модели, прошедшей текущую проверку. Доступна структурная similarity-оценка, но это "
    "не экспериментальное подтверждение активности."
)

DISCLAIMER = (
    "Исследовательская оценка класса по измеренным IC50, не экспериментальное подтверждение. "
    "Качество проверяется на ретроспективном внутреннем тесте по каркасам; внешней валидации нет. "
    "Оценка класса не гарантирует клинический эффект или калибровку на новых структурах. "
    "Вне эвристической области применимости численный прогноз скрыт."
)


@lru_cache(maxsize=1)
def _load_models():
    sources = [MODELS_DIR]
    bundled = os.environ.get("CHEMANALYZER_BUNDLED_QSAR_DIR", "").strip()
    if bundled and Path(bundled).resolve() != MODELS_DIR.resolve():
        sources.append(Path(bundled))
    manifests = [(root, root / "manifest.json") for root in sources if (root / "manifest.json").is_file()]
    if not manifests:
        return [], None, []
    import joblib
    bundles, problems, rejected, seen = [], [], [], set()
    for root, manifest in manifests:
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            entries = payload["models"]
            if not isinstance(entries, list):
                raise ValueError("Invalid model manifest")
            for item in payload.get("declined", []):
                if isinstance(item, dict):
                    # Only the release's explicit held-out rejection summary;
                    # no fabricated compound prediction is returned from it.
                    rejected.append(item)
        except (ValueError, KeyError, TypeError, OSError) as error:
            problems.append("Manifest unavailable: " + type(error).__name__)
            continue
        for entry in entries:
            try:
                if not isinstance(entry, dict):
                    raise ValueError("Invalid model entry")
                name = entry["model_file"]
                path = root / name
                if Path(name).name != name or path.suffix != ".joblib" or path.resolve().parent != root.resolve():
                    raise ValueError("Invalid model artifact path")
                expected_hash = entry.get("artifact_sha256")
                if not expected_hash or hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
                    raise ValueError("Model checksum mismatch")
                check = admission(entry)
                if not check["passed"]:
                    rejected.append(dict(target_id=entry.get("target_id"), evidence="legacy_or_incompatible", reasons=check["reasons"]))
                    continue
                bundle = joblib.load(path)
                meta = bundle["meta"]
                check = admission(meta)
                if not check["passed"]:
                    rejected.append(dict(target_id=meta.get("target_id"), evidence="incompatible_bundle", reasons=check["reasons"]))
                    continue
                if (describe_model(bundle["model"], bundle.get("train_groups")) != meta["procedure"]
                        or list(bundle["model"].classes_) != [0, 1]
                        or bundle["model"].n_features_in_ != fp.N_BITS
                        or np.asarray(bundle["train_packed"]).shape != (meta["n_train"], fp.N_BITS // 8)
                        or not np.array_equal(core.popcounts(np.asarray(bundle["train_packed"])), bundle["train_popcount"])):
                    raise ValueError("Fitted procedure, features or applicability evidence mismatch")
                key = meta.get("model_id", f"{meta['target_id']}:{meta.get('assay_id', 'legacy')}")
                if key not in seen:
                    bundle["quality"] = check
                    bundles.append(bundle)
                    seen.add(key)
            except Exception as error:
                problems.append(f"Model unavailable: {type(error).__name__}: {error}")
    if rejected:
        problems.append("Модели, не прошедшие текущую проверку, исключены из прогнозирования.")
    return bundles, " | ".join(problems) or None, rejected


def _version(meta: dict) -> str:
    date = str(meta.get("trained_at", ""))[:10] or "дата неизвестна"
    algorithm = meta.get("procedure", {}).get("algorithm", "unknown")
    return f"{algorithm} · обучена {date} · отдельный тест без переобучения"


def reload_models() -> None:
    _load_models.cache_clear()


def predict_qsar(smiles: str) -> dict:
    bundles, problem, rejected = _load_models()
    if bundles:
        status, message = "ready", problem
    elif rejected:
        status, message = "quality_failed", "Требуется повторная валидация QSAR-модели. Численный прогноз скрыт."
    elif problem:
        status, message = "error", f"{problem} {NOT_TRAINED_MESSAGE}"
    else:
        status, message = "not_trained", NOT_TRAINED_MESSAGE

    base = {
        "status": status,
        "available": bool(bundles),
        "message": message,
        "models_loaded": len(bundles),
        "predictions": [],
        "disclaimer": DISCLAIMER,
        "rejected_models": rejected,
    }
    if not bundles:
        return base

    mol = fp.mol_from_smiles(smiles)
    if mol is None:
        raise ValueError(
            "Некорректный SMILES. Не удалось распознать химическую структуру."
        )
    if len(__import__("rdkit").Chem.GetMolFrags(mol)) != 1 or mol.GetNumAtoms() > 200:
        raise ValueError("Соли, смеси и слишком большие структуры требуют отдельной курации QSAR.")

    mol = fp.standardize(mol)
    x = fp.fingerprint_array(mol).reshape(1, -1)
    x_packed = core.pack_bits(x)[0]

    predictions = []
    for bundle in bundles:
        meta = bundle["meta"]
        similarity = core.max_tanimoto(
            x_packed, bundle["train_packed"], bundle["train_popcount"]
        )
        probability = float(bundle["model"].predict_proba(x)[0, 1]) if similarity >= core.DOMAIN_EDGE else None
        if probability is not None and (not finite(probability) or not 0 <= probability <= 1):
            raise ValueError("QSAR returned a non-finite or invalid class score")
        predictions.append(
            {
                "model_version": _version(meta),
                "model_id": meta.get("model_id", meta["target_id"]),
                "target_id": meta["target_id"],
                "target_name": meta["label"],
                "chembl_name": meta.get("chembl_name"),
                "probability": round(probability, 3) if probability is not None else None,
                "domain": core.domain_label(similarity),
                "max_similarity": round(similarity, 3),
                "metrics": meta["metrics"],
                "validation_method": "Ретроспективный отложенный тест по каркасам; модель не переобучалась после проверки; внешней валидации нет",
                "n_train": meta["n_train"],
                "n_test": meta["n_test"],
                "test_positive": meta["evaluation"]["support"]["test"]["positive"],
                "test_negative": meta["evaluation"]["support"]["test"]["negative"],
                "active_threshold_nM": meta["active_threshold_nM"],
                "active_pchembl": meta["active_pchembl"],
            }
        )

    # Сначала в области применимости, затем по вероятности.
    order = {"в области применимости": 0, "на границе области": 1}
    predictions.sort(
            key=lambda p: (order.get(p["domain"], 2), -(p["probability"] or 0))
    )
    base["predictions"] = predictions[:TOP_N]
    return base
