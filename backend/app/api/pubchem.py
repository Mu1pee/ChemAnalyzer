"""Идентификация соединения в PubChem.

Три РАЗДЕЛЬНЫХ уровня проверки (их нельзя смешивать):
  exact         — та же структура с учётом стереохимии и изотопов;
  connectivity  — та же связность атомов, стереохимия/изотопы могут отличаться;
  similarity    — ПОХОЖИЕ вещества (Tanimoto ≥ порога); это НЕ то же вещество.

Название присваивается только при exact или connectivity. Если PubChem
недоступен, возвращается статус "unavailable" — отличный от "not_found".
"""

import asyncio

import httpx

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
TIMEOUT = httpx.Timeout(12.0, connect=5.0)
HEADERS = {"User-Agent": "ChemAnalyzerModern/3.0 (+desktop app)"}

LISTKEY_POLL_ATTEMPTS = 5
LISTKEY_POLL_DELAY = 1.0

SIMILARITY_THRESHOLD = 90
SIMILARITY_MAX = 6

FOUND = "found"
NOT_FOUND = "not_found"
UNAVAILABLE = "unavailable"
SKIPPED = "skipped"

MSG_UNAVAILABLE = "PubChem недоступен — локальный анализ выполнен."
MSG_NOT_FOUND = "Точное соединение не найдено."
MSG_CONNECTIVITY = (
    "Совпадение только по связности атомов: стереохимия или изотопы могут "
    "отличаться. Это не подтверждает тождество вещества."
)


class _Unavailable(Exception):
    """Сеть, таймаут или ошибка сервера — вывод о наличии вещества невозможен."""


def _empty_result() -> dict:
    return {
        "status": NOT_FOUND,
        "found": False,
        "match_type": None,
        "cid": None,
        "title": None,
        "iupac_name": None,
        "synonyms": [],
        "inchikey": None,
        "source": "PubChem",
        "source_url": None,
        "message": None,
        "checks": {"exact": SKIPPED, "connectivity": SKIPPED, "similarity": SKIPPED},
        "similar": [],
        "similarity_threshold": SIMILARITY_THRESHOLD,
    }


def _extract_cids(payload: dict) -> list[int]:
    cids = (payload or {}).get("IdentifierList", {}).get("CID", [])
    result = []
    for value in cids:
        try:
            cid = int(value)
        except (TypeError, ValueError):
            continue
        if cid > 0:  # PubChem возвращает [0], если совпадений нет
            result.append(cid)
    return result


async def _poll_listkey(client: httpx.AsyncClient, list_key: str) -> list[int]:
    url = f"{PUBCHEM_BASE}/compound/listkey/{list_key}/cids/JSON"
    for _ in range(LISTKEY_POLL_ATTEMPTS):
        await asyncio.sleep(LISTKEY_POLL_DELAY)
        try:
            response = await client.get(url)
        except httpx.HTTPError as error:
            raise _Unavailable() from error
        if response.status_code == 200:
            return _extract_cids(response.json())
        if response.status_code != 202:
            raise _Unavailable()
    raise _Unavailable()


async def _search(
    client: httpx.AsyncClient, operation: str, params: dict, smiles: str
) -> list[int]:
    """POST-поиск по SMILES (в теле, а не в URL: символы / \\ # + ломают путь)."""
    try:
        response = await client.post(
            f"{PUBCHEM_BASE}/compound/{operation}/smiles/cids/JSON",
            params=params,
            data={"smiles": smiles},
        )
        status = response.status_code
        if status == 200:
            return _extract_cids(response.json())
        if status == 404:
            return []
        if status == 202:
            list_key = response.json().get("Waiting", {}).get("ListKey")
            if list_key:
                return await _poll_listkey(client, list_key)
    except (httpx.HTTPError, ValueError, TypeError) as error:
        raise _Unavailable() from error
    raise _Unavailable()


async def _fetch_properties(
    client: httpx.AsyncClient, cids: list[int]
) -> dict[int, dict]:
    joined = ",".join(str(c) for c in cids)
    url = f"{PUBCHEM_BASE}/compound/cid/{joined}/property/IUPACName,Title,InChIKey/JSON"
    try:
        response = await client.get(url)
        if response.status_code == 200:
            items = response.json().get("PropertyTable", {}).get("Properties", [])
            return {int(i["CID"]): i for i in items if "CID" in i}
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        pass
    return {}


async def _fetch_synonyms(client: httpx.AsyncClient, cid: int) -> list[str]:
    url = f"{PUBCHEM_BASE}/compound/cid/{cid}/synonyms/JSON"
    try:
        response = await client.get(url)
        if response.status_code == 200:
            infos = response.json().get("InformationList", {}).get("Information", [])
            if infos and isinstance(infos[0].get("Synonym"), list):
                return [str(v) for v in infos[0]["Synonym"][:12]]
    except (httpx.HTTPError, ValueError, TypeError):
        pass
    return []


def _cid_url(cid: int) -> str:
    return f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}"


async def identify_by_smiles(smiles: str) -> dict:
    result = _empty_result()
    checks = result["checks"]

    async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as client:
        steps = [
            ("exact", "fastidentity", {"identity_type": "same_stereo_isotope"}),
            ("connectivity", "fastidentity", {"identity_type": "same_connectivity"}),
            (
                "similarity",
                "fastsimilarity_2d",
                {"Threshold": SIMILARITY_THRESHOLD, "MaxRecords": SIMILARITY_MAX},
            ),
        ]

        matched_cid: int | None = None
        similar_cids: list[int] = []
        unavailable = False

        for name, operation, params in steps:
            # Точное или связностное совпадение уже есть — остальное не нужно.
            if matched_cid is not None:
                break
            # Сервис не отвечает — не тратим время на оставшиеся запросы.
            if unavailable:
                checks[name] = UNAVAILABLE
                continue

            try:
                cids = await _search(client, operation, params, smiles)
            except _Unavailable:
                unavailable = True
                checks[name] = UNAVAILABLE
                continue

            if name == "similarity":
                similar_cids = cids
                checks[name] = FOUND if cids else NOT_FOUND
            elif cids:
                matched_cid = cids[0]
                checks[name] = FOUND
                result["match_type"] = name
            else:
                checks[name] = NOT_FOUND

        if matched_cid is not None:
            props, synonyms = await asyncio.gather(
                _fetch_properties(client, [matched_cid]),
                _fetch_synonyms(client, matched_cid),
            )
            record = props.get(matched_cid, {})
            result.update(
                {
                    "status": FOUND,
                    "found": True,
                    "cid": matched_cid,
                    "title": record.get("Title"),
                    "iupac_name": record.get("IUPACName"),
                    "inchikey": record.get("InChIKey"),
                    "synonyms": synonyms,
                    "source_url": _cid_url(matched_cid),
                    "message": MSG_CONNECTIVITY
                    if result["match_type"] == "connectivity"
                    else None,
                }
            )
            return result

        if similar_cids:
            props = await _fetch_properties(client, similar_cids)
            result["similar"] = [
                {
                    "cid": cid,
                    "title": props.get(cid, {}).get("Title"),
                    "iupac_name": props.get(cid, {}).get("IUPACName"),
                    "inchikey": props.get(cid, {}).get("InChIKey"),
                    "source_url": _cid_url(cid),
                }
                for cid in similar_cids
            ]

    if unavailable:
        result["status"] = UNAVAILABLE
        result["message"] = MSG_UNAVAILABLE
    else:
        result["status"] = NOT_FOUND
        result["message"] = MSG_NOT_FOUND + (
            " Найдены только похожие вещества — это НЕ то же самое соединение."
            if result["similar"]
            else ""
        )
    return result
