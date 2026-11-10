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
    return dict(test=dict(balanced_accuracy=.72, roc_auc=.8), beats_baseline=True,
                test_used_for_selection=False,
                support=dict(test=dict(molecules=40, scaffolds=5, negative=20, positive=20)))


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
