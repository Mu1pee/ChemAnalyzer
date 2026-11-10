"""Ядро QSAR: метрики, кросс-валидация, обучение, область применимости.

Модуль не зависит от RDKit — только numpy и scikit-learn, поэтому его
можно тестировать на любых числовых данных.
"""

import numpy as np
from app.model_quality import classification_reasons, finite
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    matthews_corrcoef,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold

POPCOUNT = np.array([bin(i).count("1") for i in range(256)], dtype=np.int64)

# Пороги области применимости (макс. сходство Tanimoto с обучающей выборкой).
DOMAIN_IN = 0.50
DOMAIN_EDGE = 0.30


# ---------- область применимости ----------


def pack_bits(X: np.ndarray) -> np.ndarray:
    return np.packbits(X.astype(np.uint8), axis=1)


def popcounts(packed: np.ndarray) -> np.ndarray:
    return POPCOUNT[packed].sum(axis=1)


def max_tanimoto(
    x_packed: np.ndarray, train_packed: np.ndarray, train_pop: np.ndarray
) -> float:
    """Максимальное сходство Tanimoto молекулы с обучающей выборкой."""
    inter = POPCOUNT[np.bitwise_and(train_packed, x_packed)].sum(axis=1)
    union = train_pop + int(POPCOUNT[x_packed].sum()) - inter
    sim = np.where(union > 0, inter / np.maximum(union, 1), 0.0)
    return float(sim.max()) if sim.size else 0.0


def domain_label(similarity: float) -> str:
    if similarity >= DOMAIN_IN:
        return "в области применимости"
    if similarity >= DOMAIN_EDGE:
        return "на границе области"
    return "вне области применимости"


# ---------- модель ----------


def _forest(n_estimators: int, seed: int) -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=n_estimators,
        class_weight="balanced_subsample",
        n_jobs=-1,
        random_state=seed,
    )


def fit_model(
    X: np.ndarray, y: np.ndarray, n_estimators: int, seed: int
):
    """Случайный лес + калибровка вероятностей (сигмоида).

    Один и тот же конвейер используется и в кросс-валидации, и в финальной
    модели, чтобы метрики описывали именно то, что будет работать в
    приложении. Без калибровки лес занижает вероятность редкого класса,
    и порог 0.5 почти никого не относит к активным.
    """
    forest = _forest(n_estimators, seed)
    folds = int(min(3, np.bincount(y).min()))
    if folds >= 2:
        # ensemble=False: хранится ОДИН лес (обученный на всех данных),
        # калибратор подбирается по внеобучающим предсказаниям. Это втрое
        # компактнее ансамбля по умолчанию — важно для размера моделей.
        model = CalibratedClassifierCV(
            estimator=forest, method="sigmoid", cv=folds, ensemble=False
        )
        model.fit(X, y)
        return model
    forest.fit(X, y)
    return forest


def classification_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict:
    y_pred = (y_prob >= 0.5).astype(int)
    return {
        "roc_auc": round(float(roc_auc_score(y_true, y_prob)), 4),
        "pr_auc": round(float(average_precision_score(y_true, y_prob)), 4),
        "balanced_accuracy": round(
            float(balanced_accuracy_score(y_true, y_pred)), 4
        ),
        "mcc": round(float(matthews_corrcoef(y_true, y_pred)), 4),
    }


def cross_validate(
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    n_splits: int = 5,
    seed: int = 0,
    n_estimators: int = 200,
) -> dict | None:
    """Кросс-валидация с разбиением по скаффолдам.

    Молекулы с одним скаффолдом попадают в один фолд, поэтому оценка
    честнее случайного разбиения (нет «утечки» близких аналогов).
    """
    cv = StratifiedGroupKFold(
        n_splits=n_splits, shuffle=True, random_state=seed
    )
    oof = np.full(len(y), np.nan)

    for train_idx, test_idx in cv.split(X, y, groups):
        if len(np.unique(y[train_idx])) < 2:
            continue
        model = fit_model(X[train_idx], y[train_idx], n_estimators, seed)
        oof[test_idx] = model.predict_proba(X[test_idx])[:, 1]

    mask = ~np.isnan(oof)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return None

    metrics = classification_metrics(y[mask], oof[mask])
    metrics["n_evaluated"] = int(mask.sum())
    return metrics


def y_randomization_auc(
    X: np.ndarray, y: np.ndarray, groups: np.ndarray, seed: int = 0
) -> float | None:
    """AUC при перемешанных метках. Должен быть ≈ 0.5, иначе есть утечка."""
    rng = np.random.default_rng(seed)
    shuffled = rng.permutation(y)
    result = cross_validate(
        X, shuffled, groups, seed=seed, n_estimators=100
    )
    return result["roc_auc"] if result else None


def train_final(X: np.ndarray, y: np.ndarray, seed: int = 0):
    """Финальная модель (тот же конвейер, что и в кросс-валидации)."""
    return fit_model(X, y, 300, seed)


def quality_gate(
    metrics: dict | None,
    n_active: int,
    n_inactive: int,
    y_random_auc: float | None,
    min_auc: float = 0.75,
    min_mcc: float = 0.25,
    min_per_class: int = 30,
) -> list[str]:
    """Возвращает список причин отказа (пустой — модель принята)."""
    reasons = []
    if n_active < min_per_class or n_inactive < min_per_class:
        reasons.append(
            f"мало данных (активных {n_active}, неактивных {n_inactive}, "
            f"нужно ≥ {min_per_class} каждого класса)"
        )
    if metrics is None:
        reasons.append("не удалось провести кросс-валидацию")
        return reasons
    reasons += classification_reasons(metrics, min_auc, min_mcc)
    if metrics.get("n_evaluated") != n_active + n_inactive:
        reasons.append("Incomplete out-of-fold evaluation")
    if not finite(y_random_auc) or not 0 <= y_random_auc <= 0.60:
        reasons.append(
            f"Y-рандомизация: недопустимый AUC {y_random_auc} (нужно 0–0.60)"
        )
    return reasons
