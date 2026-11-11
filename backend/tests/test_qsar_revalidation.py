"""Procedure/curation software fixtures only, never scientific training evidence."""
import copy

import numpy as np
import pytest

from app.chemistry import qsar_core as core
from app.chemistry.qsar_evidence import admission, describe_model
from training import revalidate_qsar as trainer


def record(**changes):
    return dict(dict(assay_chembl_id="fixture", target_chembl_id="CHEMBL230", target_organism="Homo sapiens",
                     assay_type="B", standard_type="IC50", standard_units="nM", standard_relation="=",
                     standard_value="1000", pchembl_value="6.00", canonical_smiles="CCO", activity_id=1,
                     data_validity_comment=None, potential_duplicate=0), **changes)


def test_measured_units_define_cutoff_not_rounded_pchembl():
    rows, rejected = trainer.curate([record(), record(activity_id=2, standard_value="1001", canonical_smiles="CCN")], {"fixture"})
    assert not rejected
    labels = {row["smiles"]: row["label"] for row in rows}
    assert labels == {"CCN": 0, "CCO": 1}
    assert {row["scaffold"] for row in rows} == {"ACYCLIC"}


@pytest.mark.parametrize("changes", [dict(standard_value="nan"), dict(standard_value="-1"), dict(standard_value="0"),
                                     dict(pchembl_value="9"), dict(canonical_smiles="CCO.Cl"), dict(standard_relation="<"),
                                     dict(target_organism="Mus musculus"), dict(potential_duplicate=1)])
def test_unusable_or_incompatible_experimental_rows_excluded(changes):
    rows, rejected = trainer.curate([record(**changes)], {"fixture"})
    assert not rows and sum(rejected.values()) == 1


def test_conflicting_parent_labels_never_averaged_across_cutoff():
    rows, rejected = trainer.curate([record(), record(activity_id=2, standard_value="10000", pchembl_value="5")], {"fixture"})
    assert not rows and rejected["conflicting_compound"] == 1


def test_unrounded_auc_cannot_pass_a_rounded_boundary():
    # Regression safeguard: retaining full precision avoids rounding .74996 to .75.
    from app.model_quality import classification_reasons
    assert classification_reasons(dict(roc_auc=.74996, balanced_accuracy=.7, mcc=.3), min_auc=.75, min_mcc=.25)


def test_cv_and_final_share_default_forest_configuration(monkeypatch):
    seen = []
    class Estimator:
        def predict_proba(self, X):
            return np.tile([.4, .6], (len(X), 1))
    monkeypatch.setattr(core, "fit_model", lambda X, y, n, seed, groups=None: (seen.append(n) or Estimator()))
    X = np.zeros((120, 8))
    y = np.arange(120) % 2
    groups = np.arange(120)
    core.cross_validate(X, y, groups, n_splits=3)
    core.train_final(X, y)
    assert seen == [200] * 4


def test_calibration_is_grouped_and_described_from_actual_fitted_object():
    X = np.zeros((90, 2048), dtype=np.uint8)
    y = np.arange(90) % 2
    X[:, 0] = y
    groups = np.repeat(np.arange(30), 3)
    model = core.fit_model(X, y, 200, 42, groups)
    description = describe_model(model, groups)
    assert description["forest_parameters"]["n_estimators"] == 200
    assert "scaffold" in description["calibration"]
    for left, right in model.cv:
        assert not set(groups[left]) & set(groups[right])
    model.calibrated_classifiers_[0].estimator.estimators_.pop()
    with pytest.raises(ValueError, match="configurations differ"):
        describe_model(model, groups)


def experiment_fixture(monkeypatch):
    rows = [dict(smiles=str(i), label=i % 2, scaffold=f"software_fixture_{i}") for i in range(400)]
    monkeypatch.setattr(trainer.fp, "mol_from_smiles", lambda text: int(text))
    monkeypatch.setattr(trainer.fp, "fingerprint_array", lambda i: np.array([i % 256, i // 256, i % 2] + [0]*2045, dtype=np.uint8))
    fits = []
    class Estimator:
        classes_ = np.array([0, 1])
        def predict(self, X):
            return X[:, 2].astype(int)
        def predict_proba(self, X):
            p = np.where(self.predict(X) == 1, .9, .1)
            return np.column_stack((1-p, p))
    def fit(name, X, y, groups, seed=42):
        estimator = Estimator()
        estimator.indices = (X[:, 0].astype(int)+256*X[:, 1].astype(int)).tolist()
        fits.append(estimator)
        return estimator
    monkeypatch.setattr(trainer, "fit", fit)
    monkeypatch.setattr(trainer, "describe_model", lambda *args: dict(algorithm="random_forest", software_fixture=True))
    return rows, fits


def test_selection_and_null_check_never_fit_test_rows_or_refit_winner(monkeypatch):
    rows, fits = experiment_fixture(monkeypatch)
    model, report, reason, *_ = trainer.experiment(rows)
    assert reason is None and model is fits[0] and len(fits) == 6
    train = set(report["split"]["train"])
    assert all(set(item.indices) == train for item in fits[:3])
    assert all(set(item.indices) <= train for item in fits[3:])
    assert report["test_used_for_selection"] is False and report["y_randomization"]["partition"] == "train_only"
    assert report["test"]["balanced_accuracy"] == 1


def test_bad_test_does_not_choose_replacement_candidate(monkeypatch):
    rows, fits = experiment_fixture(monkeypatch)
    _, _, test = trainer.scaffold_split(np.array([row["label"] for row in rows]), np.array([row["scaffold"] for row in rows]), 42)
    for index in test:
        rows[index]["label"] = 1-rows[index]["label"]
    model, report, reason, *_ = trainer.experiment(rows)
    assert model is fits[0] and len(fits) == 6 and report["selected"] == "random_forest"
    assert report["test"]["balanced_accuracy"] == 0 and report["test_used_for_selection"] is False


def test_legacy_cv_score_does_not_qualify_the_deployed_model():
    assert not admission(dict(metrics=dict(roc_auc=.99, balanced_accuracy=.99, mcc=.99), n_active=100, n_inactive=100))["passed"]
