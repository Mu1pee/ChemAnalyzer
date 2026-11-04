"""Explicit allow-list scheduling, driven by FastAPI lifespan; never activates models."""
import threading
import time

from pydantic import BaseModel, Field

from .data_discovery import fetch_freesolv
from .security import checksum, read_json, safe_child, utcnow, write_json


class Schedule(BaseModel):
    task_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    interval_seconds: int = Field(default=86400, ge=3600, le=2592000)
    enabled: bool = False
    check_freesolv: bool = False
    approved_dataset_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class Scheduler:
    def __init__(self, agent):
        self.agent = agent
        self.stop_event = threading.Event()
        self.thread = None

    def save(self, policy: Schedule):
        task = self.agent.task(policy.task_id)
        if policy.check_freesolv and task.endpoint != "hydration_free_energy":
            raise ValueError("FreeSolv checks require a hydration_free_energy task")
        if policy.approved_dataset_sha256:
            folder = safe_child(self.agent.root / "tasks", policy.task_id)
            manifest = read_json(folder / "dataset.json")
            if manifest["dataset_sha256"] != policy.approved_dataset_sha256:
                raise ValueError("Scheduled training authorization must match imported dataset checksum")
        path = safe_child(self.agent.root / "schedules", policy.task_id)
        write_json(path / "policy.json", policy.model_dump())
        return policy.model_dump()

    def tick(self, now=None):
        now = time.time() if now is None else now
        for path in self.agent.root.glob("schedules/*/policy.json"):
            policy = Schedule.model_validate(read_json(path))
            state_path = path.parent / "state.json"
            state = read_json(state_path) if state_path.exists() else {}
            if not policy.enabled or state.get("next_check", 0) > now:
                continue
            result = dict(at=utcnow(), next_check=now + policy.interval_seconds)
            try:
                if policy.check_freesolv:
                    text, provenance, raw, license_data, evidence = fetch_freesolv()
                    result["source_check"] = dict(dataset_sha256=checksum(text.encode()), provenance=provenance, evidence=evidence)
                if policy.approved_dataset_sha256:
                    folder = safe_child(self.agent.root / "tasks", policy.task_id)
                    digest = read_json(folder / "dataset.json")["dataset_sha256"]
                    if digest != policy.approved_dataset_sha256:
                        result["training"] = "Skipped: changed data require new explicit approval"
                    elif state.get("run_id") and self.agent.run(state["run_id"])["status"] in ("queued", "running"):
                        result.update(run_id=state["run_id"], training="Previous scheduled run still active")
                    elif state.get("run_id") and self.agent.run(state["run_id"])["status"] == "completed":
                        result.update(trained_sha256=digest, training="Approved dataset completed")
                    elif state.get("trained_sha256") != digest:
                        run = self.agent.start(policy.task_id)
                        result.update(run_id=run["id"])
                    else:
                        result["training"] = "No new approved data"
            except Exception as error:
                result["error"] = f"{type(error).__name__}: {error}"
            if "trained_sha256" not in result and state.get("trained_sha256"):
                result["trained_sha256"] = state["trained_sha256"]
            write_json(state_path, result)

    def start(self):
        def loop():
            while not self.stop_event.is_set():
                self.tick()
                self.stop_event.wait(30)
        self.thread = threading.Thread(target=loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(1)
