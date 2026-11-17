"""Cache recovery scenarios only; these are not scientific measurements."""
import asyncio
from datetime import datetime, timezone
import json
import time

import httpx
import pytest

from app.api import chembl, chembl_transport as transport
from app.schemas.molecule import ChemblResponse


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("CHEMANALYZER_DATA_DIR", str(tmp_path))
    transport._memory.clear()
    clock = [time.time()]
    monkeypatch.setattr(transport.time, "time", lambda: clock[0])
    return clock


def profile(clock, complete, rows=None):
    return ChemblResponse(available=True, found=True, chembl_id="CHEMBL545",
        retrieved_at=datetime.fromtimestamp(clock[0], timezone.utc).isoformat(),
        partial=not complete, warnings=[] if complete else ["activity: http_500"],
        activity_coverage=dict(retrieved_rows=rows or (3 if complete else 2),
            total_rows=rows or 3, pages=2 if complete else 1, complete=complete, limit_rows=8)).model_dump()


def history(clock):
    key = transport.cache_key("CCO", "FIXTURE-ONLY")
    clock[0] -= 2 * transport.FRESH_SECONDS
    full = profile(clock, True)
    transport.write_cache(key, full)
    clock[0] += 2 * transport.FRESH_SECONDS
    partial = profile(clock, False)
    transport.write_cache(key, partial)
    return key, full, partial


def test_offline_after_partial_refresh_recovers_last_full_disk_snapshot(isolated, monkeypatch):
    key, full, partial = history(isolated)
    transport._memory.clear()  # A fresh application process must retain the fallback.
    isolated[0] += 301
    factory = transport.ChemblClient
    monkeypatch.setattr(chembl, "ChemblClient", lambda **kw: factory(
        transport=httpx.MockTransport(lambda request: httpx.Response(503)), **kw))
    result = asyncio.run(chembl.fetch_chembl_profile("CCO", "FIXTURE-ONLY"))
    assert result["cached"] and result["stale"]
    assert result["activity_coverage"]["retrieved_rows"] == 3
    assert result["activity_coverage"]["complete"]
    assert result["retrieved_at"] == full["retrieved_at"] != partial["retrieved_at"]
    assert "molecule: http_503" in result["warnings"]


def test_fresh_partial_result_keeps_its_own_date_and_five_minute_cache(isolated, monkeypatch):
    key, full, partial = history(isolated)
    isolated[0] += 100
    monkeypatch.setattr(chembl, "ChemblClient", lambda **kw: pytest.fail("Fresh partial response must not be refreshed yet"))
    result = asyncio.run(chembl.fetch_chembl_profile("CCO", "FIXTURE-ONLY"))
    assert result["cached"] and result["partial"] and not result["stale"]
    assert result["activity_coverage"]["retrieved_rows"] == 2
    assert result["retrieved_at"] == partial["retrieved_at"]


def test_repeated_partial_writes_preserve_one_full_snapshot_without_extending_age(isolated):
    key, full, partial = history(isolated)
    isolated[0] += 400
    newest = profile(isolated, False)
    transport.write_cache(key, newest)
    transport._memory.clear()
    saved, age = transport.read_cache(key, prefer_complete=True)
    assert saved["retrieved_at"] == full["retrieved_at"]
    assert age == pytest.approx(2 * transport.FRESH_SECONDS + 400)
    raw = json.loads((transport._directory() / f"{key}.json").read_text(encoding="utf-8"))
    assert raw["profile"]["retrieved_at"] == newest["retrieved_at"]
    assert "complete_snapshot" not in raw["complete_snapshot"]


def test_expired_full_snapshot_cannot_displace_usable_partial_data(isolated):
    key, full, partial = history(isolated)
    isolated[0] += transport.MAX_AGE_SECONDS
    latest = profile(isolated, False)
    transport.write_cache(key, latest)
    transport._memory.clear()
    result, age = transport.read_cache(key, prefer_complete=True)
    assert result["retrieved_at"] == latest["retrieved_at"] and age == 0
    assert result["partial"] and result["activity_coverage"]["retrieved_rows"] == 2


def test_new_complete_response_replaces_the_older_fallback(isolated):
    key, old, partial = history(isolated)
    isolated[0] += 400
    latest = profile(isolated, True, rows=4)
    transport.write_cache(key, latest)
    raw = json.loads((transport._directory() / f"{key}.json").read_text(encoding="utf-8"))
    assert "complete_snapshot" not in raw
    isolated[0] += 400
    transport.write_cache(key, profile(isolated, False))
    transport._memory.clear()
    result, age = transport.read_cache(key, prefer_complete=True)
    assert result["retrieved_at"] == latest["retrieved_at"] and age == 400
    assert result["activity_coverage"]["retrieved_rows"] == 4


@pytest.mark.parametrize("damage", ["coverage", "future_time", "nonfinite_time", "huge_time"])
def test_damaged_fallback_cannot_suppress_valid_latest_result(isolated, damage):
    key, full, partial = history(isolated)
    path = transport._directory() / f"{key}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    fallback = raw["complete_snapshot"]
    if damage == "coverage":
        fallback["profile"]["activity_coverage"]["total_rows"] = 4
    else:
        fallback["stored_at"] = {"future_time": isolated[0] + 5, "nonfinite_time": float("nan"), "huge_time": 10**1000}[damage]
    path.write_text(json.dumps(raw), encoding="utf-8")
    transport._memory.clear()
    result, age = transport.read_cache(key, prefer_complete=True)
    assert result["retrieved_at"] == partial["retrieved_at"] and result["partial"]


def test_complete_snapshots_are_isolated_by_user_data_directory(isolated, monkeypatch, tmp_path):
    key, full, partial = history(isolated)
    monkeypatch.setenv("CHEMANALYZER_DATA_DIR", str(tmp_path / "other-user"))
    transport.write_cache(key, partial)
    result, age = transport.read_cache(key, prefer_complete=True)
    assert result["retrieved_at"] == partial["retrieved_at"] and result["partial"]


@pytest.mark.parametrize("bad_date", [None, "", "not-a-date", "2026-11-16", "2099-01-01T00:00:00Z"])
def test_unreliable_source_date_cannot_displace_dated_partial(isolated, bad_date):
    key, full, partial = history(isolated)
    path = transport._directory() / f"{key}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["complete_snapshot"]["profile"]["retrieved_at"] = bad_date
    path.write_text(json.dumps(record), encoding="utf-8")
    transport._memory.clear()
    saved, _ = transport.read_cache(key, prefer_complete=True)
    assert saved == partial
    transport.write_cache(key, partial)
    assert "complete_snapshot" not in json.loads(path.read_text(encoding="utf-8"))


def test_invalid_latest_entry_does_not_hide_a_valid_full_snapshot(isolated):
    key, full, partial = history(isolated)
    path = transport._directory() / f"{key}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["profile"] = ["invalid latest result"]
    path.write_text(json.dumps(raw), encoding="utf-8")
    transport._memory.clear()
    result, age = transport.read_cache(key)
    assert result["retrieved_at"] == full["retrieved_at"]
    assert result["activity_coverage"]["complete"]


def test_offline_legacy_snapshot_keeps_unknown_coverage_warning(isolated, monkeypatch):
    key = transport.cache_key("CCO", "FIXTURE-ONLY")
    legacy = ChemblResponse(available=True, found=True, chembl_id="CHEMBL545").model_dump()
    transport.write_cache(key, legacy)
    isolated[0] += 2 * transport.FRESH_SECONDS
    factory = transport.ChemblClient
    monkeypatch.setattr(chembl, "ChemblClient", lambda **kw: factory(
        transport=httpx.MockTransport(lambda request: httpx.Response(503)), **kw))
    result = asyncio.run(chembl.fetch_chembl_profile("CCO", "FIXTURE-ONLY"))
    assert result["cached"] and result["stale"] and result["partial"]
    assert result["activity_coverage"] is None
    assert "activity: legacy_cache_coverage_unknown" in result["warnings"]
