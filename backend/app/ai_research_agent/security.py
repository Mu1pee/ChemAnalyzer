import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def checksum(data: bytes):
    return hashlib.sha256(data).hexdigest()


def safe_child(root: Path, identifier: str) -> Path:
    if not re.fullmatch(r"[a-z0-9_-]{1,80}", identifier):
        raise ValueError("Invalid identifier")
    path = root / identifier
    if path.resolve().parent != root.resolve():
        raise ValueError("Path outside storage")
    return path


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def bounded_text(value: str, max_bytes=8_000_000):
    data = value.encode("utf-8")
    if len(data) > max_bytes:
        raise ValueError("Input exceeds 8 MB limit")
    return data
