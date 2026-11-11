"""Scientific contract for the two requested specialized research endpoints."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ai_research_agent.config import Provenance
from app.ai_research_agent.data_validation import validate_source
from app.model_quality import classification_reasons, held_out_quality, valid_count

FEATURE_CONFIG = dict(morgan_radius=2, morgan_bits=2048, chirality=False,
                      standardization="single fragment; largest-fragment standardizer and uncharger; canonical isomeric SMILES",
                      grouping="nonchiral Murcko scaffold; all acyclic structures share ACYCLIC")
PROFILES = {
    "apap_rescue": dict(domain="antidote", endpoint="rescue_from_acetaminophen_injury",
                        conditions=("species", "cell_or_tissue", "toxicant_concentration", "compound_concentration",
                                    "exposure_duration", "pretreatment_or_posttreatment", "readout", "control_definition")),
    "arabidopsis_primary_root": dict(domain="growth_regulating", endpoint="primary_root_length_relative_to_control",
                                     conditions=("ecotype", "seedling_age", "compound_concentration", "exposure_duration",
                                                 "medium", "light_cycle", "control_definition", "replicates")),
}


class SpecializedProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[2] = 2
    profile_id: Literal["apap_rescue", "arabidopsis_primary_root"]
    domain: Literal["antidote", "growth_regulating"]
    endpoint: str = Field(min_length=3, max_length=160)
    context: str = Field(min_length=10, max_length=2000)
    species: str = Field(min_length=3, max_length=200)
    toxicant: str | None = Field(default=None, max_length=200)
    conditions: dict[str, str]
    label_definition: str = Field(min_length=30, max_length=4000)
    dataset_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    provenance: Provenance

    @model_validator(mode="after")
    def exact_experiment(self):
        profile = PROFILES[self.profile_id]
        if self.domain != profile["domain"] or self.endpoint != profile["endpoint"]:
            raise ValueError("Separate endpoint/profile required for another biological task")
        if self.domain == "antidote":
            if (self.toxicant or "").strip().lower() not in ("acetaminophen", "paracetamol"):
                raise ValueError("This antidote profile requires acetaminophen as the toxicant")
            if self.conditions.get("species") != self.species:
                raise ValueError("Species must match the documented experimental conditions")
        elif self.species != "Arabidopsis thaliana" or self.toxicant is not None:
            raise ValueError("This growth profile requires Arabidopsis thaliana without a toxicant")
        if any(not self.conditions.get(key, "").strip() for key in profile["conditions"]):
            raise ValueError("All profile-specific experimental conditions must be documented")
        # Same endpoint, units, context and experimental declaration as the CSV
        # task. This checks a curator declaration, not independent source review.
        from types import SimpleNamespace
        validate_source(SimpleNamespace(endpoint=self.endpoint, units="0/1", context=self.context), self.provenance)
        return self


def quality(meta):
    result = held_out_quality("classification", meta.get("evaluation"))
    result["reasons"] += classification_reasons(meta.get("metrics"), min_mcc=.10)
    if meta.get("schema_version") != 2 or meta.get("feature_config") != FEATURE_CONFIG:
        result["reasons"].append("Retraining with the version-2 specialized evidence contract is required")
    try:
        protocol = SpecializedProtocol.model_validate(meta.get("protocol"))
        if any(getattr(protocol, key) != meta.get(key) for key in ("domain", "endpoint", "context")):
            raise ValueError("Protocol/model context mismatch")
        if protocol.dataset_sha256 != meta.get("dataset_sha256"):
            raise ValueError("Protocol/dataset checksum mismatch")
    except ValueError as error:
        result["reasons"].append(str(error))
    evaluation = meta.get("evaluation")
    if not isinstance(evaluation, dict) or meta.get("metrics") != evaluation.get("test"):
        result["reasons"].append("Served metrics must equal the fixed held-out evaluation")
    support = evaluation.get("support", {}) if isinstance(evaluation, dict) else {}
    train = support.get("train", {}) if isinstance(support, dict) else {}
    test = support.get("test", {}) if isinstance(support, dict) else {}
    train = train if isinstance(train, dict) else {}
    test = test if isinstance(test, dict) else {}
    if (not valid_count(train.get("positive"), 30) or not valid_count(train.get("negative"), 30)
            or train.get("molecules") != meta.get("n_train")
            or train.get("positive") != meta.get("n_active") or train.get("negative") != meta.get("n_inactive")
            or (isinstance(meta.get("metrics"), dict) and meta["metrics"].get("n_evaluated") != test.get("molecules"))):
        result["reasons"].append("Training/test support must match model metadata and retain 30 fitted compounds/class")
    if not isinstance(meta.get("scientific_status"), str):
        result["reasons"].append("Scientific status must be documented")
    partitions = evaluation.get("split") if isinstance(evaluation, dict) else None
    seen = set()
    total = meta.get("n_total")
    valid_partitions = isinstance(partitions, dict) and valid_count(total, 60) and total <= 50000
    for name in ("train", "validation", "test"):
        indices = partitions.get(name) if isinstance(partitions, dict) else None
        counts = support.get(name) if isinstance(support, dict) else None
        if not isinstance(indices, list) or not isinstance(counts, dict):
            valid_partitions = False
            continue
        if (not valid_count(counts.get("molecules")) or len(indices) != counts.get("molecules")
                or not valid_count(counts.get("scaffolds"), 3)
                or counts["scaffolds"] > len(indices)
                or not valid_count(counts.get("positive"), 5) or not valid_count(counts.get("negative"), 5)
                or counts["positive"] + counts["negative"] != len(indices)
                or any(not isinstance(index, int) or isinstance(index, bool) or index < 0 for index in indices)):
            valid_partitions = False
            continue
        current = set(indices)
        if len(current) != len(indices) or current & seen:
            valid_partitions = False
        seen.update(current)
    if not valid_partitions or seen != set(range(int(total))):
        result["reasons"].append("Complete nonoverlapping train/validation/test partitions must match their support")
    result["passed"] = not result["reasons"]
    return result
