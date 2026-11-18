"""Экспериментальные данные о биологической активности из ChEMBL.

Используется публичный REST API ChEMBL:
https://www.ebi.ac.uk/chembl/api/data
"""

import asyncio
import math
from urllib.parse import quote

import httpx
from .chembl_sqlite import configured_database, read_local_profile
from .chembl_transport import (
    ChemblClient, FRESH_SECONDS, cache_key, is_complete_snapshot, read_cache, timestamp, write_cache,
)

CHEMBL_BASE = "https://www.ebi.ac.uk/chembl/api/data"
CHEMBL_COMPOUND_URL = "https://www.ebi.ac.uk/chembl/compound_report_card"
TIMEOUT = httpx.Timeout(22.0, connect=5.0)
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ChemAnalyzerModern/3.2 (+local app)",
}

SIMILARITY_CUTOFF = 70
SIMILAR_LIMIT = 8
ACTIVITY_LIMIT = 500
MAX_ACTIVITY_PAGES = 4
TOP_TARGETS = 15
ACTIVITY_TYPES = "IC50,Ki,Kd,EC50,Potency"


def _to_float(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


async def _get_json(
    client: ChemblClient, path: str, params: dict | None = None
) -> dict | None:
    return await client.fetch(path, params)


# ---------- чистые функции обработки ответов (без сети) ----------


def parse_molecule(payload: dict | None) -> dict | None:
    molecules = (payload or {}).get("molecules") or []
    if not molecules:
        return None
    molecule = molecules[0]
    chembl_id = molecule.get("molecule_chembl_id")
    if not chembl_id:
        return None
    return {
        "chembl_id": chembl_id,
        "name": molecule.get("pref_name"),
        "max_phase": _to_float(molecule.get("max_phase")),
    }


def parse_mechanisms(payload: dict | None) -> list[dict]:
    result = []
    seen = set()
    for item in (payload or {}).get("mechanisms") or []:
        action = item.get("mechanism_of_action")
        target_id = item.get("target_chembl_id")
        key = (action, target_id)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "molecule_id": item.get("molecule_chembl_id"),
                "action": action,
                "action_type": item.get("action_type"),
                "target_id": target_id,
                "target_name": None,
            }
        )
    return result


def parse_indications(payload: dict | None) -> list[dict]:
    best: dict[str, float | None] = {}
    for item in (payload or {}).get("drug_indications") or []:
        name = item.get("mesh_heading") or item.get("efo_term")
        if not name:
            continue
        phase = _to_float(item.get("max_phase_for_ind"))
        previous = best.get(name)
        if name not in best or (phase or 0) > (previous or 0):
            best[name] = phase

    items = [{"name": n, "max_phase": p} for n, p in best.items()]
    items.sort(key=lambda i: (-(i["max_phase"] or 0), i["name"]))
    return items[:15]


def aggregate_targets(payload: dict | None) -> list[dict]:
    """Группирует измерения активности по мишеням, берёт лучший pChEMBL."""
    targets: dict[str, dict] = {}

    for item in (payload or {}).get("activities") or []:
        target_id = item.get("target_chembl_id")
        pchembl = _to_float(item.get("pchembl_value"))
        if not target_id or pchembl is None:
            continue

        entry = targets.setdefault(
            target_id,
            {
                "target_id": target_id,
                "target_name": item.get("target_pref_name"),
                "organism": item.get("target_organism"),
                "best_pchembl": pchembl,
                "measurements": 0,
                "activity_types": [],
            },
        )
        entry["measurements"] += 1
        entry["best_pchembl"] = max(entry["best_pchembl"], pchembl)
        activity_type = item.get("standard_type")
        if activity_type and activity_type not in entry["activity_types"]:
            entry["activity_types"].append(activity_type)

    ranked = sorted(
        targets.values(),
        key=lambda t: (-t["best_pchembl"], t["target_id"]),
    )
    for entry in ranked:
        entry["best_pchembl"] = round(entry["best_pchembl"], 2)
    return ranked[:TOP_TARGETS]


def parse_target_names(payload: dict | None) -> dict[str, str]:
    names = {}
    for item in (payload or {}).get("targets") or []:
        target_id = item.get("target_chembl_id")
        if target_id and item.get("pref_name"):
            names[target_id] = item["pref_name"]
    return names


def parse_similar(payload: dict | None, exclude_id: str | None) -> list[dict]:
    result = []
    for item in (payload or {}).get("molecules") or []:
        chembl_id = item.get("molecule_chembl_id")
        similarity = _to_float(item.get("similarity"))
        if not chembl_id or chembl_id == exclude_id or similarity is None:
            continue
        result.append(
            {
                "chembl_id": chembl_id,
                "name": item.get("pref_name"),
                "similarity": round(similarity, 1),
                "max_phase": _to_float(item.get("max_phase")),
                "mechanisms": [],
            }
        )
    result.sort(key=lambda m: -m["similarity"])
    return result[:SIMILAR_LIMIT]


# ---------- запросы ----------


async def _fetch_mechanisms(
    client: ChemblClient, ids: list[str]
) -> list[dict]:
    if not ids:
        return []
    joined = ",".join(ids)
    payload = await _get_json(
        client,
        "mechanism.json",
        {"molecule_chembl_id__in": joined, "limit": 50},
    )
    mechanisms = parse_mechanisms(payload)
    if payload is not None and not mechanisms:
        # Механизмы индексируются по родительской молекуле (соли/пролекарства).
        payload = await _get_json(
            client,
            "mechanism.json",
            {"parent_molecule_chembl_id__in": joined, "limit": 50},
        )
        mechanisms = parse_mechanisms(payload)
    return mechanisms


async def _fetch_target_names(
    client: ChemblClient, ids: list[str]
) -> dict[str, str]:
    ids = [i for i in dict.fromkeys(ids) if i]
    if not ids:
        return {}
    payload = await _get_json(
        client,
        "target.json",
        {"target_chembl_id__in": ",".join(ids), "limit": len(ids)},
    )
    return parse_target_names(payload)


async def _fetch_named_mechanisms(client: ChemblClient, ids: list[str]) -> list[dict]:
    mechanisms = await _fetch_mechanisms(client, ids)
    names = await _fetch_target_names(client, [item["target_id"] for item in mechanisms])
    for item in mechanisms:
        item["target_name"] = names.get(item["target_id"])
    return mechanisms


async def _fetch_activities(client: ChemblClient, molecule_id: str):
    """Fetch bounded, ordered source pages and retain explicit completeness evidence.

    Reconstruct offsets locally; never follow an upstream next-page URL. A
    changed total, inconsistent page or duplicate row cannot be called complete.
    All requests share the client's existing wall-clock deadline.
    """
    rows, seen, total, pages = [], set(), None, 0
    complete = False
    for _ in range(MAX_ACTIVITY_PAGES):
        payload = await _get_json(client, "activity.json", {
            "molecule_chembl_id": molecule_id, "standard_type__in": ACTIVITY_TYPES,
            "limit": ACTIVITY_LIMIT, "offset": len(rows), "order_by": "activity_id",
        })
        if payload is None:
            break
        page = payload["activities"]
        meta = payload.get("page_meta")
        valid_int = lambda value: isinstance(value, int) and not isinstance(value, bool) and value >= 0
        if (not isinstance(meta, dict) or not valid_int(meta.get("total_count"))
                or not valid_int(meta.get("offset")) or meta["offset"] != len(rows)
                or len(page) > ACTIVITY_LIMIT or len(rows) + len(page) > meta["total_count"]
                or (not page and len(rows) < meta["total_count"])):
            client.failures.append("activity: invalid_pagination")
            break
        if total is not None and total != meta["total_count"]:
            client.failures.append("activity: source_changed_during_pagination")
            break
        total = meta["total_count"]
        identifiers = [row.get("activity_id") for row in page]
        if (any(not valid_int(value) for value in identifiers)
                or len(set(identifiers)) != len(identifiers) or seen.intersection(identifiers)):
            client.failures.append("activity: duplicate_or_invalid_record_id")
            break
        rows.extend(page)
        seen.update(identifiers)
        pages += 1
        if len(rows) == total:
            complete = True
            break
    if not complete and pages == MAX_ACTIVITY_PAGES:
        client.failures.append(f"activity: row_limit ({len(rows)} of {total})")
    coverage = dict(retrieved_rows=len(rows), total_rows=total, pages=pages,
                    complete=complete, limit_rows=ACTIVITY_LIMIT * MAX_ACTIVITY_PAGES)
    return {"activities": rows}, coverage


async def _fetch_exact_match(client: ChemblClient, inchikey: str | None) -> tuple[bool, dict | None]:
    if not inchikey:
        return False, None
    payload = await _get_json(client, "molecule.json", {
        "molecule_structures__standard_inchi_key": inchikey,
        "limit": 1,
    })
    return payload is not None, parse_molecule(payload)


async def _fetch_exact_details(
    client: ChemblClient, exact_match: asyncio.Task[tuple[bool, dict | None]]
) -> dict:
    _, molecule = await exact_match
    if not molecule:
        return {}
    molecule_id = molecule["chembl_id"]
    mechanisms, indications, activities = await asyncio.gather(
        _fetch_named_mechanisms(client, [molecule_id]),
        _get_json(client, "drug_indication.json", {"molecule_chembl_id": molecule_id, "limit": 100}),
        _fetch_activities(client, molecule_id),
    )
    activity_payload, coverage = activities
    return {
        "found": True,
        **molecule,
        "source_url": f"{CHEMBL_COMPOUND_URL}/{molecule_id}",
        "mechanisms": mechanisms,
        "indications": parse_indications(indications),
        "targets": aggregate_targets(activity_payload),
        "activity_coverage": coverage,
    }


async def _fetch_analog_details(
    client: ChemblClient, smiles: str, exact_match: asyncio.Task[tuple[bool, dict | None]]
) -> list[dict] | None:
    path = f"similarity/{quote(smiles, safe='')}/{SIMILARITY_CUTOFF}.json"
    payload = await _get_json(client, path, {"limit": SIMILAR_LIMIT + 2})
    if payload is None:
        return None
    _, molecule = await exact_match
    similar = parse_similar(payload, molecule["chembl_id"] if molecule else None)
    mechanisms = await _fetch_named_mechanisms(client, [row["chembl_id"] for row in similar])
    by_molecule: dict[str, list[dict]] = {}
    for mechanism in mechanisms:
        by_molecule.setdefault(mechanism["molecule_id"], []).append(mechanism)
    for row in similar:
        row["mechanisms"] = by_molecule.get(row["chembl_id"], [])[:3]
    return similar


def _saved_profile(snapshot: dict, warnings: list[str], message: str) -> dict:
    return {
        **snapshot,
        "cached": True,
        "stale": True,
        "message": message,
        "warnings": list(dict.fromkeys(snapshot["warnings"] + warnings)),
    }


def _first_activity_failed(profile: dict) -> bool:
    coverage = profile["activity_coverage"]
    return (profile["found"] and coverage is not None and not coverage["complete"]
            and coverage["retrieved_rows"] == 0
            and any(issue.startswith("activity:") for issue in profile["warnings"]))


def _recover_missing_activity(key: str, profile: dict) -> dict | None:
    if not _first_activity_failed(profile):
        return None
    saved = read_cache(key, prefer_complete=True)
    if saved is None:
        return None
    snapshot, _ = saved
    if (not is_complete_snapshot(snapshot) or snapshot["chembl_id"] != profile["chembl_id"]
            or snapshot["activity_coverage"]["retrieved_rows"] == 0):
        return None
    return _saved_profile(
        snapshot, profile["warnings"],
        "Не удалось загрузить измерения ChEMBL. Показан полный сохранённый профиль. Проверьте дату получения.",
    )


async def _recover_local_profile(profile: dict, inchikey: str | None) -> dict | None:
    # Empty authoritative measurements and useful partial measurements keep
    # their own live source. The local report is one separate dated snapshot.
    exact_lookup_failed = not profile["found"] and any(issue.startswith("molecule:") for issue in profile["warnings"])
    if not inchikey or not (exact_lookup_failed or _first_activity_failed(profile)):
        return None
    path = configured_database()
    if path is None or not path.is_file():
        return None
    limit = ACTIVITY_LIMIT * MAX_ACTIVITY_PAGES
    snapshot = await asyncio.to_thread(read_local_profile, path, inchikey, tuple(ACTIVITY_TYPES.split(",")), limit)
    if snapshot is None or (profile["found"] and profile["chembl_id"] != snapshot.molecule["chembl_id"]):
        return None
    molecule_id = snapshot.molecule["chembl_id"]
    size = len(snapshot.activities)
    coverage = dict(retrieved_rows=size, total_rows=snapshot.total_activities,
                    pages=1, complete=size == snapshot.total_activities, limit_rows=limit)
    warnings = list(dict.fromkeys(profile["warnings"] + ["similarity: offline"]))
    if not coverage["complete"]:
        warnings.append(f"activity: row_limit ({size} of {snapshot.total_activities})")
    return {
        **profile, **snapshot.molecule, "available": True, "found": True,
        "max_phase": _to_float(snapshot.molecule["max_phase"]),
        "source_url": f"{CHEMBL_COMPOUND_URL}/{molecule_id}",
        "source": "ChEMBL SQLite", "offline_release": snapshot.release,
        "offline_release_date": snapshot.release_date,
        "cached": False, "stale": False, "partial": True, "retrieved_at": None,
        "mechanisms": snapshot.mechanisms, "indications": parse_indications({"drug_indications": snapshot.indications}),
        "targets": aggregate_targets({"activities": snapshot.activities}), "similar": [],
        "warnings": warnings, "activity_coverage": coverage,
        "message": "Данные из локальной копии ChEMBL. Поиск аналогов доступен через онлайн-сервис.",
    }


async def fetch_chembl_profile(smiles: str, inchikey: str | None) -> dict:
    key = cache_key(smiles, inchikey)
    cached = read_cache(key)
    if cached and cached[1] < (300 if cached[0]["partial"] else FRESH_SECONDS):
        result = cached[0]
        result["cached"] = True
        return _recover_missing_activity(key, result) or await _recover_local_profile(result, inchikey) or result
    profile: dict = {
        "available": False,
        "found": False,
        "chembl_id": None,
        "name": None,
        "max_phase": None,
        "source_url": None,
        "mechanisms": [],
        "indications": [],
        "targets": [],
        "similar": [],
        "message": None,
        "source": "ChEMBL",
        "cached": False,
        "stale": False,
        "partial": False,
        "retrieved_at": None,
        "warnings": [],
        "activity_coverage": None,
    }

    async with ChemblClient(timeout=TIMEOUT, headers=HEADERS) as client:
        # Start activity pages as soon as the exact ID is known, even when
        # the similarity endpoint is slow or retrying within the same budget.
        async with asyncio.TaskGroup() as requests:
            exact_match = requests.create_task(_fetch_exact_match(client, inchikey))
            exact_details = requests.create_task(_fetch_exact_details(client, exact_match))
            analog_details = requests.create_task(_fetch_analog_details(client, smiles, exact_match))
        exact_available, _ = exact_match.result()
        similar = analog_details.result()
        profile.update(exact_details.result())
        profile["available"] = exact_available or similar is not None
        profile["similar"] = similar or []
        profile["warnings"] = list(client.failures)

    profile["partial"] = bool(profile["warnings"])

    if not profile["available"]:
        # A newer partial refresh must not erase the last complete response.
        # Display one dated snapshot, never a mixture of observations.
        cached = read_cache(key, prefer_complete=True)
        if cached and is_complete_snapshot(cached[0]):
            return _saved_profile(
                cached[0], profile["warnings"],
                "ChEMBL сейчас не отвечает. Показана сохранённая копия; проверьте дату получения.",
            )
        offline = await _recover_local_profile(profile, inchikey)
        if offline:
            return offline
        if cached:
            return _saved_profile(
                cached[0], profile["warnings"],
                "ChEMBL сейчас не отвечает. Показана сохранённая копия; проверьте дату получения.",
            )
        profile["message"] = (
            "Не удалось получить ответ ChEMBL: " + "; ".join(profile["warnings"]) + ". Повторите запрос позже."
        )
        return profile

    if profile["partial"]:
        profile["message"] = "ChEMBL ответил частично. Часть данных не загрузилась или ограничена объёмом: " + "; ".join(profile["warnings"])
    elif not profile["found"] and not similar:
        profile["message"] = (
            "Соединение и близкие аналоги в ChEMBL не найдены."
        )
    elif not profile["found"]:
        profile["message"] = (
            "Точного совпадения в ChEMBL нет — показаны близкие аналоги."
        )

    profile["retrieved_at"] = timestamp()
    write_cache(key, profile)
    return _recover_missing_activity(key, profile) or await _recover_local_profile(profile, inchikey) or profile
