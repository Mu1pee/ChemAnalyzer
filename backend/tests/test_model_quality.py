"""Admission boundaries and legacy-model bypass prevention."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.model_quality import classification_reasons, held_out_quality, registry_quality, research_quality
from app.ai_research_agent.evaluation import scaffold_split
from app.ai_research_agent.model_registry import Registry, Review, Approval, ExternalEvaluation
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


@pytest.mark.parametrize("scope, passed, reason", [
    ({"molecules": 20, "scaffolds": 3}, True, None),
    ({"molecules": 20, "scaffolds": 2}, False, "3 distinct scaffold groups"),
    ({"molecules": 41, "scaffolds": 3}, False, "subset"),
])
def test_covered_regression_support_is_checked_separately(scope, passed, reason):
    report = dict(test=dict(r2=.729, mae=1.2), baseline_test=dict(mae=2),
                  test_used_for_selection=False, beats_baseline=True,
                  support=dict(test=dict(molecules=40, scaffolds=4)))
    assert research_quality("regression", report)["applicability_domain"]["status"] == "not_recorded"
    report["applicability_domain_test"] = report | dict(test=dict(r2=.762, mae=1), support=dict(test=scope))
    result = research_quality("regression", report)
    assert result["value"] == .729 and result["applicability_domain"]["value"] == .762
    assert result["passed"] is passed
    if reason:
        assert any(item.startswith("Applicability domain:") and reason in item for item in result["reasons"])


def external(source, dataset, **fields):
    return dict(source=source, dataset_sha256=dataset, artifact_sha256="a" * 64,
                protocol="Technical comparison protocol fixture", independent_of_development=True,
                scope="applicability_domain", evaluation=evaluation()) | fields


def test_reviewed_external_regression_failure_blocks_review_approval_and_prediction(tmp_path, monkeypatch):
    registry = Registry(tmp_path)

    def regression(r2):
        return dict(test=dict(r2=r2, mae=.7), baseline_test=dict(mae=1.3), beats_baseline=True,
                    test_used_for_selection=False, support=dict(test=dict(molecules=31, scaffolds=24)))

    good = external("Passing cohort", "b" * 64, evaluation=regression(.723))
    metadata = dict(id="external-regression-fixture", status="experimental", task=dict(kind="regression"),
                    artifact_sha256="a" * 64, dataset_sha256="d" * 64, evaluation=regression(.637),
                    external_evaluations=[good])
    path = tmp_path / "models" / metadata["id"] / "metadata.json"
    write_json(path, metadata)
    assert registry.metadata(metadata["id"])["quality"]["passed"]
    metadata["external_evaluations"].append(external("Conflicting cohort", "c" * 64, evaluation=regression(.344)))
    write_json(path, metadata)
    quality = registry.metadata(metadata["id"])["quality"]
    assert not quality["passed"] and quality["value"] == .637
    assert [entry["passed"] for entry in quality["external_tests"]] == [True, False]
    assert any("Conflicting cohort" in issue and "Held-out R2" in issue for issue in quality["reasons"])
    monkeypatch.setattr(registry, "load", lambda *args: pytest.fail("Reject conflicting evidence before loading"))
    review = Review(reviewer="Software fixture", evidence="Technical regression test for conflicting independent evidence.")
    with pytest.raises(ValueError, match="Conflicting cohort"):
        registry.review(metadata["id"], review)
    with pytest.raises(ValueError, match="Conflicting cohort"):
        registry.predict(metadata["id"], "CCO")
    metadata["status"] = "validated"
    write_json(path, metadata)
    with pytest.raises(ValueError, match="Conflicting cohort"):
        registry.approve(metadata["id"], Approval(**review.model_dump(), confirm_activation=True))


@pytest.mark.parametrize("reports, reason", [
    (None, "must be an array"),
    ([external("Wrong artifact", "b" * 64, artifact_sha256="c" * 64)], "evaluated model artifact"),
    ([external("Shared partition", "b" * 64, independent_of_development=False)], "development separation"),
    ([external("Duplicate A", "b" * 64), external("Duplicate B", "b" * 64)], "duplicate dataset"),
    ([external("Development set", "d" * 64)], "matches the development dataset"),
    ([external("Missing score", "b" * 64, evaluation={})], "PR-AUC"),
])
def test_registry_rejects_unbound_or_incomplete_external_classification_evidence(reports, reason):
    quality = registry_quality("classification", evaluation(), reports,
                               artifact_sha256="a" * 64, training_dataset_sha256="d" * 64)
    assert not quality["passed"]
    assert any(reason in item for item in quality["reasons"])


def test_external_report_import_persists_failure_and_retries_without_duplicates(tmp_path, monkeypatch):
    from app.ai_research_agent import api
    from app.main import app

    registry = Registry(tmp_path)
    meta = registry.register({}, dict(task=dict(kind="classification"), evaluation=evaluation(), dataset_sha256="d" * 64))
    monkeypatch.setenv("CHEMANALYZER_RESEARCH_ENABLED", "1")
    monkeypatch.setattr(api, "agent", lambda: SimpleNamespace(root=tmp_path))
    client = TestClient(app)
    path = f"/api/research/models/{meta['id']}/external-evaluation"
    report = external("Independent assay", "b" * 64, artifact_sha256=meta["artifact_sha256"])
    report["evaluation"].pop("beats_baseline")
    report["evaluation"]["test"]["balanced_accuracy"] = .58
    assert client.post(path, json=report | {"artifact_sha256": "a" * 64}).status_code == 400
    first = client.post(path, json=report)
    assert first.status_code == 200
    assert first.json()["quality"]["external_tests"][0]["value"] == .58
    assert first.json()["quality"]["passed"] is False
    assert client.post(path, json=report).status_code == 200
    assert client.post(path, json=report | {"source": "Changed report"}).status_code == 400
    assert len(Registry(tmp_path).metadata(meta["id"])["external_evaluations"]) == 1
    prediction = client.post(f"/api/research/models/{meta['id']}/predict", json={"smiles": "CCO"})
    assert prediction.status_code == 400 and "Independent assay" in prediction.json()["detail"]


def test_concurrent_reports_to_one_model_keep_both_sources(tmp_path):
    meta = Registry(tmp_path).register({}, dict(task=dict(kind="classification"), evaluation=evaluation(), dataset_sha256="d" * 64))
    reports = []
    for source, dataset in (("Source A", "b" * 64), ("Source B", "c" * 64)):
        report = external(source, dataset, artifact_sha256=meta["artifact_sha256"])
        report["evaluation"].pop("beats_baseline")
        reports.append(ExternalEvaluation.model_validate(report))
    with ThreadPoolExecutor(max_workers=2) as workers:
        list(workers.map(lambda report: Registry(tmp_path).record_external_evaluation(meta["id"], report), reports))
    saved = Registry(tmp_path).metadata(meta["id"])
    assert {row["source"] for row in saved["quality"]["external_tests"]} == {"Source A", "Source B"}
    assert saved["quality"]["passed"]


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
