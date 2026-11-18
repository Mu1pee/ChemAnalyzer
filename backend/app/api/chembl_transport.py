"""Bounded ChEMBL requests and local, timestamped response cache."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import time
from uuid import uuid4
from collections import OrderedDict

import httpx
from app import config

BASE = "https://www.ebi.ac.uk/chembl/api/data"
logger = logging.getLogger(__name__)
FRESH_SECONDS = 24 * 3600
MAX_AGE_SECONDS = 30 * FRESH_SECONDS
MAX_ENTRIES = 128
MAX_CACHE_BYTES = 4_000_000  # Latest result and at most one complete snapshot.
_memory = OrderedDict()


class ChemblClient(httpx.AsyncClient):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.failures = []
        self.deadline = time.monotonic() + 55

    async def fetch(self, path, params=None):
        endpoint = path.split("/")[0].split(".")[0]
        code = "timeout"
        for attempt in range(2):
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                break
            retry = False
            delay = 0.35
            try:
                # Includes DNS resolution in the wall-clock limit.
                # Live EBI responses can take ~15 s even for a successful exact hit.
                # Allow those responses while retaining the shared 55 s deadline.
                response = await asyncio.wait_for(self.get(f"{BASE}/{path}", params=params), min(22, remaining))
                if response.status_code == 200:
                    data = response.json()
                    collection = {"molecule": "molecules", "similarity": "molecules",
                                  "mechanism": "mechanisms", "drug_indication": "drug_indications",
                                  "activity": "activities", "target": "targets"}.get(endpoint)
                    if (isinstance(data, dict) and (collection is None or
                            (isinstance(data.get(collection), list)
                             and all(isinstance(row, dict) for row in data[collection])))):
                        return data
                    code = "invalid_response"
                else:
                    code = f"http_{response.status_code}"
                    retry = response.status_code in (408, 429, 500, 502, 503, 504)
                    try:
                        delay = min(1.0, max(delay, float(response.headers.get("Retry-After", "0"))))
                    except ValueError:
                        pass
            except (httpx.TimeoutException, asyncio.TimeoutError):
                code, retry = "timeout", True
            except httpx.ConnectError as error:
                # TLS remains enabled; distinguish transport errors from missing compounds.
                code = "tls_error" if "CERTIFICATE_VERIFY_FAILED" in str(error) else "connection_error"
                retry = code != "tls_error"
            except httpx.HTTPError:
                code, retry = "connection_error", True
            except (ValueError, TypeError):
                code = "invalid_json"
            if not retry or attempt == 1:
                break
            await asyncio.sleep(min(delay, max(0, self.deadline - time.monotonic())))
        issue = f"{endpoint}: {code}"
        if issue not in self.failures:
            self.failures.append(issue)
        # Never log a SMILES, full URL, credentials, or response body.
        logger.warning("ChEMBL request failed: %s", issue)
        return None


def cache_key(smiles, inchikey):
    return hashlib.sha256(json.dumps([smiles, inchikey]).encode()).hexdigest()


def _directory():
    root = config.data_dir()
    return root / "cache" / "chembl-v1" if root else None


def _cache_entry(key):
    directory = _directory()
    memory_key = (str(directory), key)
    value = _memory.get(memory_key)
    if value is None and directory:
        try:
            path = directory / f"{key}.json"
            if path.stat().st_size <= MAX_CACHE_BYTES:
                value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return value if isinstance(value, dict) else None


def _validated_snapshot(value):
    if not isinstance(value, dict):
        return None
    try:
        from app.schemas.molecule import ChemblResponse
        stored_at = value["stored_at"]
        if isinstance(stored_at, bool) or not isinstance(stored_at, (int, float)):
            return None
        age = time.time() - stored_at
        payload = ChemblResponse.model_validate(value["profile"]).model_dump()
        if not payload["available"] or not math.isfinite(age) or not 0 <= age <= MAX_AGE_SECONDS:
            return None
        if payload["retrieved_at"]:
            try:
                retrieved = datetime.fromisoformat(payload["retrieved_at"])
                if retrieved.tzinfo is None or retrieved > datetime.fromtimestamp(stored_at, timezone.utc):
                    payload["retrieved_at"] = None
            except (ValueError, OverflowError):
                payload["retrieved_at"] = None
        # Historic cache entries predate pagination evidence. Keep the copy,
        # but never promote its capped activity table to a complete response.
        if payload["found"] and payload["activity_coverage"] is None:
            payload["partial"] = True
            issue = "activity: legacy_cache_coverage_unknown"
            if issue not in payload["warnings"]:
                payload["warnings"].append(issue)
            payload["message"] = "Сохранённая выдача ChEMBL: полнота списка измерений не проверена. Обновите запрос."
        elif payload["activity_coverage"] is not None and not payload["activity_coverage"]["complete"]:
            payload["partial"] = True
        json.dumps(payload, allow_nan=False)
        return value, payload, age
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def is_complete_snapshot(payload):
    coverage = payload["activity_coverage"]
    return (payload["found"] and bool(payload["retrieved_at"]) and not payload["partial"] and not payload["warnings"]
            and coverage is not None and coverage["complete"])


def _snapshots(value):
    if not isinstance(value, dict):
        return []
    # Never traverse nested history supplied by an old or damaged cache file.
    latest = _validated_snapshot(value)
    history = _validated_snapshot(value.get("complete_snapshot"))
    snapshots = [latest] if latest else []
    if history and is_complete_snapshot(history[1]):
        snapshots.append(history)
    return snapshots


def read_cache(key, *, prefer_complete=False):
    value = _cache_entry(key)
    snapshots = _snapshots(value)
    if not snapshots:
        return None
    complete = [item for item in snapshots if is_complete_snapshot(item[1])] if prefer_complete else []
    selected = min(complete, key=lambda item: item[2]) if complete else snapshots[0]
    _remember((str(_directory()), key), value)
    return deepcopy(selected[1]), selected[2]


def _remember(key, value):
    _memory[key] = value
    _memory.move_to_end(key)
    while len(_memory) > MAX_ENTRIES:
        _memory.popitem(last=False)


def write_cache(key, profile):
    directory = _directory()
    previous = _cache_entry(key)
    value = dict(stored_at=time.time(), profile=deepcopy(profile))
    incoming = _validated_snapshot(value)
    if incoming is None or not is_complete_snapshot(incoming[1]):
        full = [item for item in _snapshots(previous) if is_complete_snapshot(item[1])]
        if full:
            original, payload, _ = min(full, key=lambda item: item[2])
            value["complete_snapshot"] = dict(stored_at=original["stored_at"], profile=deepcopy(payload))
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode("utf-8")) > MAX_CACHE_BYTES:
            raise ValueError("Cache entry exceeds size limit")
    except (TypeError, ValueError, OverflowError):
        logger.warning("Could not encode bounded ChEMBL cache entry")
        return
    _remember((str(directory), key), value)
    if directory:
        temporary = directory / f"{key}.{uuid4().hex}.tmp"
        try:
            directory.mkdir(parents=True, exist_ok=True)
            temporary.write_text(encoded, encoding="utf-8")
            os.replace(temporary, directory / f"{key}.json")
            for path in sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[MAX_ENTRIES:]:
                path.unlink(missing_ok=True)
        except (OSError, ValueError):
            logger.warning("Could not save local ChEMBL cache")
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
