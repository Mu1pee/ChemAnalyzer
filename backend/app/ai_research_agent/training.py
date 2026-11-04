import numpy as np
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from .evaluation import metrics, scaffold_split


def train(X, y, groups, task, checkpoint=lambda stage: None):
    if task.domain == "antidote_catalog":
        raise ValueError("Antidote tasks are catalog/report only; training is not authorized")
    if not np.isfinite(X).all() or not np.isfinite(y).all():
        raise ValueError("Non-finite training values")
    if task.kind == "classification" and (set(y) != {0, 1} or min(np.bincount(y.astype(int))) < 30):
        raise ValueError("Binary labels 0/1 and at least 30 compounds per class required")
    tr, va, te = scaffold_split(y, groups, task.seed)
    if task.kind == "classification":
        for indices in (tr, va, te):
            if len(np.unique(y[indices])) != 2 or min(np.bincount(y[indices].astype(int))) < 3:
                raise ValueError("Insufficient class support in scaffold partitions")
    folds = list(GroupKFold(n_splits=3).split(X[tr], y[tr], groups[tr]))
    if task.kind == "classification" and any(len(np.unique(y[tr][ix])) != 2 for pair in folds for ix in pair):
        raise ValueError("Insufficient class support in scaffold CV")
    seed = task.seed
    if task.kind == "regression":
        candidates = [
            ("random_forest", RandomForestRegressor(n_estimators=100, n_jobs=1, random_state=seed), {"min_samples_leaf": [1, 3]}),
            ("ridge", make_pipeline(StandardScaler(), Ridge()), {"ridge__alpha": [1., 10.]}),
            ("gradient_boosting", GradientBoostingRegressor(n_estimators=80, random_state=seed), {"max_depth": [2, 3]}),
        ]
        baseline, scoring, selection = DummyRegressor(), "neg_mean_absolute_error", "mae"
    else:
        candidates = [
            ("random_forest", RandomForestClassifier(n_estimators=100, n_jobs=1, random_state=seed, class_weight="balanced"), {"min_samples_leaf": [1, 3]}),
            ("logistic_regression", make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, random_state=seed, class_weight="balanced")), {"logisticregression__C": [.1, 1.]}),
            ("gradient_boosting", GradientBoostingClassifier(n_estimators=80, random_state=seed), {"max_depth": [2, 3]}),
        ]
        baseline, scoring, selection = DummyClassifier(strategy="prior"), "average_precision", "pr_auc"
    results, fitted = [], []
    with threadpool_limits(limits=1):
        for name, estimator, parameters in candidates:
            checkpoint("training:" + name)
            search = GridSearchCV(estimator, parameters, scoring=scoring, cv=folds, n_jobs=1, error_score="raise")
            search.fit(X[tr], y[tr])
            valid = metrics(search.best_estimator_, X[va], y[va], task.kind)
            results.append(dict(algorithm=name, parameters=search.best_params_, cv_score=float(search.best_score_), validation=valid))
            fitted.append(search.best_estimator_)
        scores = [r["validation"][selection] for r in results]
        winner = int(np.argmin(scores) if task.kind == "regression" else np.argmax(scores))
        checkpoint("evaluating:held_out_test")
        # The test set is evaluated only after all candidate/parameter selection.
        model = fitted[winner]
        baseline.fit(X[tr], y[tr])
        test_metrics = metrics(model, X[te], y[te], task.kind)
        baseline_metrics = metrics(baseline, X[te], y[te], task.kind)
    better = (test_metrics[selection] < baseline_metrics[selection] if task.kind == "regression"
              else test_metrics[selection] > baseline_metrics[selection])
    report = dict(candidates=results, selected=results[winner]["algorithm"], test=test_metrics,
                  baseline_test=baseline_metrics, beats_baseline=bool(better),
                  split={"train": tr.tolist(), "validation": va.tolist(), "test": te.tolist()},
                  split_method="scaffold groups; acyclic molecules share one group; train-only 3-fold CV",
                  scientific_status="experimental; no external validation", test_used_for_selection=False)
    return model, X[tr], report
