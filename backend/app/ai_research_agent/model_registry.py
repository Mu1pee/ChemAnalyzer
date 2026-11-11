import json
import logging
from uuid import uuid4

import joblib
from pydantic import BaseModel, Field
from app.model_quality import held_out_quality

from .applicability_domain import assess
from .molecular_features import molecule, vector
from .security import checksum, read_json, safe_child, utcnow, write_json

logger = logging.getLogger(__name__)


class Review(BaseModel):
    reviewer: str = Field(min_length=3, max_length=120)
    evidence: str = Field(min_length=30, max_length=4000)


class Approval(Review):
    confirm_activation: bool = False


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
        meta["quality"] = held_out_quality(meta["task"]["kind"], meta.get("evaluation"))
        return meta

    def require_quality(self, meta):
        if not meta["quality"]["passed"]:
            raise ValueError("Model failed quality policy: " + "; ".join(meta["quality"]["reasons"]))

    def load(self, identifier):
        folder = safe_child(self.root, identifier)
        meta = self.metadata(identifier)
        path = folder / "model.joblib"
        if checksum(path.read_bytes()) != meta["artifact_sha256"]:
            raise ValueError("Model checksum mismatch")
        # Only agent-generated local artifacts; arbitrary uploaded pickle is never accepted.
        return joblib.load(path)

    def review(self, identifier, review: Review):
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
        meta = self.metadata(identifier)
        self.require_quality(meta)
        bundle = self.load(identifier)
        if meta["status"] == "archived":
            raise ValueError("Archived model cannot be used for prediction")
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
