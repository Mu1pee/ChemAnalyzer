"""Ядро QSAR на синтетических данных (RDKit не нужен)."""

import numpy as np
import pytest

pytest.importorskip("sklearn")

from app.chemistry import qsar_core as q  # noqa: E402


def make(n=1200, seed=1):
    rng = np.random.default_rng(seed)
    X = (rng.random((n, 2048)) < 0.08).astype(np.uint8)
    X[:, :10] = (rng.random((n, 10)) < 0.4).astype(np.uint8)
    score = X[:, :10].sum(1) + rng.normal(0, 0.5, n)
    y = (score > np.percentile(score, 65)).astype(int)
    return X, y, rng.integers(0, 250, n)


def test_cv_finds_signal_and_noise_is_rejected():
    X, y, g = make()
    m = q.cross_validate(X, y, g, n_estimators=80)
    # Порог — тот же, что у «ворот качества» приложения (MIN_AUC=0.75, MIN_MCC=0.25).
    assert m["roc_auc"] > 0.75 and m["mcc"] > 0.25
    assert q.quality_gate(m, int(y.sum()), int((1 - y).sum()), 0.5) == []

    rng = np.random.default_rng(2)
    Xn = (rng.random((len(y), 2048)) < 0.08).astype(np.uint8)
    yn = rng.integers(0, 2, len(y))
    mn = q.cross_validate(Xn, yn, g, n_estimators=80)
    assert 0.4 < mn["roc_auc"] < 0.6
    assert q.quality_gate(mn, int(yn.sum()), int((1 - yn).sum()), 0.5) != []


def test_y_randomization_near_half():
    X, y, g = make(800)
    assert 0.4 < q.y_randomization_auc(X, y, g) < 0.6


def test_max_tanimoto_matches_direct_computation():
    X, _, _ = make(300)
    train = q.pack_bits(X[:200])
    pop = q.popcounts(train)
    x = X[250]
    fast = q.max_tanimoto(q.pack_bits(x[None, :])[0], train, pop)
    a = x.astype(bool)
    best = max((a & r).sum() / (a | r).sum() for r in X[:200].astype(bool))
    assert abs(fast - best) < 1e-9
    assert abs(q.max_tanimoto(train[5], train, pop) - 1.0) < 1e-9


def test_domain_labels():
    assert q.domain_label(0.9) == "в области применимости"
    assert q.domain_label(0.4) == "на границе области"
    assert q.domain_label(0.1) == "вне области применимости"


def test_extremely_rare_class_does_not_crash():
    X, y, _ = make(300)
    y2 = np.zeros_like(y)
    y2[:2] = 1
    q.train_final(X, y2)
