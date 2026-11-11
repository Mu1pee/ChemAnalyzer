"""Bounded ChEMBL requests and local, timestamped response cache."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import logging
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
                    if isinstance(data, dict):
                        return data
                    code = "invalid_json"
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


def read_cache(key):
    directory = _directory()
    memory_key = (str(directory), key)
    value = _memory.get(memory_key)
    if value is None and directory:
        try:
            path = directory / f"{key}.json"
            if path.stat().st_size <= 2_000_000:
                value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    if not isinstance(value, dict):
        return None
    try:
        from app.schemas.molecule import ChemblResponse
        age = time.time() - value["stored_at"]
        payload = ChemblResponse.model_validate(value["profile"]).model_dump()
        if not payload["available"] or not 0 <= age <= MAX_AGE_SECONDS:
            return None
        _remember(memory_key, value)
        return deepcopy(payload), age
    except (KeyError, TypeError, ValueError):
        return None


def _remember(key, value):
    _memory[key] = value
    _memory.move_to_end(key)
    while len(_memory) > MAX_ENTRIES:
        _memory.popitem(last=False)


def write_cache(key, profile):
    directory = _directory()
    value = dict(stored_at=time.time(), profile=deepcopy(profile))
    _remember((str(directory), key), value)
    if directory:
        temporary = directory / f"{key}.{uuid4().hex}.tmp"
        try:
            directory.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding="utf-8")
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
