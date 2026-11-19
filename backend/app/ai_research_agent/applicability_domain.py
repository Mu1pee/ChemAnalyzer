import numpy as np
from rdkit import DataStructs


_BIT_TEXT = bytes.maketrans(b"\x00\x01", b"01")


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


def membership_mask(domain, X):
    """Batch counterpart of assess; convert the training fingerprints only once."""
    descriptors = X[:, 1024:]
    candidates = np.flatnonzero(np.all(
        (descriptors >= domain["descriptor_min"]) & (descriptors <= domain["descriptor_max"]), axis=1))
    accepted = np.zeros(len(X), dtype=bool)
    if not len(candidates):
        return accepted

    def fingerprint(row):
        bits = row.astype(np.uint8).astype(bool)
        return DataStructs.CreateFromBitString(bits.tobytes().translate(_BIT_TEXT).decode("ascii"))

    training = [fingerprint(row) for row in domain["train_bits"]]
    for index in candidates:
        query = fingerprint(X[index, :1024])
        # assess reports zero similarity when both fingerprints are empty.
        similarity = max(DataStructs.BulkTanimotoSimilarity(query, training)) if query.GetNumOnBits() else 0.0
        accepted[index] = similarity >= domain["threshold"]
    return accepted
