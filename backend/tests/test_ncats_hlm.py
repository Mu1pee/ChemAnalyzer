"""Tiny validation fixtures only; no artificial scientific training data."""
import csv
import io
import json

import httpx
import pytest

from app.ai_research_agent import ncats_hlm as source
from app.ai_research_agent.config import TaskConfig
from app.ai_research_agent.security import checksum


def inputs(monkeypatch, changes=None):
    records = [dict(PUBCHEM_RESULT_TAG="1", PUBCHEM_SID="100", PUBCHEM_CID="200", PUBCHEM_EXT_DATASOURCE_SMILES="CCO",
                    PUBCHEM_ACTIVITY_OUTCOME="Active", Phenotype="Stable", **{"Half-life": "120", "Analysis Comment": "Class=0"}),
               dict(PUBCHEM_RESULT_TAG="2", PUBCHEM_SID="101", PUBCHEM_CID="201", PUBCHEM_EXT_DATASOURCE_SMILES="CCN",
                    PUBCHEM_ACTIVITY_OUTCOME="Inactive", Phenotype="Unstable", **{"Half-life": "15", "Analysis Comment": "Class=1"})]
    if changes:
        records[0].update(changes)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=source.FIELDS)
    writer.writeheader()
    for tag in ("RESULT_TYPE", "RESULT_DESCR", "RESULT_UNIT"):
        writer.writerow(dict(PUBCHEM_RESULT_TAG=tag, **{"Half-life": "MINUTES" if tag == "RESULT_UNIT" else "FLOAT"}))
    writer.writerows(records)
    raw = output.getvalue().encode()
    monkeypatch.setattr(source, "RAW_SHA256", checksum(raw))
    monkeypatch.setattr(source, "ROWS", 2)
    description = dict(PC_AssayContainer=[dict(assay=dict(descr=dict(aid=dict(id=source.AID, version=1), revision=1,
        aid_source=dict(db=dict(name="NCGC", source_id=dict(str="ADME-HLM1"))),
        protocol=["human liver microsomes; 0.5 mg/mL; 1 muM; pH 7.4; 37 degrees C"])))])
    return raw, json.dumps(description).encode()


def test_original_phenotype_and_pubchem_outcome_define_positive_stability(monkeypatch):
    text, evidence = source.parse_source(*inputs(monkeypatch))
    rows = list(csv.DictReader(io.StringIO(text)))
    assert [r["value"] for r in rows] == ["1", "0"]
    assert rows[0]["record_id"] == "SID:100" and "Class=0" in rows[0]["notes"]
    assert evidence["stable"] == 1 and evidence["unstable"] == 1
    # A reported 120-min value remains a binary phenotype, never a regression target.
    assert rows[0]["value"] != "120"


@pytest.mark.parametrize("changed", [
    {"PUBCHEM_ACTIVITY_OUTCOME": "Inactive"}, {"Analysis Comment": "Class=1"},
    {"Half-life": "30"}, {"Half-life": "15"}, {"Half-life": "nan"},
    {"Phenotype": "Unknown"}, {"PUBCHEM_SID": "101"},
])
def test_disagreements_boundaries_and_duplicate_ids_fail_closed(monkeypatch, changed):
    with pytest.raises(ValueError):
        source.parse_source(*inputs(monkeypatch, changed))


def test_changed_snapshot_or_rat_assay_cannot_be_imported(monkeypatch):
    raw, metadata = inputs(monkeypatch)
    with pytest.raises(ValueError, match="snapshot"):
        source.parse_source(raw + b"\n", metadata)
    changed = json.loads(metadata)
    changed["PC_AssayContainer"][0]["assay"]["descr"]["aid"]["id"] = 1508591
    with pytest.raises(ValueError, match="identity"):
        source.parse_source(raw, json.dumps(changed).encode())
    task = TaskConfig(**source.task_config())
    source.validate_task(task)
    with pytest.raises(ValueError):
        source.validate_task(task.model_copy(update={"context": "Rat liver microsomes, mixed clearance units"}))


def test_fixed_source_never_follows_untrusted_redirect_or_oversized_body():
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(303, headers={"Location": "https://evil.example/file"}))) as client:
        with pytest.raises((ValueError, httpx.HTTPStatusError)):
            source._download(client, source.BASE + "CSV")
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"123456"))) as client:
        with pytest.raises(ValueError, match="limit"):
            source._download(client, source.BASE + "CSV", limit=5)


def test_error_metadata_or_changed_protocol_cannot_supply_training_labels(monkeypatch):
    raw, metadata = inputs(monkeypatch)
    with pytest.raises(ValueError, match="metadata"):
        source.parse_source(raw, b'{"Fault": "source unavailable"}')
    changed = json.loads(metadata)
    changed["PC_AssayContainer"][0]["assay"]["descr"]["protocol"] = ["rat microsomes; different incubation"]
    with pytest.raises(ValueError, match="conditions"):
        source.parse_source(raw, json.dumps(changed).encode())


def test_reviewed_preset_and_import_api_route(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.ai_research_agent import api
    from app.ai_research_agent.orchestrator import ResearchAgent
    agent = ResearchAgent(tmp_path)
    identifier = agent.create(TaskConfig(**source.task_config()))["id"]
    monkeypatch.setattr(api, "agent", lambda: agent)
    monkeypatch.setattr(agent, "import_ncats_hlm", lambda identifier: {"source": "ncats_hlm", "task_id": identifier})
    monkeypatch.setenv("CHEMANALYZER_RESEARCH_ENABLED", "1")
    client = TestClient(app)
    assert client.get("/api/research/status").json()["hlm_task"]["endpoint"] == source.task_config()["endpoint"]
    response = client.post(f"/api/research/tasks/{identifier}/ncats-hlm", json={})
    assert response.status_code == 200 and response.json()["source"] == "ncats_hlm"
