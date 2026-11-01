"""Предсказание активности обученными QSAR-моделями (models/*.joblib).

Если моделей нет (обучение ещё не запускали), приложение работает как
раньше, а вкладка показывает подсказку, как их обучить.
"""

import json
from functools import lru_cache
from pathlib import Path

from app import config

from app.chemistry import fingerprints as fp
from app.chemistry import qsar_core as core

MODELS_DIR: Path = config.models_dir()
TOP_N = 12

NOT_TRAINED_MESSAGE = (
    "QSAR-модель не обучена. Доступна структурная similarity-оценка, но это "
    "не экспериментальное подтверждение активности."
)

DISCLAIMER = (
    "Вероятность — результат модели, обученной на данных ChEMBL о "
    "соединениях, которые уже тестировали на мишени. Модель отличает "
    "сильные соединения от слабых среди известных аналогов, поэтому для "
    "структур, не похожих на обучающую выборку (см. область применимости), "
    "вероятность может быть завышена. Это не эксперимент."
)


@lru_cache(maxsize=1)
def _load_models() -> tuple[list[dict], str | None]:
    manifest = MODELS_DIR / "manifest.json"
    if not manifest.exists():
        return [], None

    try:
        import joblib  # импорт здесь: без моделей зависимость не нужна

        entries = json.loads(manifest.read_text(encoding="utf-8"))["models"]
        bundles = []
        for entry in entries:
            path = MODELS_DIR / f"{entry['target_id']}.joblib"
            if path.exists():
                bundles.append(joblib.load(path))
    except Exception as error:
        return [], f"Не удалось загрузить модели: {error}"

    if not bundles:
        return [], "Манифест есть, но файлы моделей не найдены."
    return bundles, None


def _version(meta: dict) -> str:
    date = str(meta.get("trained_at", ""))[:10] or "дата неизвестна"
    sk = meta.get("sklearn_version", "?")
    return f"случайный лес + калибровка · обучена {date} · scikit-learn {sk}"


def reload_models() -> None:
    _load_models.cache_clear()


def predict_qsar(smiles: str) -> dict:
    bundles, problem = _load_models()
    if bundles:
        status, message = "ready", None
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
    }
    if not bundles:
        return base

    mol = fp.mol_from_smiles(smiles)
    if mol is None:
        raise ValueError(
            "Некорректный SMILES. Не удалось распознать химическую структуру."
        )

    mol = fp.standardize(mol)
    x = fp.fingerprint_array(mol).reshape(1, -1)
    x_packed = core.pack_bits(x)[0]

    predictions = []
    for bundle in bundles:
        meta = bundle["meta"]
        probability = float(bundle["model"].predict_proba(x)[0, 1])
        similarity = core.max_tanimoto(
            x_packed, bundle["train_packed"], bundle["train_popcount"]
        )
        predictions.append(
            {
                "model_version": _version(meta),
                "target_id": meta["target_id"],
                "target_name": meta["label"],
                "chembl_name": meta.get("chembl_name"),
                "probability": round(probability, 3),
                "domain": core.domain_label(similarity),
                "max_similarity": round(similarity, 3),
                "cv_auc": meta["metrics"]["roc_auc"],
                "n_train": meta["n_train"],
                "active_pchembl": meta["active_pchembl"],
            }
        )

    # Сначала в области применимости, затем по вероятности.
    order = {"в области применимости": 0, "на границе области": 1}
    predictions.sort(
        key=lambda p: (order.get(p["domain"], 2), -p["probability"])
    )
    base["predictions"] = predictions[:TOP_N]
    return base
