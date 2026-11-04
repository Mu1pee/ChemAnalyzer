import numpy as np
import pytest

from training.train_specialized import ALGORITHMS, create_model


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_candidate_probability_contract(algorithm):
    # Synthetic fixture tests estimator API compatibility, not scientific quality.
    rng = np.random.default_rng(42)
    x = rng.integers(0, 2, size=(60, 16), dtype=np.uint8)
    y = x[:, 0]
    model = create_model(algorithm, 42)
    model.fit(x, y)
    probabilities = model.predict_proba(x[:5])
    assert list(model.classes_) == [0, 1]
    assert probabilities.shape == (5, 2)
    assert np.isfinite(probabilities).all()
    assert np.allclose(probabilities.sum(axis=1), 1)


def test_unknown_algorithm_is_rejected():
    with pytest.raises(ValueError):
        create_model("unknown", 42)
