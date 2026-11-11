"""Network failure fixtures, never scientific training data."""
import asyncio
import time

import httpx
import pytest

from app.api import chembl, chembl_transport as transport


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("CHEMANALYZER_DATA_DIR", str(tmp_path))
    transport._memory.clear()


def run_fetch(handler, monkeypatch):
    factory = transport.ChemblClient
    monkeypatch.setattr(chembl, "ChemblClient", lambda **kw: factory(transport=httpx.MockTransport(handler), **kw))
    return asyncio.run(chembl.fetch_chembl_profile("CCO", "TESTKEY"))


def test_transient_503_is_retried_without_reporting_outage():
    count = 0
    def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(503 if count == 1 else 200, json={"molecules": []})
    async def scenario():
        async with transport.ChemblClient(transport=httpx.MockTransport(handler)) as client:
            assert await client.fetch("molecule.json") == {"molecules": []}
            assert not client.failures
    asyncio.run(scenario())
    assert count == 2


def test_permanent_error_is_not_retried_and_contains_no_structure():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(400)
    async def scenario():
        async with transport.ChemblClient(transport=httpx.MockTransport(handler)) as client:
            assert await client.fetch("similarity/SECRET-SMILES/70.json") is None
            assert client.failures == ["similarity: http_400"]
    asyncio.run(scenario())
    assert len(requests) == 1


def test_exact_hit_survives_failed_similarity_and_is_cached(monkeypatch):
    def handler(request):
        if "/similarity/" in request.url.path:
            raise httpx.ConnectError("offline")
        if request.url.path.endswith("molecule.json"):
            return httpx.Response(200, json={"molecules": [{"molecule_chembl_id": "CHEMBL545", "pref_name": "ETHANOL"}]})
        return httpx.Response(200, json={})
    result = run_fetch(handler, monkeypatch)
    assert result["available"] and result["found"] and result["partial"]
    assert result["chembl_id"] == "CHEMBL545"
    assert "частично" in result["message"]
    assert result["retrieved_at"]
    monkeypatch.setattr(chembl, "ChemblClient", lambda **kw: pytest.fail("Fresh cache must avoid network"))
    cached = asyncio.run(chembl.fetch_chembl_profile("CCO", "TESTKEY"))
    assert cached["cached"] and cached["chembl_id"] == result["chembl_id"]


def test_offline_uses_stale_disk_cache_with_original_timestamp(monkeypatch):
    from app.schemas.molecule import ChemblResponse
    key = transport.cache_key("CCO", "TESTKEY")
    profile = ChemblResponse(available=True, found=True, chembl_id="CHEMBL545", retrieved_at="2026-11-01T12:00:00+00:00").model_dump()
    now = time.time()
    monkeypatch.setattr(transport.time, "time", lambda: now - 2 * transport.FRESH_SECONDS)
    transport.write_cache(key, profile)
    transport._memory.clear()
    monkeypatch.setattr(transport.time, "time", lambda: now)
    def offline(request):
        raise httpx.ConnectError("offline")
    result = run_fetch(offline, monkeypatch)
    assert result["available"] and result["stale"] and result["cached"]
    assert result["retrieved_at"] == profile["retrieved_at"]
    assert "сохранённая" in result["message"]


def test_empty_success_is_not_unavailability(monkeypatch):
    result = run_fetch(lambda request: httpx.Response(200, json={"molecules": []}), monkeypatch)
    assert result["available"] and not result["found"] and not result["partial"]
    assert "не найдены" in result["message"]


def test_deadline_bounds_wait_even_if_transport_hangs():
    async def handler(request):
        await asyncio.sleep(10)
        return httpx.Response(200, json={})
    async def scenario():
        async with transport.ChemblClient(transport=httpx.MockTransport(handler)) as client:
            client.deadline = time.monotonic() + .05
            assert await client.fetch("molecule.json") is None
            assert client.failures == ["molecule: timeout"]
    started = time.monotonic()
    asyncio.run(scenario())
    assert time.monotonic() - started < 2


def test_nonfinite_activity_is_excluded():
    assert chembl.aggregate_targets({"activities": [dict(target_chembl_id="CHEMBL230", pchembl_value="nan")]}) == []


def test_successful_fifteen_second_response_is_not_reported_unavailable(monkeypatch):
    # Virtual elapsed time represents the measured EBI latency, without sleeping.
    async def simulated_wait(awaitable, timeout):
        if timeout < 15:
            awaitable.close()
            raise asyncio.TimeoutError
        return await awaitable
    monkeypatch.setattr(transport.asyncio, "wait_for", simulated_wait)
    async def scenario():
        async with transport.ChemblClient(timeout=chembl.TIMEOUT, transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"molecules": []}))) as client:
            assert client.timeout.read >= 15
            assert await client.fetch("molecule.json") == {"molecules": []}
            assert not client.failures
    asyncio.run(scenario())


def test_empty_similarity_cannot_mask_failed_exact_search(monkeypatch):
    def handler(request):
        if request.url.path.endswith("molecule.json"):
            return httpx.Response(500)
        return httpx.Response(200, json={"molecules": []})
    result = run_fetch(handler, monkeypatch)
    assert result["available"] and result["partial"] and not result["found"]
    assert "molecule: http_500" in result["warnings"]
    assert "частично" in result["message"] and "не найдены" not in result["message"]


def test_http_200_error_envelope_is_not_an_empty_success():
    async def scenario():
        async with transport.ChemblClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"error": "database unavailable"}))) as client:
            assert await client.fetch("molecule.json") is None
            assert client.failures == ["molecule: invalid_response"]
    asyncio.run(scenario())
