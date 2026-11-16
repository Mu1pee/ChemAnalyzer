"""Admission boundaries and legacy-model bypass prevention."""
import numpy as np
import pytest

from app.model_quality import classification_reasons, held_out_quality
from app.ai_research_agent.evaluation import scaffold_split
from app.ai_research_agent.model_registry import Registry, Review, Approval
from app.ai_research_agent.security import write_json
from app.chemistry.qsar_core import quality_gate


@pytest.mark.parametrize("ba", [.60, .59, float("nan"), float("inf"), None])
def test_sixty_percent_is_strict_and_nonfinite_metrics_fail(ba):
    assert classification_reasons(dict(balanced_accuracy=ba, roc_auc=.8))


def test_qsar_cannot_pass_using_auc_alone_or_incomplete_oof():
    metrics = dict(roc_auc=.9, mcc=.4, balanced_accuracy=.60, n_evaluated=100)
    assert quality_gate(metrics, 50, 50, .5)
    metrics.update(balanced_accuracy=.71, n_evaluated=99)
    assert quality_gate(metrics, 50, 50, .5)
    metrics["n_evaluated"] = 100
    assert quality_gate(metrics, 50, 50, .5) == []
    assert quality_gate(metrics, 50, 50, None)


def evaluation():
    return dict(test=dict(balanced_accuracy=.72, roc_auc=.8, pr_auc=.7),
                baseline_test=dict(pr_auc=.5), beats_baseline=True,
                test_used_for_selection=False,
                support=dict(test=dict(molecules=40, scaffolds=5, negative=20, positive=20)))


@pytest.mark.parametrize("baseline", [None, {}, [], "invalid", 0.5, True,
                                     dict(pr_auc=.7), dict(pr_auc=.8)])
def test_classification_baseline_flag_cannot_replace_measured_improvement(baseline):
    report = evaluation()
    if baseline is None:
        report.pop("baseline_test")
    else:
        report["baseline_test"] = baseline
    result = held_out_quality("classification", report)
    assert not result["passed"]
    assert any("PR-AUC" in reason for reason in result["reasons"])


@pytest.mark.parametrize("which", ["test", "baseline_test"])
@pytest.mark.parametrize("bad", [None, True, "0.5", -.1, 1.1, float("nan"), float("inf")])
def test_classification_pr_auc_requires_finite_bounded_numeric_evidence(which, bad):
    report = evaluation()
    report[which]["pr_auc"] = bad
    assert not held_out_quality("classification", report)["passed"]


def test_classification_pr_auc_improvement_keeps_all_other_admission_requirements():
    report = evaluation()
    assert held_out_quality("classification", report)["passed"]
    report["beats_baseline"] = False
    assert not held_out_quality("classification", report)["passed"]
    report["beats_baseline"] = True
    report["test"]["balanced_accuracy"] = .60
    assert not held_out_quality("classification", report)["passed"]


def test_unproven_baseline_prevents_registry_review_activation_and_prediction(tmp_path, monkeypatch):
    registry = Registry(tmp_path)
    report = evaluation()
    report["baseline_test"]["pr_auc"] = .9
    metadata = dict(id="baseline-fixture", status="experimental", task=dict(kind="classification"),
                    evaluation=report)
    path = tmp_path / "models" / metadata["id"] / "metadata.json"
    write_json(path, metadata)
    monkeypatch.setattr(registry, "load", lambda *args: pytest.fail("Reject unsupported evidence before loading the artifact"))
    review = Review(reviewer="Software fixture", evidence="Baseline-admission regression fixture; no biological measurements.")
    with pytest.raises(ValueError, match="PR-AUC"):
        registry.review(metadata["id"], review)
    with pytest.raises(ValueError, match="PR-AUC"):
        registry.predict(metadata["id"], "CCO")
    metadata["status"] = "validated"
    write_json(path, metadata)
    with pytest.raises(ValueError, match="PR-AUC"):
        registry.approve(metadata["id"], Approval(**review.model_dump(), confirm_activation=True))


def test_regression_r2_is_separate_from_accuracy_and_needs_scaffold_support():
    report = evaluation()
    report.update(test=dict(r2=.70, mae=1.3), baseline_test=dict(mae=2.9))
    assert held_out_quality("regression", report)["passed"]
    report["support"]["test"]["scaffolds"] = 1
    assert not held_out_quality("regression", report)["passed"]
    report["support"]["test"]["scaffolds"] = 5
    report["test"]["r2"] = .60
    assert not held_out_quality("regression", report)["passed"]


def test_legacy_model_without_evidence_cannot_review_approve_or_predict(tmp_path):
    registry = Registry(tmp_path)
    metadata = dict(id="legacy", status="experimental", task=dict(kind="classification"),
                    evaluation=dict(beats_baseline=True, test=dict(balanced_accuracy=.99, roc_auc=.99)))
    path = tmp_path / "models" / "legacy" / "metadata.json"
    write_json(path, metadata)
    review = Review(reviewer="Software test", evidence="Technical fixture only; no scientific measurements.")
    with pytest.raises(ValueError, match="quality policy"):
        registry.review("legacy", review)
    with pytest.raises(ValueError, match="quality policy"):
        registry.predict("legacy", "CCO")
    metadata["status"] = "validated"
    write_json(path, metadata)
    with pytest.raises(ValueError, match="quality policy"):
        registry.approve("legacy", Approval(**review.model_dump(), confirm_activation=True))


def test_large_acyclic_group_does_not_leave_single_group_holdout():
    groups = np.array(["acyclic"] * 150 + [f"s{i}" for i in range(30) for _ in range(10)])
    splits = scaffold_split(np.zeros(len(groups)), groups, 42)
    seen = []
    for indices in splits:
        current = set(groups[indices])
        assert len(current) >= 3
        assert all(not current & other for other in seen)
        seen.append(current)
    assert sorted(np.concatenate(splits)) == list(range(len(groups)))
