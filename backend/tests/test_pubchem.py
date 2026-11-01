"""Идентификация в PubChem: три уровня совпадения и поведение при сбоях.

Сеть не используется: httpx.AsyncClient подменяется заглушкой.
"""

import asyncio

import pytest

httpx = pytest.importorskip("httpx")

from app.api import pubchem  # noqa: E402


class Resp:
    def __init__(self, code, js=None):
        self.status_code = code
        self._js = js

    def json(self):
        if isinstance(self._js, Exception):
            raise self._js
        return self._js


def install(monkeypatch, handler):
    calls = []

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, params=None, data=None):
            calls.append(("POST", url.rsplit("/compound/", 1)[1], dict(params or {})))
            return handler("post", url, params or {})

        async def get(self, url):
            calls.append(("GET", url, {}))
            return handler("get", url, {})

    monkeypatch.setattr(pubchem.httpx, "AsyncClient", Client)
    monkeypatch.setattr(pubchem, "LISTKEY_POLL_DELAY", 0)
    return calls


def run(smiles="CCO"):
    return asyncio.run(pubchem.identify_by_smiles(smiles))


def props(cid=702):
    return Resp(200, {"PropertyTable": {"Properties": [
        {"CID": cid, "Title": "Ethanol", "IUPACName": "ethanol", "InChIKey": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"}]}})


def test_exact_match_skips_other_levels(monkeypatch):
    def handler(kind, url, params):
        if kind == "post":
            return Resp(200, {"IdentifierList": {"CID": [702]}})
        if "property" in url:
            return props()
        return Resp(200, {"InformationList": {"Information": [{"Synonym": ["ethanol"]}]}})

    calls = install(monkeypatch, handler)
    r = run()
    assert r["status"] == "found" and r["match_type"] == "exact" and r["cid"] == 702
    assert r["title"] == "Ethanol" and r["message"] is None
    assert r["checks"] == {"exact": "found", "connectivity": "skipped", "similarity": "skipped"}
    assert [c for c in calls if c[0] == "POST"][0][2]["identity_type"] == "same_stereo_isotope"
    assert len([c for c in calls if c[0] == "POST"]) == 1


def test_connectivity_match_is_flagged_not_exact(monkeypatch):
    def handler(kind, url, params):
        if kind == "post":
            if params.get("identity_type") == "same_stereo_isotope":
                return Resp(404, {})
            return Resp(200, {"IdentifierList": {"CID": [5]}})
        return props(5) if "property" in url else Resp(404, {})

    install(monkeypatch, handler)
    r = run()
    assert r["status"] == "found" and r["match_type"] == "connectivity"
    assert "не подтверждает тождество" in r["message"]
    assert r["checks"]["exact"] == "not_found" and r["checks"]["connectivity"] == "found"


def test_only_similar_is_not_found_and_never_named(monkeypatch):
    def handler(kind, url, params):
        if kind == "post":
            if "Threshold" in params:
                return Resp(200, {"IdentifierList": {"CID": [11, 12]}})
            return Resp(200, {"IdentifierList": {"CID": [0]}})  # «нет совпадений»
        return Resp(200, {"PropertyTable": {"Properties": [
            {"CID": 11, "Title": "Similar A"}, {"CID": 12, "Title": "Similar B"}]}})

    install(monkeypatch, handler)
    r = run()
    assert r["status"] == "not_found" and r["found"] is False
    assert r["title"] is None and r["cid"] is None
    assert [s["cid"] for s in r["similar"]] == [11, 12]
    assert "НЕ то же самое" in r["message"]
    assert r["checks"] == {"exact": "not_found", "connectivity": "not_found", "similarity": "found"}


def test_nothing_found(monkeypatch):
    install(monkeypatch, lambda k, u, p: Resp(404, {}))
    r = run()
    assert r["status"] == "not_found" and r["message"] == "Точное соединение не найдено."
    assert r["similar"] == []


def test_network_failure_is_unavailable_not_not_found(monkeypatch):
    def handler(kind, url, params):
        raise httpx.HTTPError("нет сети")

    calls = install(monkeypatch, handler)
    r = run()
    assert r["status"] == "unavailable" and r["found"] is False
    assert r["message"] == "PubChem недоступен — локальный анализ выполнен."
    assert set(r["checks"].values()) == {"unavailable"}
    # После первого сбоя остальные запросы не отправляются (нет трёх таймаутов подряд).
    assert len(calls) == 1


@pytest.mark.parametrize("code", [429, 500, 503])
def test_server_errors_are_unavailable(monkeypatch, code):
    install(monkeypatch, lambda k, u, p: Resp(code, {}))
    assert run()["status"] == "unavailable"


def test_listkey_polling(monkeypatch):
    state = {"n": 0}

    def handler(kind, url, params):
        if kind == "post":
            return Resp(202, {"Waiting": {"ListKey": "abc"}})
        if "listkey" in url:
            state["n"] += 1
            return Resp(202, {}) if state["n"] < 2 else Resp(200, {"IdentifierList": {"CID": [2244]}})
        return props(2244)

    install(monkeypatch, handler)
    r = run()
    assert r["status"] == "found" and r["cid"] == 2244


def test_listkey_never_ready_is_unavailable(monkeypatch):
    def handler(kind, url, params):
        return Resp(202, {"Waiting": {"ListKey": "abc"}}) if kind == "post" else Resp(202, {})

    install(monkeypatch, handler)
    assert run()["status"] == "unavailable"


def test_details_failure_keeps_match(monkeypatch):
    def handler(kind, url, params):
        if kind == "post":
            return Resp(200, {"IdentifierList": {"CID": [702]}})
        raise httpx.HTTPError("обрыв после поиска")

    install(monkeypatch, handler)
    r = run()
    assert r["status"] == "found" and r["cid"] == 702 and r["title"] is None
