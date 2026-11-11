"""Versioned admission criteria; a probability is never a quality metric."""
import math

POLICY_VERSION = "2026-11-11"
MIN_BALANCED_ACCURACY = 0.60


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def valid_count(value, minimum=0):
    return finite(value) and value >= minimum and value == int(value)


def classification_reasons(metrics, min_auc=0.70, min_mcc=None):
    metrics = metrics if isinstance(metrics, dict) else {}
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
    evaluation = evaluation if isinstance(evaluation, dict) else {}
    scores = evaluation.get("test")
    scores = scores if isinstance(scores, dict) else {}
    support = evaluation.get("support")
    support = support.get("test") if isinstance(support, dict) else None
    support = support if isinstance(support, dict) else {}
    reasons = []
    if evaluation.get("test_used_for_selection") is not False:
        reasons.append("A test set excluded from model selection must be documented")
    if evaluation.get("beats_baseline") is not True:
        reasons.append("Model must beat the held-out baseline")
    molecules, scaffolds = support.get("molecules"), support.get("scaffolds")
    if (not valid_count(molecules, 20) or not valid_count(scaffolds, 3)
            or scaffolds > molecules):
        reasons.append("Held-out test needs at least 20 molecules and 3 distinct scaffold groups")
    if kind == "classification":
        metric = "balanced_accuracy"
        reasons += classification_reasons(scores)
        negative, positive = support.get("negative"), support.get("positive")
        if not valid_count(negative, 10) or not valid_count(positive, 10):
            reasons.append("Held-out test needs at least 10 compounds of each class")
        elif negative + positive != molecules:
            reasons.append("Held-out class counts must equal the molecule count")
    elif kind == "regression":
        metric = "r2"
        value = scores.get(metric)
        if not finite(value) or not 0.60 < value <= 1:
            reasons.append("Held-out R2 must be finite and strictly greater than 0.60; R2 is not percent accuracy")
        baseline = evaluation.get("baseline_test")
        baseline = baseline if isinstance(baseline, dict) else {}
        mae, baseline_mae = scores.get("mae"), baseline.get("mae")
        if not finite(mae) or not finite(baseline_mae) or not 0 <= mae < baseline_mae:
            reasons.append("Held-out MAE must be finite and better than the baseline")
    else:
        metric = None
        reasons.append("Unsupported prediction task")
    return dict(policy_version=POLICY_VERSION, passed=not reasons, metric=metric,
                value=scores.get(metric) if finite(scores.get(metric)) else None, threshold=0.60, strict=True,
                evidence="internal held-out scaffolds; no external validation", reasons=reasons)
