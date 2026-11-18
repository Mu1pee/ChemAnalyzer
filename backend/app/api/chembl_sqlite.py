"""Exact compound lookup in the optional official ChEMBL SQLite release."""

from contextlib import closing
from dataclasses import dataclass
from datetime import date
import logging
import os
from pathlib import Path
import re
import sqlite3
import time

from app import config

logger = logging.getLogger(__name__)
INCHIKEY = re.compile(r"[A-Z]{14}-[A-Z]{10}-[A-Z]")
CHEMBL_ID = re.compile(r"CHEMBL[0-9]+")
RELEASE = re.compile(r"ChEMBL_([1-9][0-9]*)", re.IGNORECASE)
QUERY_SECONDS = 5


@dataclass
class LocalProfile:
    release: str
    release_date: str
    molecule: dict
    activities: list[dict]
    total_activities: int
    mechanisms: list[dict]
    indications: list[dict]


def configured_database() -> Path | None:
    override = os.environ.get("CHEMANALYZER_CHEMBL_SQLITE", "").strip()
    if override:
        path = Path(override)
        return path if path.is_absolute() else None
    data = config.data_dir()
    return data / "chembl" / "chembl_37.db" if data else None


def _release(db: sqlite3.Connection) -> tuple[str, str]:
    row = db.execute("SELECT name, creation_date FROM version ORDER BY creation_date DESC LIMIT 1").fetchone()
    if row is None or not isinstance(row["name"], str) or not isinstance(row["creation_date"], str):
        raise ValueError("Missing ChEMBL release metadata")
    match = RELEASE.fullmatch(row["name"].strip())
    if match is None or match[1] != "37":
        raise ValueError("Expected the official ChEMBL 37 SQLite release")
    released = date.fromisoformat(row["creation_date"][:10])
    return f"ChEMBL {match[1]}", released.isoformat()


def _dict_rows(db: sqlite3.Connection, sql: str, values: tuple) -> list[dict]:
    return [dict(row) for row in db.execute(sql, values)]


def _mechanisms(db: sqlite3.Connection, molregno: int) -> list[dict]:
    query = """
        SELECT md.chembl_id AS molecule_id, dm.mechanism_of_action AS action, dm.action_type,
               td.chembl_id AS target_id, td.pref_name AS target_name
        FROM drug_mechanism AS dm
        JOIN molecule_dictionary AS md ON dm.molregno = md.molregno
        LEFT JOIN target_dictionary AS td ON dm.tid = td.tid
        WHERE dm.molregno = ? ORDER BY dm.mec_id LIMIT 50
    """
    rows = _dict_rows(db, query, (molregno,))
    if not rows:
        parent = db.execute(
            "SELECT parent_molregno FROM molecule_hierarchy WHERE molregno = ?", (molregno,)
        ).fetchone()
        if parent and parent[0] is not None and parent[0] != molregno:
            rows = _dict_rows(db, query, (parent[0],))
    unique = {}
    for row in rows:
        unique.setdefault((row["action"], row["target_id"]), row)
    return list(unique.values())


def read_local_profile(
    path: Path, inchikey: str, activity_types: tuple[str, ...], row_limit: int
) -> LocalProfile | None:
    if not INCHIKEY.fullmatch(inchikey):
        return None
    deadline = time.monotonic() + QUERY_SECONDS
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
            db.row_factory = sqlite3.Row
            db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 10_000)
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            release, release_date = _release(db)
            matches = _dict_rows(db, """
                SELECT md.molregno, md.chembl_id, md.pref_name AS name, md.max_phase
                FROM compound_structures AS cs
                JOIN molecule_dictionary AS md ON cs.molregno = md.molregno
                WHERE cs.standard_inchi_key = ? LIMIT 2
            """, (inchikey,))
            if len(matches) != 1:
                return None
            molecule = matches[0]
            compound_id = molecule["chembl_id"]
            if not isinstance(compound_id, str) or not CHEMBL_ID.fullmatch(compound_id):
                return None
            molregno = molecule.pop("molregno")
            slots = ",".join("?" for _ in activity_types)
            parameters = (molregno, *activity_types)
            total = db.execute(f"""
                SELECT COUNT(*) FROM activities WHERE molregno = ? AND standard_type IN ({slots})
            """, parameters).fetchone()[0]
            activities = _dict_rows(db, f"""
                SELECT act.activity_id, act.standard_type, act.pchembl_value,
                       td.chembl_id AS target_chembl_id, td.pref_name AS target_pref_name,
                       td.organism AS target_organism
                FROM activities AS act
                JOIN assays AS a ON act.assay_id = a.assay_id
                LEFT JOIN target_dictionary AS td ON a.tid = td.tid
                WHERE act.molregno = ? AND act.standard_type IN ({slots})
                ORDER BY act.activity_id LIMIT ?
            """, (*parameters, row_limit))
            if len(activities) != min(total, row_limit):
                raise ValueError("Local activity rows do not match the declared coverage")
            indications = _dict_rows(db, """
                SELECT mesh_heading, efo_term, max_phase_for_ind
                FROM drug_indication WHERE molregno = ? ORDER BY drugind_id LIMIT 100
            """, (molregno,))
            return LocalProfile(release, release_date, molecule, activities, total,
                                _mechanisms(db, molregno), indications)
    except (OSError, ValueError, sqlite3.Error) as error:
        logger.warning("Could not read the local ChEMBL snapshot: %s", type(error).__name__)
        return None
