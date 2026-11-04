import multiprocessing
import os
import threading
import time
from pathlib import Path
from uuid import uuid4

from .config import Provenance, TaskConfig, storage_root
from .data_validation import validate_source
from .experiment_tracking import update
from .security import bounded_text, checksum, read_json, safe_child, utcnow, write_json


def execute_run(run_path: str):
    """Spawn-safe entry point; all expensive imports happen inside the worker."""
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[variable] = "1"
    run = Path(run_path)
    try:
        from .data_validation import read_measurements
        from .molecular_features import prepare, FEATURE_CONFIG
        from .training import train
        from .applicability_domain import fit_domain
        from .model_registry import Registry
        from .reporting import write_report
        import platform
        import importlib.metadata
        import numpy as np

        task = TaskConfig.model_validate(read_json(run / "task.json"))
        provenance = Provenance.model_validate(read_json(run / "provenance.json"))
        validate_source(task, provenance)
        update(run, "preparing", status="running")
        raw = (run / "dataset.csv").read_bytes()
        rows, issues = read_measurements(raw.decode("utf-8-sig"), task.max_rows)
        X, y, groups, preparation = prepare(rows, issues)
        write_json(run / "preparation.json", preparation)
        if read_json(run / "request.json")["action"] == "prepare":
            update(run, "prepared", status="completed", accepted=preparation["accepted"])
            return
        model, train_X, evaluation = train(X, y, groups, task, lambda stage: update(run, stage))
        update(run, "saving")
        domain = fit_domain(train_X)
        meta = dict(task=task.model_dump(), source=provenance.model_dump(), dataset_sha256=checksum(raw),
                    feature_config=FEATURE_CONFIG, evaluation=evaluation,
                    dependencies={name: importlib.metadata.version(name) for name in ("rdkit", "scikit-learn", "numpy", "scipy", "joblib")},
                    python_version=platform.python_version(), run_id=run.name, accepted=preparation["accepted"],
                    domain_method=domain["method"])
        # Registry is per run; supervisor publishes only after successful bounded completion.
        meta = Registry(run).register(dict(model=model, domain=domain), meta)
        np.savez_compressed(run / "features.npz", X=X, y=y, groups=groups)
        write_report(run, meta)
        update(run, "ready_to_publish", status="running", model_id=meta["id"])
    except Exception as error:
        update(run, "failed", status="failed", error=f"{type(error).__name__}: {error}")


class ResearchAgent:
    def __init__(self, root=None):
        self.root = Path(root) if root is not None else storage_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.jobs = {}
        self.monitors = {}
        # Recovery preserves all evidence; restarting needs an explicit new run.
        for state in self.root.glob("runs/*/state.json"):
            if read_json(state).get("status") in ("queued", "running"):
                update(state.parent, "interrupted", status="interrupted", error="Backend restarted; explicit restart required")

    def create(self, task: TaskConfig):
        identifier = uuid4().hex
        folder = safe_child(self.root / "tasks", identifier)
        write_json(folder / "task.json", dict(task.model_dump(), id=identifier, created_at=utcnow()))
        return read_json(folder / "task.json")

    def tasks(self):
        return [read_json(p) for p in sorted(self.root.glob("tasks/*/task.json"))]

    def task(self, identifier):
        data = read_json(safe_child(self.root / "tasks", identifier) / "task.json")
        return TaskConfig.model_validate({k: v for k, v in data.items() if k not in ("id", "created_at")})

    def import_csv(self, identifier, csv_text, provenance: Provenance, evidence=None):
        from .data_validation import read_measurements
        with self.lock:
            task = self.task(identifier)
            validate_source(task, provenance)
            raw = bounded_text(csv_text)
            rows, issues = read_measurements(csv_text, task.max_rows)
            if not rows:
                raise ValueError("No usable experimental measurements")
            # Immutable dataset versions avoid mixed snapshots during concurrent import/run.
            folder = safe_child(self.root / "tasks", identifier)
            digest = checksum(raw)
            version_id = uuid4().hex
            version = folder / version_id
            version.mkdir(exist_ok=True)
            (version / "dataset.csv").write_bytes(raw)
            write_json(version / "provenance.json", provenance.model_dump())
            write_json(version / "evidence.json", evidence or {"curation": "User declaration; source/conditions require independent review"})
            manifest = dict(dataset_sha256=digest, version_id=version_id, imported_at=utcnow(), measurements=len(rows), issues=issues)
            write_json(folder / "dataset.json", manifest)
            return manifest

    def import_freesolv(self, identifier):
        from .data_discovery import fetch_freesolv
        text, provenance, raw, license_data, evidence = fetch_freesolv()
        result = self.import_csv(identifier, text, Provenance(**provenance), evidence)
        folder = safe_child(self.root / "tasks", identifier) / result["version_id"]
        (folder / "source.txt").write_bytes(raw)
        (folder / "LICENSE.txt").write_bytes(license_data)
        return result

    def start(self, identifier, action="train"):
        if action not in ("prepare", "train"):
            raise ValueError("Unknown action")
        import shutil
        with self.lock:
            if any(t.is_alive() for t in self.monitors.values()):
                raise ValueError("A research worker is already running; wait or cancel it")
            task = self.task(identifier)
            if task.domain == "antidote_catalog" and action == "train":
                raise ValueError("Antidote catalog tasks cannot train models")
            folder = safe_child(self.root / "tasks", identifier)
            manifest = read_json(folder / "dataset.json")
            source = safe_child(folder, manifest["version_id"])
            run_id = uuid4().hex
            run = safe_child(self.root / "runs", run_id)
            run.mkdir(parents=True)
            for name in ("dataset.csv", "provenance.json", "evidence.json"):
                shutil.copyfile(source / name, run / name)
            write_json(run / "task.json", task.model_dump())
            write_json(run / "request.json", dict(task_id=identifier, action=action))
            update(run, "queued", status="queued", id=run_id, task_id=identifier)
            process = multiprocessing.get_context("spawn").Process(target=execute_run, args=(str(run),), daemon=True)
            process.start()
            self.jobs[run_id] = process
            monitor = threading.Thread(target=self._supervise, args=(run_id, task), daemon=True)
            self.monitors[run_id] = monitor
            monitor.start()
            return self.run(run_id)

    def _supervise(self, identifier, task):
        import psutil
        import shutil
        run, process = safe_child(self.root / "runs", identifier), self.jobs[identifier]
        started, reason = time.monotonic(), None
        while process.is_alive():
            try:
                rss = psutil.Process(process.pid).memory_info().rss
                disk = sum(p.stat().st_size for p in run.rglob("*") if p.is_file())
                if rss > task.max_ram_mb * 1024**2:
                    reason = "RAM limit exceeded"
                if disk > task.max_disk_mb * 1024**2:
                    reason = "Disk limit exceeded"
                if time.monotonic() - started > task.max_seconds:
                    reason = "Time limit exceeded"
                if reason:
                    with self.lock:
                        if process.is_alive():
                            process.terminate()
                            process.join(5)
                        update(run, "resource_limit", status="failed", error=reason)
                    return
            except (psutil.NoSuchProcess, FileNotFoundError):
                pass
            process.join(.25)
        with self.lock:
            state = self.run(identifier)
            if state["stage"] == "ready_to_publish" and process.exitcode == 0:
                if sum(p.stat().st_size for p in run.rglob("*") if p.is_file()) > task.max_disk_mb * 1024**2:
                    update(run, "resource_limit", status="failed", error="Disk limit exceeded at completion")
                    return
                model_id = state["model_id"]
                destination = safe_child(self.root / "models", model_id)
                destination.parent.mkdir(exist_ok=True)
                try:
                    shutil.copytree(run / "models" / model_id, destination)
                    update(run, "completed", status="completed")
                except OSError as error:
                    update(run, "failed", status="failed", error=f"Registry publication failed: {error}")
            elif state["status"] in ("queued", "running"):
                update(run, "failed", status="failed", error=f"Worker exited unexpectedly ({process.exitcode})")

    def cancel(self, identifier):
        with self.lock:
            process = self.jobs.get(identifier)
            state = self.run(identifier)
            if state["status"] not in ("queued", "running"):
                return state
            if process and process.is_alive():
                process.terminate()
                process.join(5)
            update(safe_child(self.root / "runs", identifier), "cancelled", status="cancelled")
            return self.run(identifier)

    def run(self, identifier):
        run = safe_child(self.root / "runs", identifier)
        state = read_json(run / "state.json")
        for name in ("preparation", "result"):
            if (run / (name + ".json")).exists():
                state[name] = read_json(run / (name + ".json"))
        return state

    def runs(self):
        return [read_json(p) for p in sorted(self.root.glob("runs/*/state.json"))]

    def shutdown(self):
        for identifier in list(self.jobs):
            self.cancel(identifier)
