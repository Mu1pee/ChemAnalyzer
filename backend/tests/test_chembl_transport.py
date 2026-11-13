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


def paged_activities(handler, monkeypatch, max_pages=4):
    monkeypatch.setattr(chembl, "ACTIVITY_LIMIT", 2)
    monkeypatch.setattr(chembl, "MAX_ACTIVITY_PAGES", max_pages)
    async def scenario():
        async with transport.ChemblClient(transport=httpx.MockTransport(handler)) as client:
            payload, coverage = await chembl._fetch_activities(client, "CHEMBL25")
            return payload, coverage, client.failures
    return asyncio.run(scenario())


def activity_page(offset, total, ids):
    return {"activities": [{"activity_id": i} for i in ids],
            "page_meta": {"offset": offset, "total_count": total}}


def test_activity_fetches_remaining_page_without_following_remote_urls(monkeypatch):
    seen = []
    def handler(request):
        offset = int(request.url.params["offset"])
        seen.append(offset)
        assert request.url.host == "www.ebi.ac.uk" and request.url.params["order_by"] == "activity_id"
        payload = activity_page(offset, 3, [1, 2] if offset == 0 else [3])
        payload["page_meta"]["next"] = "https://untrusted.invalid/ignored"
        return httpx.Response(200, json=payload)
    payload, coverage, errors = paged_activities(handler, monkeypatch)
    assert seen == [0, 2] and len(payload["activities"]) == 3
    assert coverage == dict(retrieved_rows=3, total_rows=3, pages=2, complete=True, limit_rows=8)
    assert not errors


def test_large_source_is_capped_and_explicitly_incomplete(monkeypatch):
    def handler(request):
        offset = int(request.url.params["offset"])
        return httpx.Response(200, json=activity_page(offset, 7, [offset+1, offset+2]))
    payload, coverage, errors = paged_activities(handler, monkeypatch, max_pages=2)
    assert len(payload["activities"]) == 4 and coverage["total_rows"] == 7
    assert not coverage["complete"] and errors == ["activity: row_limit (4 of 7)"]


def test_empty_activity_collection_is_complete_not_an_outage(monkeypatch):
    payload, coverage, errors = paged_activities(
        lambda request: httpx.Response(200, json=activity_page(0, 0, [])), monkeypatch)
    assert payload == {"activities": []} and coverage["complete"] and not errors


def test_truncation_is_visible_in_profile_and_survives_schema_and_cache(monkeypatch):
    from app.schemas.molecule import ChemblResponse
    monkeypatch.setattr(chembl, "ACTIVITY_LIMIT", 2)
    monkeypatch.setattr(chembl, "MAX_ACTIVITY_PAGES", 2)
    def handler(request):
        resource = request.url.path.rsplit("/", 1)[-1]
        if resource == "molecule.json":
            data = {"molecules": [{"molecule_chembl_id": "CHEMBL25"}]}
        elif resource == "activity.json":
            offset = int(request.url.params["offset"])
            data = activity_page(offset, 7, [offset+1, offset+2])
        elif resource == "mechanism.json":
            data = {"mechanisms": []}
        elif resource == "drug_indication.json":
            data = {"drug_indications": []}
        else:
            data = {"molecules": []}
        return httpx.Response(200, json=data)
    profile = ChemblResponse.model_validate(run_fetch(handler, monkeypatch)).model_dump()
    assert profile["available"] and profile["partial"] and not profile["activity_coverage"]["complete"]
    cached, _ = transport.read_cache(transport.cache_key("CCO", "TESTKEY"))
    assert cached["activity_coverage"] == profile["activity_coverage"] and cached["partial"]


@pytest.mark.parametrize("bad_page", [activity_page(1, 3, [3]), activity_page(2, 4, [3]),
                                      activity_page(2, 3, [1]), activity_page(2, 3, []),
                                      {"activities": [{"activity_id": 3}]},
                                      activity_page(2, True, [3])])
def test_inconsistent_second_page_does_not_corrupt_saved_first_page(monkeypatch, bad_page):
    def handler(request):
        payload = activity_page(0, 3, [1, 2]) if request.url.params["offset"] == "0" else bad_page
        return httpx.Response(200, json=payload)
    payload, coverage, errors = paged_activities(handler, monkeypatch)
    assert [r["activity_id"] for r in payload["activities"]] == [1, 2]
    assert coverage["retrieved_rows"] == 2 and not coverage["complete"] and errors


def test_failed_later_activity_page_keeps_partial_data(monkeypatch):
    def handler(request):
        if request.url.params["offset"] != "0":
            return httpx.Response(500)
        return httpx.Response(200, json=activity_page(0, 3, [1, 2]))
    payload, coverage, errors = paged_activities(handler, monkeypatch)
    assert len(payload["activities"]) == 2 and not coverage["complete"]
    assert errors == ["activity: http_500"]


def test_malformed_collection_rows_do_not_reach_profile_parsers():
    async def scenario():
        async with transport.ChemblClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"mechanisms": [None, "bad"]}))) as client:
            assert await client.fetch("mechanism.json") is None
            assert client.failures == ["mechanism: invalid_response"]
    asyncio.run(scenario())


def test_legacy_cache_cannot_claim_complete_activity_coverage():
    from app.schemas.molecule import ChemblResponse
    key = transport.cache_key("CCO", "TESTKEY")
    profile = ChemblResponse(available=True, found=True, chembl_id="CHEMBL545").model_dump()
    transport.write_cache(key, profile)
    cached, _ = transport.read_cache(key)
    assert cached["partial"] and cached["activity_coverage"] is None
    assert "activity: legacy_cache_coverage_unknown" in cached["warnings"]


@pytest.mark.parametrize("changes", [dict(complete=True), dict(retrieved_rows=True),
                                     dict(pages=0), dict(limit_rows=1), dict(total_rows=1)])
def test_inconsistent_cached_coverage_is_rejected(changes):
    from app.schemas.molecule import ChemblResponse
    key = transport.cache_key("CCO", "TESTKEY")
    profile = ChemblResponse(available=True, found=True).model_dump()
    profile["activity_coverage"] = dict(dict(retrieved_rows=2, total_rows=3, pages=1,
                                             complete=False, limit_rows=8), **changes)
    transport.write_cache(key, profile)
    assert transport.read_cache(key) is None


def test_cached_incomplete_coverage_cannot_clear_partial_flag():
    from app.schemas.molecule import ChemblResponse
    key = transport.cache_key("CCO", "TESTKEY")
    profile = ChemblResponse(available=True, found=True, partial=False,
        activity_coverage=dict(retrieved_rows=2, total_rows=3, pages=1, complete=False, limit_rows=8)).model_dump()
    transport.write_cache(key, profile)
    cached, _ = transport.read_cache(key)
    assert cached["partial"]


@pytest.mark.parametrize("value", [True, 10**1000, "nan", "inf"])
def test_non_numeric_or_nonfinite_source_values_are_never_pchembl(value):
    assert chembl._to_float(value) is None
