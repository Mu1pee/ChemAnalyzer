from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app import config as app_config


def storage_root() -> Path:
    return (app_config.data_dir() or app_config.BACKEND_DIR) / "research_agent"


class TaskConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=3, max_length=120)
    domain: Literal["qsar", "admet", "growth", "antidote_catalog"] = "qsar"
    endpoint: str = Field(min_length=3, max_length=160)
    units: str = Field(min_length=1, max_length=60)
    context: str = Field(min_length=10, max_length=2000)
    kind: Literal["regression", "classification"] = "regression"
    mode: Literal["manual", "assisted", "scheduled"] = "manual"
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    max_rows: int = Field(default=10000, ge=60, le=50000)
    max_seconds: int = Field(default=600, ge=10, le=3600)
    max_ram_mb: int = Field(default=2048, ge=256, le=8192)
    max_disk_mb: int = Field(default=512, ge=32, le=2048)
    # No paid API or LLM calls are implemented. CPU is always one worker/thread.

    @model_validator(mode="after")
    def domain_context(self):
        if self.domain == "growth" and (
            self.endpoint != "primary_root_length_relative_to_control"
            or "Arabidopsis thaliana" not in self.context
        ):
            raise ValueError("Growth tasks require Arabidopsis thaliana primary-root endpoint")
        return self


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_url: str = Field(min_length=8, max_length=2000)
    doi: str = Field(min_length=3, max_length=200)
    license: Literal["CC-BY-4.0", "CC0-1.0", "CC-BY-SA-4.0", "PDDL-1.0", "Public-Domain-US-Gov"]
    license_url: str = Field(min_length=8, max_length=2000)
    source_version: str = Field(min_length=1, max_length=100)
    retrieved_at: str = Field(min_length=10, max_length=100)
    endpoint: str
    units: str
    context: str
    experimental: bool
    curator: str = Field(min_length=3, max_length=120)


FREESOLV_TASK = dict(
    name="FreeSolv experimental hydration free energy",
    endpoint="hydration_free_energy", units="kcal/mol",
    context="FreeSolv v0.52 small neutral molecules; hydration free energy in water; source reference conditions",
)
