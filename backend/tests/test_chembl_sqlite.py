"""Software fixtures for ChEMBL fallback. All measurements here are test-only."""

import asyncio
import hashlib
import sqlite3

import httpx
import pytest

from app.api import chembl, chembl_transport
from app.schemas.molecule import ChemblResponse

SMILES = "CC(=O)Oc1ccccc1C(=O)O"
INCHIKEY = "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"


@pytest.fixture
def offline_database(tmp_path, monkeypatch):
    root = tmp_path / "fresh-profile"
    monkeypatch.setenv("CHEMANALYZER_DATA_DIR", str(root))
    monkeypatch.delenv("CHEMANALYZER_CHEMBL_SQLITE", raising=False)
    chembl_transport._memory.clear()
    path = root / "chembl" / "chembl_37.db"
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE version (name TEXT, creation_date TEXT);
            INSERT INTO version VALUES ('ChEMBL_37', '2026-05-01 00:00:00');
            CREATE TABLE compound_structures (molregno INTEGER PRIMARY KEY, standard_inchi_key TEXT);
            CREATE TABLE molecule_dictionary (molregno INTEGER PRIMARY KEY, chembl_id TEXT, pref_name TEXT, max_phase REAL);
            INSERT INTO molecule_dictionary VALUES (1,'CHEMBL25','TECHNICAL FIXTURE',4),(2,'CHEMBL20',NULL,NULL);
            CREATE TABLE activities (activity_id INTEGER PRIMARY KEY, assay_id INTEGER, molregno INTEGER,
                                     standard_type TEXT, pchembl_value REAL);
            INSERT INTO activities VALUES
                (1,10,1,'IC50',6.5),(2,10,1,'EC50',7.0),(3,10,1,'Ki',NULL),
                (4,20,1,'Kd',8.0),(5,10,1,'Excluded type',9.0),(6,10,2,'IC50',10.0);
            CREATE TABLE assays (assay_id INTEGER PRIMARY KEY, tid INTEGER);
            INSERT INTO assays VALUES (10,5),(20,NULL);
            CREATE TABLE target_dictionary (tid INTEGER PRIMARY KEY, chembl_id TEXT, pref_name TEXT, organism TEXT);
            INSERT INTO target_dictionary VALUES (5,'CHEMBL100','TECHNICAL TARGET','Technical organism');
            CREATE TABLE drug_indication (drugind_id INTEGER, molregno INTEGER, mesh_heading TEXT,
                                          efo_term TEXT, max_phase_for_ind REAL);
            INSERT INTO drug_indication VALUES (1,1,'TECHNICAL INDICATION',NULL,4);
            CREATE TABLE molecule_hierarchy (molregno INTEGER PRIMARY KEY, parent_molregno INTEGER);
            INSERT INTO molecule_hierarchy VALUES (1,2),(2,2);
            CREATE TABLE drug_mechanism (mec_id INTEGER, molregno INTEGER, tid INTEGER,
                                         mechanism_of_action TEXT, action_type TEXT);
            INSERT INTO drug_mechanism VALUES (1,2,5,'TECHNICAL MECHANISM','INHIBITOR');
        """)
        db.execute("INSERT INTO compound_structures VALUES (1,?)", (INCHIKEY,))
    return root, path


def fetch(monkeypatch, exact_status, activity_status=500, analog_status=500, live_id="CHEMBL25", live_rows=()):
    def handler(request):
        if request.url.path.endswith("/molecule.json"):
            return httpx.Response(exact_status, json={"molecules": [{"molecule_chembl_id": live_id}] if live_id else []})
        if "/similarity/" in request.url.path:
            return httpx.Response(analog_status, json={"molecules": []})
        if request.url.path.endswith("/activity.json"):
            return httpx.Response(activity_status, json={
                "activities": list(live_rows), "page_meta": {"offset": 0, "total_count": len(live_rows)},
            })
        if request.url.path.endswith("/mechanism.json"):
            return httpx.Response(200, json={"mechanisms": []})
        if request.url.path.endswith("/drug_indication.json"):
            return httpx.Response(200, json={"drug_indications": []})
        pytest.fail(f"Unexpected endpoint: {request.url.path}")

    factory = chembl_transport.ChemblClient
    monkeypatch.setattr(chembl, "ChemblClient", lambda **kw: factory(
        transport=httpx.MockTransport(handler), **kw))
    return ChemblResponse.model_validate(asyncio.run(chembl.fetch_chembl_profile(SMILES, INCHIKEY))).model_dump()


@pytest.mark.parametrize("exact_status, analog_status", [(500,500), (500,200), (200,200)])
def test_fresh_profile_recovers_exact_data_from_one_local_release(
    offline_database, monkeypatch, exact_status, analog_status,
):
    root, db = offline_database
    before = hashlib.sha256(db.read_bytes()).digest()
    profile = fetch(monkeypatch, exact_status, analog_status=analog_status)
    assert profile["found"] and profile["available"] and profile["partial"]
    assert profile["offline_release"] == "ChEMBL 37"
    assert profile["offline_release_date"] == "2026-05-01"
    assert not profile["cached"] and profile["retrieved_at"] is None
    assert profile["chembl_id"] == "CHEMBL25" and not profile["similar"]
    assert profile["activity_coverage"]["complete"]
    assert profile["activity_coverage"]["retrieved_rows"] == 4
    assert profile["targets"][0]["measurements"] == 2
    assert profile["targets"][0]["best_pchembl"] == 7
    assert profile["targets"][0]["target_name"] == "TECHNICAL TARGET"
    assert profile["targets"][0]["organism"] == "Technical organism"
    assert profile["indications"][0]["name"] == "TECHNICAL INDICATION"
    assert profile["mechanisms"][0]["target_name"] == "TECHNICAL TARGET"
    assert "similarity: offline" in profile["warnings"]
    assert hashlib.sha256(db.read_bytes()).digest() == before
    result = chembl_transport.read_cache(chembl_transport.cache_key(SMILES, INCHIKEY))
    assert result is None or not result[0]["offline_release"]


@pytest.mark.parametrize("live_id, activity_status", [(None,500), ("CHEMBL25",200), ("CHEMBL99",500)])
def test_offline_does_not_replace_online_absence_empty_experiment_or_conflicting_identity(
    offline_database, monkeypatch, live_id, activity_status,
):
    profile = fetch(monkeypatch, 200, activity_status=activity_status, analog_status=200, live_id=live_id)
    assert profile["offline_release"] is None
    assert profile["chembl_id"] == live_id


def test_offline_reports_limit_instead_of_claiming_complete_coverage(offline_database, monkeypatch):
    monkeypatch.setattr(chembl, "ACTIVITY_LIMIT", 1)
    monkeypatch.setattr(chembl, "MAX_ACTIVITY_PAGES", 2)
    profile = fetch(monkeypatch, 500)
    coverage = profile["activity_coverage"]
    assert coverage["total_rows"] == 4 and coverage["retrieved_rows"] == 2 and not coverage["complete"]
    assert "activity: row_limit (2 of 4)" in profile["warnings"]


@pytest.mark.parametrize("bad_snapshot", ["unsupported_version", "ambiguous_exact_identity", "missing_database"])
def test_unusable_snapshot_does_not_mask_online_failure(offline_database, monkeypatch, bad_snapshot):
    _, path = offline_database
    if bad_snapshot == "missing_database":
        monkeypatch.setenv("CHEMANALYZER_CHEMBL_SQLITE", str(path.with_name("missing.db")))
    else:
        with sqlite3.connect(path) as db:
            if bad_snapshot == "unsupported_version":
                db.execute("UPDATE version SET name='ChEMBL_36'")
            else:
                db.execute("INSERT INTO compound_structures VALUES (2,?)", (INCHIKEY,))
    profile = fetch(monkeypatch, 500)
    assert not profile["available"] and not profile["found"]
    assert profile["offline_release"] is None
    assert "molecule: http_500" in profile["warnings"]
