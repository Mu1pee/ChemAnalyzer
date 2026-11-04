import numpy as np


def fit_domain(X):
    return dict(train_bits=X[:, :1024].astype(np.uint8),
                descriptor_min=X[:, 1024:].min(axis=0), descriptor_max=X[:, 1024:].max(axis=0),
                threshold=.35, method="max training Morgan Tanimoto >= 0.35 and train descriptor ranges; heuristic, not calibrated")


def assess(domain, x):
    train, bits = domain["train_bits"], x[:1024].astype(np.uint8)
    inter = np.logical_and(train, bits).sum(axis=1)
    union = np.logical_or(train, bits).sum(axis=1)
    sim = float(np.max(inter / np.maximum(union, 1)))
    within = bool(np.all(x[1024:] >= domain["descriptor_min"]) and np.all(x[1024:] <= domain["descriptor_max"]))
    return dict(max_similarity=sim, within_descriptor_ranges=within,
                in_domain=sim >= domain["threshold"] and within,
                warning="Similarity is not an activity probability; domain rule is heuristic. Outside-domain predictions are unreliable.")
