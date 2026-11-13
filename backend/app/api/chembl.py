"""Экспериментальные данные о биологической активности из ChEMBL.

Используется публичный REST API ChEMBL:
https://www.ebi.ac.uk/chembl/api/data
"""

import asyncio
import math
from urllib.parse import quote

import httpx
from .chembl_transport import ChemblClient, cache_key, read_cache, write_cache, timestamp, FRESH_SECONDS

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


async def fetch_chembl_profile(smiles: str, inchikey: str | None) -> dict:
    key = cache_key(smiles, inchikey)
    cached = read_cache(key)
    if cached and cached[1] < (300 if cached[0]["partial"] else FRESH_SECONDS):
        result = cached[0]
        result["cached"] = True
        return result
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
        # 1. Точное совпадение по InChIKey.
        molecule = None
        async def exact():
            if not inchikey:
                return None
            return await _get_json(
                client,
                "molecule.json",
                {
                    "molecule_structures__standard_inchi_key": inchikey,
                    "limit": 1,
                },
            )
        payload, similar_payload = await asyncio.gather(
            exact(),
            _get_json(client, f"similarity/{quote(smiles, safe='')}/{SIMILARITY_CUTOFF}.json",
                      {"limit": SIMILAR_LIMIT + 2}),
        )
        profile["available"] = payload is not None
        molecule = parse_molecule(payload)
        own_id = molecule["chembl_id"] if molecule else None
        if similar_payload is not None:
            profile["available"] = True
        similar = parse_similar(similar_payload, own_id)

        tasks = [_fetch_mechanisms(client, [s["chembl_id"] for s in similar])]
        if molecule:
            tasks += [
                _fetch_mechanisms(client, [own_id]),
                _get_json(
                    client,
                    "drug_indication.json",
                    {"molecule_chembl_id": own_id, "limit": 100},
                ),
                _fetch_activities(client, own_id),
            ]

        results = await asyncio.gather(*tasks)
        similar_mechanisms = results[0]

        own_mechanisms: list[dict] = []
        if molecule:
            own_mechanisms = results[1]
            profile["indications"] = parse_indications(results[2])
            activity_payload, profile["activity_coverage"] = results[3]
            profile["targets"] = aggregate_targets(activity_payload)
            profile.update(
                {
                    "found": True,
                    "chembl_id": own_id,
                    "name": molecule["name"],
                    "max_phase": molecule["max_phase"],
                    "source_url": f"{CHEMBL_COMPOUND_URL}/{own_id}",
                }
            )

        # 3. Названия мишеней для механизмов.
        names = await _fetch_target_names(
            client,
            [m["target_id"] for m in own_mechanisms + similar_mechanisms],
        )
        profile["warnings"] = list(client.failures)

    for mechanism in own_mechanisms + similar_mechanisms:
        mechanism["target_name"] = names.get(mechanism["target_id"])

    profile["mechanisms"] = own_mechanisms

    by_molecule: dict[str, list[dict]] = {}
    for mechanism in similar_mechanisms:
        by_molecule.setdefault(mechanism["molecule_id"], []).append(
            mechanism
        )
    for item in similar:
        item["mechanisms"] = by_molecule.get(item["chembl_id"], [])[:3]
    profile["similar"] = similar
    profile["partial"] = bool(profile["warnings"])

    if not profile["available"]:
        if cached:
            result = cached[0]
            result.update(cached=True, stale=True,
                          message="ChEMBL сейчас не отвечает. Показана сохранённая копия; проверьте дату получения.",
                          warnings=profile["warnings"])
            return result
        profile["message"] = (
            "Не удалось получить ответ ChEMBL: " + "; ".join(profile["warnings"]) + ". Повторите запрос позже."
        )
    elif profile["partial"]:
        profile["message"] = "ChEMBL ответил частично. Часть данных не загрузилась или ограничена объёмом: " + "; ".join(profile["warnings"])
    elif not profile["found"] and not similar:
        profile["message"] = (
            "Соединение и близкие аналоги в ChEMBL не найдены."
        )
    elif not profile["found"]:
        profile["message"] = (
            "Точного совпадения в ChEMBL нет — показаны близкие аналоги."
        )

    if profile["available"]:
        profile["retrieved_at"] = timestamp()
        write_cache(key, profile)
    return profile
