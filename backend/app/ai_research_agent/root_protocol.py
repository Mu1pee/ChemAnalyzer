"""Curator-declared experiment contract for primary-root length regression."""
import hashlib
import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ROOT_ENDPOINT = "primary_root_length_relative_to_control"
Documented = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]


class RootProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    species: Literal["Arabidopsis thaliana"]
    ecotype: Documented
    seedling_age_at_treatment_days: float = Field(ge=0, allow_inf_nan=False, strict=True)
    compound_concentration_uM: float = Field(gt=0, allow_inf_nan=False, strict=True)
    exposure_duration_h: float = Field(gt=0, allow_inf_nan=False, strict=True)
    medium: Documented
    light_cycle: Documented
    matched_control: Documented
    replicate_design: Documented
    measurement_method: Documented
    normalization: Literal["treated_primary_root_length / matched_control_primary_root_length"]
    dataset_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def is_root_task(task):
    def field(name):
        return task.get(name) if isinstance(task, dict) else getattr(task, name, None)
    return field("domain") == "growth" or field("endpoint") == ROOT_ENDPOINT


def require_root_protocol(task):
    if not is_root_task(task):
        return None
    if (task.domain != "growth" or task.endpoint != ROOT_ENDPOINT
            or task.kind != "regression" or task.units != "ratio"):
        raise ValueError("Primary-root regression requires the growth domain, exact endpoint and ratio units")
    protocol = getattr(task, "root_protocol", None)
    if protocol is None:
        raise ValueError("Primary-root data require root_protocol with experimental conditions and CSV SHA-256")
    return RootProtocol.model_validate(protocol)


def validate_root_dataset(task, raw, rows):
    protocol = require_root_protocol(task)
    if protocol is None:
        return
    if hashlib.sha256(raw).hexdigest() != protocol.dataset_sha256:
        raise ValueError("Root protocol/CSV checksum mismatch; review this exact dataset")
    for row in rows:
        value = row["value"]
        if isinstance(value, bool) or not math.isfinite(value) or value < 0:
            raise ValueError("Measured primary-root/control ratios must be finite and nonnegative")
    # Ratios above one represent longer roots and must not be clipped or treated
    # as probabilities. Missing values remain the ordinary reader's exclusions.


def root_metadata_reasons(meta):
    if not is_root_task(meta.get("task")):
        return []
    # Keep imports local: config/source validation also use this contract.
    from .config import Provenance, TaskConfig
    from .data_validation import validate_source
    try:
        task = TaskConfig.model_validate(meta["task"])
        provenance = Provenance.model_validate(meta.get("source"))
        validate_source(task, provenance)
        protocol = require_root_protocol(task)
        if protocol.dataset_sha256 != meta.get("dataset_sha256"):
            raise ValueError("Root protocol/model dataset checksum mismatch")
    except (ValueError, TypeError, KeyError) as error:
        return ["Primary-root experimental evidence is incomplete: " + str(error)]
    return []
