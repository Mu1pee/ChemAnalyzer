from pathlib import Path

from .security import read_json, write_json, utcnow


def update(run: Path, stage: str, **extra):
    previous = read_json(run / "state.json") if (run / "state.json").exists() else {}
    events = previous.get("events", []) + [dict(at=utcnow(), stage=stage)]
    write_json(run / "state.json", dict(previous, stage=stage, updated_at=utcnow(), events=events, **extra))
