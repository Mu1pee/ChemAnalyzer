import json
import logging
from threading import Lock
from typing import Literal
from uuid import uuid4

import joblib
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat
from app.model_quality import held_out_quality, registry_quality

from .applicability_domain import assess
from .molecular_features import molecule, vector
from .root_protocol import root_metadata_reasons
from .security import checksum, read_json, safe_child, utcnow, write_json

logger = logging.getLogger(__name__)
TASK_FIELDS = ("endpoint", "context", "kind", "domain", "units")
PREDICTABLE_STATES = ("experimental", "validated", "approved")
_metadata_lock = Lock()


def task_matches(meta, expected):
    task = meta.get("task") if isinstance(meta, dict) else None
    return (isinstance(task, dict) and isinstance(expected, dict)
            and all(isinstance(expected.get(field), str) and bool(expected[field])
                    and task.get(field) == expected[field] for field in TASK_FIELDS))


def select_task_model(models, expected):
    """Same scientific contract and selection for catalog and inference.

    Only human approval and recency affect selection; test scores never do.
    Registry.list() recomputes quality before these records are considered.
    """
    candidates = [meta for meta in models if meta.get("status") in PREDICTABLE_STATES
                  and task_matches(meta, expected)]
    qualified = [meta for meta in candidates if meta.get("quality", {}).get("passed") is True]
    selected = max(qualified, key=lambda m: (m["status"] == "approved", m.get("trained_at", ""), m["id"])) if qualified else None
    return candidates, selected


class Review(BaseModel):
    reviewer: str = Field(min_length=3, max_length=120)
    evidence: str = Field(min_length=30, max_length=4000)


class Approval(Review):
    confirm_activation: bool = False


class ExternalSupport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    molecules: int = Field(ge=20)
    scaffolds: int = Field(ge=3)
    negative: int | None = Field(default=None, ge=10)
    positive: int | None = Field(default=None, ge=10)


class ExternalResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    test: dict[str, FiniteFloat] = Field(min_length=1, max_length=16)
    baseline_test: dict[str, FiniteFloat] = Field(min_length=1, max_length=16)
    support: dict[Literal["test"], ExternalSupport] = Field(min_length=1, max_length=1)
    test_used_for_selection: Literal[False]


class ExternalEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    source: str = Field(min_length=3, max_length=200)
    protocol: str = Field(min_length=10, max_length=2000)
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    independent_of_development: Literal[True]
    scope: Literal["whole_cohort", "applicability_domain"]
    evaluation: ExternalResult


class Registry:
    def __init__(self, root):
        self.root = root / "models"

    def active_path(self, endpoint, context):
        # Encode the pair unambiguously: ("ab", "c") and ("a", "bc")
        # must never select the same scientific endpoint.
        key = checksum(json.dumps([endpoint, context], ensure_ascii=False).encode("utf-8"))
        return self.root / ("active_" + key + ".json")

    def register(self, bundle, meta):
        identifier = uuid4().hex
        folder = safe_child(self.root, identifier)
        folder.mkdir(parents=True)
        joblib.dump(bundle, folder / "model.joblib", compress=3)
        meta = dict(meta, id=identifier, version=identifier, status="experimental", trained_at=utcnow(),
                    artifact_sha256=checksum((folder / "model.joblib").read_bytes()))
        write_json(folder / "metadata.json", meta)
        return meta

    def list(self):
        models = []
        for path in sorted(self.root.glob("*/metadata.json")):
            identifier = path.parent.name
            try:
                models.append(self.metadata(identifier))
            except (ValueError, KeyError, TypeError, OSError) as error:
                # Keep the damaged record visible, without exposing untrusted
                # contents or preventing other endpoints from using their models.
                logger.warning("Excluded damaged research model %s (%s)", identifier, type(error).__name__)
                quality = held_out_quality(None, None)
                quality["reasons"] = ["Model metadata are unreadable or invalid; repair from a verified backup"]
                models.append(dict(id=identifier, status="invalid", task=dict(name="Повреждённая запись модели"),
                                   evaluation={}, quality=quality))
        return models

    def metadata(self, identifier):
        meta = read_json(safe_child(self.root, identifier) / "metadata.json")
        if (not isinstance(meta, dict) or meta.get("id") != identifier
                or meta.get("status") not in ("experimental", "validated", "approved", "archived")
                or not isinstance(meta.get("task"), dict)
                or meta["task"].get("kind") not in ("classification", "regression")
                or not isinstance(meta.get("trained_at", ""), str)):
            raise ValueError("Invalid model metadata")
        # Python's JSON reader accepts non-standard NaN/Infinity. Such records
        # cannot be served as JSON and must never disable the whole registry.
        json.dumps(meta, allow_nan=False)
        meta["quality"] = registry_quality(
            meta["task"]["kind"], meta.get("evaluation"), meta.get("external_evaluations", []),
            artifact_sha256=meta.get("artifact_sha256"), training_dataset_sha256=meta.get("dataset_sha256"),
        )
        meta["quality"]["reasons"] += root_metadata_reasons(meta)
        meta["quality"]["passed"] = not meta["quality"]["reasons"]
        return meta

    def require_quality(self, meta):
        if not meta["quality"]["passed"]:
            raise ValueError("Model failed quality policy: " + "; ".join(meta["quality"]["reasons"]))

    def verify_artifact(self, identifier):
        folder = safe_child(self.root, identifier)
        meta = self.metadata(identifier)
        path = folder / "model.joblib"
        if checksum(path.read_bytes()) != meta["artifact_sha256"]:
            raise ValueError("Model checksum mismatch")
        return meta

    def load(self, identifier):
        self.verify_artifact(identifier)
        path = safe_child(self.root, identifier) / "model.joblib"
        # Only agent-generated local artifacts; arbitrary uploaded pickle is never accepted.
        return joblib.load(path)

    def record_external_evaluation(self, identifier, report: ExternalEvaluation):
        with _metadata_lock:
            meta = self.verify_artifact(identifier)
            if report.artifact_sha256 != meta["artifact_sha256"] or report.dataset_sha256 == meta.get("dataset_sha256"):
                raise ValueError("External evidence must identify this model and a different dataset")
            packet = report.model_dump(exclude_none=True)
            result = packet["evaluation"]
            test, baseline = result["test"], result["baseline_test"]
            support = result["support"]["test"]
            if support["scaffolds"] > support["molecules"]:
                raise ValueError("External scaffold count must not exceed the compound count")
            if meta["task"]["kind"] == "classification":
                if (any(key not in test or not 0 <= test[key] <= 1
                        for key in ("balanced_accuracy", "roc_auc", "pr_auc"))
                        or not 0 <= baseline.get("pr_auc", -1) <= 1
                        or support.get("negative", 0) + support.get("positive", 0) != support["molecules"]
                        or not all(key in support for key in ("negative", "positive"))):
                    raise ValueError("External classification requires valid class counts, BA, ROC-AUC and both PR-AUC scores")
                result["beats_baseline"] = test["pr_auc"] > baseline["pr_auc"]
            else:
                if "r2" not in test or test["r2"] > 1 or min(test.get("mae", -1), baseline.get("mae", -1)) < 0:
                    raise ValueError("External regression requires R2 and both nonnegative MAE scores")
                result["beats_baseline"] = test["mae"] < baseline["mae"]
            existing = meta.setdefault("external_evaluations", [])
            if not isinstance(existing, list) or any(not isinstance(row, dict) for row in existing):
                raise ValueError("Existing external evidence is invalid")
            current = next((row for row in existing if row.get("dataset_sha256") == report.dataset_sha256), None)
            if current is not None:
                if current != packet:
                    raise ValueError("A different evaluation for this dataset is already recorded")
                return meta
            existing.append(packet)
            meta.pop("quality")
            write_json(safe_child(self.root, identifier) / "metadata.json", meta)
            return self.metadata(identifier)

    def review(self, identifier, review: Review):
        with _metadata_lock:
            meta = self.metadata(identifier)
            if meta["status"] != "experimental":
                raise ValueError("Only experimental models can be reviewed")
            self.require_quality(meta)
            self.load(identifier)
            meta.update(status="validated", review=dict(review.model_dump(), at=utcnow()))
            write_json(safe_child(self.root, identifier) / "metadata.json", meta)
            return meta

    def approve(self, identifier, approval: Approval):
        if not approval.confirm_activation:
            raise ValueError("Explicit activation confirmation is required")
        with _metadata_lock:
            meta = self.metadata(identifier)
            if meta["status"] != "validated":
                raise ValueError("Documented review required before approval")
            self.require_quality(meta)
            self.load(identifier)
            meta.update(status="approved", approval=dict(approval.model_dump(), at=utcnow()))
            write_json(safe_child(self.root, identifier) / "metadata.json", meta)
            # Separate endpoint-specific pointer; never modifies legacy QSAR manifests.
            write_json(self.active_path(meta["task"]["endpoint"], meta["task"]["context"]), dict(model_id=identifier))
            return meta

    def predict(self, identifier, smiles):
        with _metadata_lock:
            meta = self.metadata(identifier)
            self.require_quality(meta)
            if meta["status"] == "archived":
                raise ValueError("Archived model cannot be used for prediction")
            bundle = self.load(identifier)
        x = vector(molecule(smiles))
        applicability = assess(bundle["domain"], x)
        in_domain = applicability["in_domain"]
        result = dict(model_id=identifier, status=meta["status"], endpoint=meta["task"]["endpoint"],
                      units=meta["task"]["units"], value=float(bundle["model"].predict(x.reshape(1, -1))[0]) if in_domain else None,
                      applicability=applicability, quality=meta["quality"],
                      disclaimer="Research prediction, not experimental confirmation. Values are withheld outside the applicability domain.")
        if meta["task"]["kind"] == "classification":
            result["probability"] = float(bundle["model"].predict_proba(x.reshape(1, -1))[0, 1]) if in_domain else None
        return result

    def archive(self, identifier):
        with _metadata_lock:
            meta = self.metadata(identifier)
            meta.update(status="archived", archived_at=utcnow())
            write_json(safe_child(self.root, identifier) / "metadata.json", meta)
            return meta

    def predict_active(self, endpoint, context, smiles):
        path = self.active_path(endpoint, context)
        if not path.exists():
            # Preserve previously approved models, but verify the complete pair
            # below before trusting the ambiguous legacy lookup.
            key = checksum((endpoint + context).encode())
            path = self.root / ("active_" + key + ".json")
        pointer = read_json(path)
        meta = self.metadata(pointer["model_id"])
        if (meta["status"] != "approved" or meta["task"]["endpoint"] != endpoint
                or meta["task"]["context"] != context):
            raise ValueError("Endpoint has no approved active model")
        return self.predict(meta["id"], smiles)
