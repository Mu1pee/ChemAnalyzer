"""Versioned admission criteria; a probability is never a quality metric."""
import math

POLICY_VERSION = "2026-11-10"
MIN_BALANCED_ACCURACY = 0.60


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def classification_reasons(metrics, min_auc=0.70, min_mcc=None):
    metrics = metrics or {}
    reasons = []
    ba = metrics.get("balanced_accuracy")
    if not finite(ba) or not MIN_BALANCED_ACCURACY < ba <= 1:
        reasons.append("Balanced accuracy must be finite and strictly greater than 0.60")
    auc = metrics.get("roc_auc")
    if not finite(auc) or not min_auc <= auc <= 1:
        reasons.append(f"ROC-AUC must be finite and at least {min_auc}")
    if min_mcc is not None:
        mcc = metrics.get("mcc")
        if not finite(mcc) or not min_mcc <= mcc <= 1:
            reasons.append(f"MCC must be finite and at least {min_mcc}")
    return reasons


def held_out_quality(kind, evaluation):
    """Recomputed at review, activation and inference, including legacy artifacts."""
    evaluation = evaluation or {}
    scores = evaluation.get("test") or {}
    support = (evaluation.get("support") or {}).get("test") or {}
    reasons = []
    if evaluation.get("test_used_for_selection") is not False:
        reasons.append("A test set excluded from model selection must be documented")
    if evaluation.get("beats_baseline") is not True:
        reasons.append("Model must beat the held-out baseline")
    if support.get("molecules", 0) < 20 or support.get("scaffolds", 0) < 3:
        reasons.append("Held-out test needs at least 20 molecules and 3 distinct scaffold groups")
    if kind == "classification":
        metric = "balanced_accuracy"
        reasons += classification_reasons(scores)
        if min(support.get("negative", 0), support.get("positive", 0)) < 10:
            reasons.append("Held-out test needs at least 10 compounds of each class")
    elif kind == "regression":
        metric = "r2"
        value = scores.get(metric)
        if not finite(value) or not 0.60 < value <= 1:
            reasons.append("Held-out R2 must be finite and strictly greater than 0.60; R2 is not percent accuracy")
        mae, baseline_mae = scores.get("mae"), (evaluation.get("baseline_test") or {}).get("mae")
        if not finite(mae) or not finite(baseline_mae) or not 0 <= mae < baseline_mae:
            reasons.append("Held-out MAE must be finite and better than the baseline")
    else:
        metric = None
        reasons.append("Unsupported prediction task")
    return dict(policy_version=POLICY_VERSION, passed=not reasons, metric=metric,
                value=scores.get(metric), threshold=0.60, strict=True,
                evidence="internal held-out scaffolds; no external validation", reasons=reasons)
