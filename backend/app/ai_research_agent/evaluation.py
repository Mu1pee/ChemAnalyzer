import numpy as np
from sklearn.metrics import (mean_absolute_error, mean_squared_error, r2_score,
                            roc_auc_score, average_precision_score, f1_score,
                            precision_score, recall_score, balanced_accuracy_score)


def scaffold_split(y, groups, seed):
    if len(y) < 60 or len(np.unique(groups)) < 10:
        raise ValueError("Insufficient data: need 60 unique molecules and 10 scaffold groups")
    # Balance molecule counts, not group counts. One large acyclic group must
    # stay intact and can make exact target proportions impossible.
    # Assignment uses sizes only, never labels or model/test performance.
    unique, counts = np.unique(groups, return_counts=True)
    rng = np.random.default_rng(seed)
    order = sorted(rng.permutation(len(unique)), key=lambda i: -counts[i])
    targets, allocated, buckets = np.array([.64, .16, .20]) * len(y), np.zeros(3), [[], [], []]
    for i in order:
        partition = int(np.argmax(targets - allocated))
        indices = np.flatnonzero(groups == unique[i]).tolist()
        buckets[partition].extend(indices)
        allocated[partition] += len(indices)
    train, valid, test = (np.array(sorted(indices), dtype=int) for indices in buckets)
    if min(map(len, (train, valid, test))) < 10:
        raise ValueError("Scaffold split too small: need at least 10 molecules per partition")
    return train, valid, test


def metrics(model, X, y, kind):
    pred = model.predict(X)
    if kind == "regression":
        if len(y) < 2 or np.var(y) == 0:
            raise ValueError("Regression evaluation needs variable measurements")
        return dict(mae=float(mean_absolute_error(y, pred)), rmse=float(np.sqrt(mean_squared_error(y, pred))), r2=float(r2_score(y, pred)))
    if len(np.unique(y)) != 2:
        raise ValueError("Classification evaluation requires both classes")
    prob = model.predict_proba(X)[:, 1]
    return dict(roc_auc=float(roc_auc_score(y, prob)), pr_auc=float(average_precision_score(y, prob)),
                f1=float(f1_score(y, pred, zero_division=0)), precision=float(precision_score(y, pred, zero_division=0)),
                recall=float(recall_score(y, pred, zero_division=0)), balanced_accuracy=float(balanced_accuracy_score(y, pred)))
