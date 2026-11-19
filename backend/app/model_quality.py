"""Versioned admission criteria; a probability is never a quality metric."""
import math
import re

POLICY_VERSION = "2026-11-16"
MIN_BALANCED_ACCURACY = 0.60
SHA256 = re.compile(r"[0-9a-f]{64}")


def finite(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


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


def test_counts(evaluation):
    support = evaluation.get("support") if isinstance(evaluation, dict) else None
    support = support.get("test") if isinstance(support, dict) else None
    return support if isinstance(support, dict) else {}


def held_out_quality(kind, evaluation):
    """Recomputed at review, activation and inference, including legacy artifacts."""
    evaluation = evaluation if isinstance(evaluation, dict) else {}
    scores = evaluation.get("test")
    scores = scores if isinstance(scores, dict) else {}
    baseline = evaluation.get("baseline_test")
    baseline = baseline if isinstance(baseline, dict) else {}
    support = test_counts(evaluation)
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
        # The stored flag cannot replace the numerical comparison used by the
        # trainer. PR-AUC is average precision here, computed on the same test
        # partition for the selected classifier and its train-fitted baseline.
        pr_auc, baseline_pr_auc = scores.get("pr_auc"), baseline.get("pr_auc")
        if (not finite(pr_auc) or not finite(baseline_pr_auc)
                or not 0 <= baseline_pr_auc < pr_auc <= 1):
            reasons.append("Held-out PR-AUC must be finite, within [0, 1] and strictly better than the baseline")
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
        mae, baseline_mae = scores.get("mae"), baseline.get("mae")
        if not finite(mae) or not finite(baseline_mae) or not 0 <= mae < baseline_mae:
            reasons.append("Held-out MAE must be finite and better than the baseline")
    else:
        metric = None
        reasons.append("Unsupported prediction task")
    return dict(policy_version=POLICY_VERSION, passed=not reasons, metric=metric,
                value=scores.get(metric) if finite(scores.get(metric)) else None, threshold=0.60, strict=True,
                evidence="internal held-out scaffolds; no external validation", reasons=reasons)


def research_quality(kind, evaluation):
    """Check the full test and the exact subset on which the Lab serves values."""
    result = held_out_quality(kind, evaluation)
    if not isinstance(evaluation, dict) or "applicability_domain_test" not in evaluation:
        result["applicability_domain"] = {"status": "not_recorded"}
        return result

    covered = evaluation["applicability_domain_test"]
    domain = held_out_quality(kind, covered)
    accepted, whole = test_counts(covered), test_counts(evaluation)
    fields = ("molecules", "scaffolds")
    if kind == "classification":
        fields += ("negative", "positive")
    if not all(valid_count(accepted.get(key)) and valid_count(whole.get(key))
               and accepted[key] <= whole[key] for key in fields):
        domain["reasons"].append("Domain test counts must describe a subset of the held-out test")

    result["applicability_domain"] = dict(
        status="failed" if domain["reasons"] else "passed",
        metric=domain["metric"], value=domain["value"],
        molecules=accepted.get("molecules"), scaffolds=accepted.get("scaffolds"),
        total_molecules=whole.get("molecules"))
    result["reasons"].extend("Applicability domain: " + reason for reason in domain["reasons"])
    result["passed"] = not result["reasons"]
    return result


def registry_quality(kind, evaluation, external_evaluations, *, artifact_sha256, training_dataset_sha256):
    """Evaluate all curator-admitted independent tests of the same fitted artifact."""
    result = research_quality(kind, evaluation)
    if not isinstance(external_evaluations, list):
        result["reasons"].append("Reviewed external evaluations must be an array")
        result["passed"] = False
        return result
    if not external_evaluations:
        return result
    if not isinstance(training_dataset_sha256, str) or not SHA256.fullmatch(training_dataset_sha256):
        result["reasons"].append("Reviewed external evaluations require a development dataset SHA-256")
        result["passed"] = False
        return result

    seen = set()
    external = []
    for index, record in enumerate(external_evaluations, 1):
        if not isinstance(record, dict):
            result["reasons"].append(f"External test {index}: invalid evidence object")
            continue
        source = record.get("source")
        dataset = record.get("dataset_sha256")
        protocol = record.get("protocol")
        if (not isinstance(source, str) or not 3 <= len(source.strip()) <= 200
                or not isinstance(protocol, str) or not 10 <= len(protocol.strip()) <= 2000
                or not isinstance(dataset, str) or not SHA256.fullmatch(dataset)):
            result["reasons"].append(f"External test {index}: source, comparison protocol and dataset SHA-256 are required")
            continue
        source = source.strip()
        if dataset == training_dataset_sha256:
            result["reasons"].append(f"External test {index}: dataset SHA-256 matches the development dataset")
            continue
        if dataset in seen:
            result["reasons"].append(f"External test {index}: duplicate dataset SHA-256")
            continue
        seen.add(dataset)
        if (not isinstance(artifact_sha256, str) or not SHA256.fullmatch(artifact_sha256)
                or artifact_sha256 != record.get("artifact_sha256")):
            result["reasons"].append(f"External test {index}: evidence must identify the evaluated model artifact")
            continue
        if (record.get("independent_of_development") is not True
                or record.get("scope") not in ("whole_cohort", "applicability_domain")):
            result["reasons"].append(f"External test {index}: independent development separation and evaluation scope are required")
            continue
        quality = held_out_quality(kind, record.get("evaluation"))
        external.append(dict(source=source, dataset_sha256=dataset, scope=record["scope"],
                             metric=quality["metric"], value=quality["value"], passed=quality["passed"]))
        result["reasons"].extend(f"External test {index} ({source}): {reason}" for reason in quality["reasons"])

    result["external_tests"] = external
    result["evidence"] = "internal held-out scaffolds and reviewed external evidence"
    result["passed"] = not result["reasons"]
    return result
