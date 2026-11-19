"""Release evidence must apply to old profiles without replacing user records."""

import hashlib
import json

import pytest

from app import served_holdouts
from app.ai_research_agent.model_registry import Registry
from app.ai_research_agent.security import write_json


@pytest.fixture
def bundled_model(monkeypatch):
    held_out = dict(test=dict(r2=.73, mae=1.2), baseline_test=dict(mae=2.9),
                    support={"test": dict(molecules=40, scaffolds=3)},
                    test_used_for_selection=False, beats_baseline=True)
    split = dict(train=[0, 1], validation=[2], test=[3])
    task = dict(endpoint="technical-fixture", context="Software regression",
                kind="regression", domain="qsar", units="kcal/mol")
    meta = dict(id="release-probe", artifact_sha256="a" * 64, dataset_sha256="b" * 64,
                task=task, evaluation=held_out | {"split": split}, status="approved",
                approval={"reviewer": "Existing reviewer"})
    record = dict(artifact_sha256=meta["artifact_sha256"], dataset_sha256=meta["dataset_sha256"],
                  split_sha256=hashlib.sha256(json.dumps(split, sort_keys=True, separators=(",", ":"))
                                             .encode("ascii")).hexdigest(), task=dict(task),
                  evaluation=held_out | {"support": {"test": dict(molecules=30, scaffolds=2)}})
    monkeypatch.setattr(served_holdouts, "_manifest", lambda: {
        "registry": {meta["id"]: record},
        "qsar": {"target-fixture": record | dict(target_id="CHEMBL1", serving_threshold=.3)},
    })
    return meta


def test_released_evidence_blocks_existing_approved_model_without_overwriting_metadata(tmp_path, bundled_model):
    registry = Registry(tmp_path)
    identifier = bundled_model["id"]
    path = registry.root / identifier / "metadata.json"
    write_json(path, bundled_model)
    before = path.read_bytes()
    model, = registry.list()
    assert model["status"] == "approved" and model["approval"] == bundled_model["approval"]
    assert model["quality"]["applicability_domain"]["scaffolds"] == 2
    assert not model["quality"]["passed"]
    with pytest.raises(ValueError, match="Applicability domain"):
        registry.predict(identifier, "CCO")
    assert before == path.read_bytes()


@pytest.mark.parametrize("changed", ["artifact_sha256", "dataset_sha256", "split", "task"])
def test_known_holdout_cannot_be_applied_to_another_experiment(bundled_model, changed):
    if changed == "split":
        bundled_model["evaluation"]["split"]["test"] = [4]
    elif changed == "task":
        bundled_model["task"]["context"] = "A different experiment"
    else:
        bundled_model[changed] = "c" * 64
    with pytest.raises(ValueError, match="Shipped holdout evidence does not match"):
        served_holdouts.reviewed_evaluation(bundled_model, "registry")


def test_qsar_evidence_matches_the_serving_boundary(bundled_model):
    model = bundled_model | dict(model_id="target-fixture", target_id="CHEMBL1")
    assert "applicability_domain_test" in served_holdouts.reviewed_evaluation(
        model, "qsar", serving_threshold=.3)
    with pytest.raises(ValueError, match="serving threshold"):
        served_holdouts.reviewed_evaluation(model, "qsar", serving_threshold=.5)
