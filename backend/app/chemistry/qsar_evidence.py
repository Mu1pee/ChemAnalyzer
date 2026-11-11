"""Admission for retrospectively held-out human IC50 QSAR models."""
import numpy as np
from app.model_quality import classification_reasons, finite, held_out_quality, valid_count

FEATURE_CONFIG = dict(morgan_bits=2048, morgan_radius=2, chirality=False,
                      standardization="single fragment; uncharge; canonical isomeric SMILES",
                      grouping="nonchiral Murcko scaffold; all acyclic structures share ACYCLIC")


def describe_model(model, train_groups=None):
    """Inspect the fitted object, not only its declared training parameters."""
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    if isinstance(model, CalibratedClassifierCV) and isinstance(model.estimator, RandomForestClassifier):
        if (model.method != "sigmoid" or model.ensemble is not False or not isinstance(model.cv, list)
                or len(model.cv) != 3 or len(model.calibrated_classifiers_) != 1):
            raise ValueError("Expected train-only three-group-fold sigmoid calibration")
        fitted = model.calibrated_classifiers_[0].estimator
        if len(fitted.estimators_) != 200 or model.estimator.get_params() != fitted.get_params():
            raise ValueError("Fitted and declared forest configurations differ")
        if train_groups is None:
            raise ValueError("Calibration scaffold evidence missing")
        train_groups = np.asarray(train_groups)
        seen = []
        for left, right in model.cv:
            if (set(left) & set(right) or set(left) | set(right) != set(range(len(train_groups)))
                    or set(train_groups[left]) & set(train_groups[right])):
                raise ValueError("Calibration folds are not disjoint by scaffold")
            seen.extend(right.tolist())
        if sorted(seen) != list(range(len(train_groups))):
            raise ValueError("Calibration out-of-fold coverage is incomplete")
        return dict(algorithm="random_forest", forest_parameters=fitted.get_params(deep=False),
                    calibration="sigmoid; train-only stratified scaffold 3-fold; ensemble=False")
    if isinstance(model, Pipeline) and len(model.steps) == 2:
        scaler, estimator = (step[1] for step in model.steps)
        if isinstance(scaler, StandardScaler) and isinstance(estimator, LogisticRegression):
            return dict(algorithm="logistic_regression", parameters=estimator.get_params(deep=False),
                        scaler=scaler.get_params(deep=False), calibration="none; raw classifier score")
    if isinstance(model, GradientBoostingClassifier):
        return dict(algorithm="gradient_boosting", parameters=model.get_params(deep=False), calibration="none; raw classifier score")
    raise ValueError("Unsupported or incompatible QSAR estimator")


def admission(meta):
    meta = meta if isinstance(meta, dict) else {}
    evaluation = meta.get("evaluation")
    result = held_out_quality("classification", evaluation)
    scores = meta.get("metrics")
    result["reasons"] += classification_reasons(scores, min_auc=.75, min_mcc=.25)
    provenance = meta.get("provenance")
    provenance = provenance if isinstance(provenance, dict) else {}
    if (meta.get("schema_version") != 2 or meta.get("feature_config") != FEATURE_CONFIG
            or provenance.get("source") != "ChEMBL" or provenance.get("target_id") != meta.get("target_id")
            or provenance.get("organism") != "Homo sapiens" or provenance.get("endpoint") != "IC50"
            or provenance.get("units") != "nM" or provenance.get("license") != "CC-BY-SA-3.0"
            or not provenance.get("version")):
        result["reasons"].append("Traceable schema-2 human IC50 source and feature contract required; revalidation of legacy artifacts is required")
    evaluation = evaluation if isinstance(evaluation, dict) else {}
    support = evaluation.get("support")
    support = support if isinstance(support, dict) else {}
    seen = set()
    split = evaluation.get("split")
    total = meta.get("n_total")
    complete = valid_count(total, 60) and total <= 10000 and isinstance(split, dict)
    for name in ("train", "validation", "test"):
        indices = split.get(name) if isinstance(split, dict) else None
        counts = support.get(name)
        if not isinstance(indices, list) or not isinstance(counts, dict):
            complete = False
            continue
        minimum = 10 if name == "validation" else 30
        if (not valid_count(counts.get("positive"), minimum) or not valid_count(counts.get("negative"), minimum)
                or counts["positive"] + counts["negative"] != len(indices)
                or counts.get("molecules") != len(indices) or not valid_count(counts.get("scaffolds"), 3)
                or counts["scaffolds"] > len(indices)
                or any(not isinstance(index, int) or isinstance(index, bool) or index < 0 for index in indices)):
            complete = False
            continue
        current = set(indices)
        if current & seen or len(current) != len(indices):
            complete = False
        seen.update(current)
    if not complete or seen != set(range(int(total))):
        result["reasons"].append("Complete disjoint train/validation/test indices and class support must be documented")
    train = support.get("train", {})
    test = support.get("test", {})
    if (not isinstance(train, dict) or not isinstance(test, dict) or scores != evaluation.get("test")
            or train.get("molecules") != meta.get("n_train") or train.get("positive") != meta.get("n_active")
            or train.get("negative") != meta.get("n_inactive") or test.get("molecules") != meta.get("n_test")):
        result["reasons"].append("Served metrics and fitted support must match the held-out experiment")
    null = evaluation.get("y_randomization")
    if (not isinstance(null, dict) or null.get("partition") != "train_only" or not finite(null.get("roc_auc"))
            or not 0 <= null["roc_auc"] <= .60 or null.get("used_for_selection") is not False):
        result["reasons"].append("Train-only label randomization ROC-AUC must be documented and at most 0.60")
    if meta.get("procedure") != evaluation.get("procedure") or not isinstance(meta.get("procedure"), dict):
        result["reasons"].append("The exact evaluated fitting procedure must be documented")
    result.update(passed=not result["reasons"], evidence="retrospective internal held-out scaffolds from a previously studied panel; no external validation")
    return result
