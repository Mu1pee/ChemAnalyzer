"""Release-owned holdout evidence for previously shipped models."""

from functools import lru_cache
import hashlib
import json
from pathlib import Path


@lru_cache(maxsize=1)
def _manifest():
    return json.loads(Path(__file__).with_name("served_holdouts.json").read_text(encoding="utf-8"))


def reviewed_evaluation(meta, family, *, serving_threshold=None):
    """Overlay reviewed evidence while keeping user metadata and weights intact."""
    identifier = meta.get("id") if family == "registry" else meta.get("model_id")
    if not isinstance(identifier, str):
        return meta.get("evaluation")
    record = _manifest()[family].get(identifier)
    evaluation = meta.get("evaluation")
    if record is None:
        return evaluation

    split = evaluation.get("split") if isinstance(evaluation, dict) else None
    split_bytes = json.dumps(split, sort_keys=True, separators=(",", ":")).encode("ascii")
    if (meta.get("artifact_sha256") != record["artifact_sha256"]
            or meta.get("dataset_sha256") != record["dataset_sha256"]
            or hashlib.sha256(split_bytes).hexdigest() != record["split_sha256"]):
        raise ValueError("Shipped holdout evidence does not match the model, dataset and test split")
    if family == "registry":
        task = meta.get("task")
        if not isinstance(task, dict) or any(task.get(key) != value for key, value in record["task"].items()):
            raise ValueError("Shipped holdout evidence does not match the research task")
    elif meta.get("target_id") != record["target_id"] or serving_threshold != record["serving_threshold"]:
        raise ValueError("Shipped holdout evidence does not match the QSAR target and serving threshold")
    return evaluation | {"applicability_domain_test": record["evaluation"]}
