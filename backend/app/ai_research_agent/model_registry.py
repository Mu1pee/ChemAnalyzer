from uuid import uuid4

import joblib
from pydantic import BaseModel, Field
from app.model_quality import held_out_quality

from .applicability_domain import assess
from .molecular_features import molecule, vector
from .security import checksum, read_json, safe_child, utcnow, write_json


class Review(BaseModel):
    reviewer: str = Field(min_length=3, max_length=120)
    evidence: str = Field(min_length=30, max_length=4000)


class Approval(Review):
    confirm_activation: bool = False


class Registry:
    def __init__(self, root):
        self.root = root / "models"

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
        return [self.metadata(p.parent.name) for p in sorted(self.root.glob("*/metadata.json"))]

    def metadata(self, identifier):
        meta = read_json(safe_child(self.root, identifier) / "metadata.json")
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
        key = checksum((meta["task"]["endpoint"] + meta["task"]["context"]).encode())
        write_json(self.root / ("active_" + key + ".json"), dict(model_id=identifier))
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
        key = checksum((endpoint + context).encode())
        pointer = read_json(self.root / ("active_" + key + ".json"))
        meta = self.metadata(pointer["model_id"])
        if meta["status"] != "approved":
            raise ValueError("Endpoint has no approved active model")
        return self.predict(meta["id"], smiles)
