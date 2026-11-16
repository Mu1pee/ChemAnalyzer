"""Small parser/admission fixtures only; never used as real training data."""
import csv
import io
import json

import pytest

from app.ai_research_agent import ncats_solubility as source
from app.ai_research_agent.config import TaskConfig
from app.ai_research_agent.security import checksum


def fixture(monkeypatch, records=None, metadata_change=None):
    records = records or [("1", "100", "200", "Low", "<1", "Inactive", "class = 1"),
                          ("2", "101", "201", "Moderate/High", ">100", "Active", "class = 0"),
                          ("3", "102", "202", "N/A", "N/A", "Inconclusive", ""),
                          ("4", "103", "203", "Moderate/High", ">6", "Active", "class = 0")]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=source.FIELDS)
    writer.writeheader()
    for tag in ("RESULT_TYPE", "RESULT_DESCR"):
        writer.writerow(dict(PUBCHEM_RESULT_TAG=tag, **{source.VALUE_FIELD: "STRING"}))
    for tag, sid, cid, phenotype, value, outcome, comment in records:
        writer.writerow(dict(PUBCHEM_RESULT_TAG=tag, PUBCHEM_SID=sid, PUBCHEM_CID=cid,
                             PUBCHEM_EXT_DATASOURCE_SMILES="CCO", Phenotype=phenotype,
                             PUBCHEM_ACTIVITY_OUTCOME=outcome, **{source.VALUE_FIELD: value, "Analysis Comment": comment}))
    metadata = dict(aid=dict(id=source.AID, version=2), revision=1,
                    aid_source=dict(db=dict(name="NCGC", source_id=dict(str="ADME-solubility1"))),
                    protocol=["kinetic; 150 microM; pH 7.4; 6 h; duplicates"])
    if metadata_change:
        metadata.update(metadata_change)
    raw = output.getvalue().encode()
    meta = json.dumps(dict(PC_AssayContainer=[dict(assay=dict(descr=metadata))])).encode()
    monkeypatch.setattr(source, "RAW_SHA256", checksum(raw))
    monkeypatch.setattr(source, "METADATA_SHA256", checksum(meta))
    monkeypatch.setattr(source, "ROWS", len(records))
    return raw, meta


def test_preserves_source_class_direction_and_excludes_missing_and_ambiguous(monkeypatch):
    raw, metadata = fixture(monkeypatch)
    text, evidence = source.parse_source(raw, metadata)
    rows = list(csv.DictReader(io.StringIO(text)))
    assert [row["value"] for row in rows] == ["1", "0"]
    assert [item["reason"] for item in evidence["exclusions"]] == ["unmeasured_or_inconclusive", "censored_interval_crosses_cutoff"]
    assert evidence["source_rows"] == 4 and evidence["retained_before_structure_curation"] == 2
    assert "<1 ug/mL" in rows[0]["notes"] and ">100 ug/mL" in rows[1]["notes"]


@pytest.mark.parametrize("value,result", [("10", 1), ("10.01", 0), ("<10", 1), (">10", 0),
                                          (">6", None), ("<12", None), ("0", 1)])
def test_censored_bounds_must_determine_the_cutoff_class(value, result):
    assert source.interval_class(value) == result


@pytest.mark.parametrize("value", ["NaN", "inf", "-1", "N/A", "10 mg/ml", "<=10", None])
def test_malformed_or_unit_changing_values_cannot_provide_labels(value):
    with pytest.raises(ValueError):
        source.interval_class(value)


def test_wrong_source_class_or_measurement_requires_review(monkeypatch):
    raw, metadata = fixture(monkeypatch, [("1", "100", "200", "Low", "20", "Inactive", "class = 1")])
    with pytest.raises(ValueError, match="contradicts"):
        source.parse_source(raw, metadata)
    raw, metadata = fixture(monkeypatch, [("1", "100", "200", "Low", "1", "Active", "class = 1")])
    with pytest.raises(ValueError, match="disagree"):
        source.parse_source(raw, metadata)


def test_snapshot_or_protocol_change_requires_review(monkeypatch):
    raw, metadata = fixture(monkeypatch)
    with pytest.raises(ValueError, match="snapshot changed"):
        source.parse_source(raw + b" ", metadata)
    raw, metadata = fixture(monkeypatch, metadata_change=dict(protocol=["thermodynamic; pH 5"]))
    with pytest.raises(ValueError, match="conditions changed"):
        source.parse_source(raw, metadata)


def test_repeated_sid_is_not_an_independent_measurement(monkeypatch):
    raw, metadata = fixture(monkeypatch, [("1", "100", "200", "Low", "1", "Inactive", "class = 1"),
                                       ("2", "100", "201", "Moderate/High", "20", "Active", "class = 0")])
    with pytest.raises(ValueError, match="repeated"):
        source.parse_source(raw, metadata)


def test_task_cannot_reinterpret_kinetic_classes_as_thermodynamic_regression():
    task = TaskConfig(**source.task_config())
    source.validate_task(task)
    task.kind, task.units = "regression", "logS"
    with pytest.raises(ValueError, match="classification task"):
        source.validate_task(task)


def test_reviewed_import_route_is_distinct_from_training_action(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.ai_research_agent import api
    from app.ai_research_agent.orchestrator import ResearchAgent
    agent = ResearchAgent(tmp_path)
    identifier = agent.create(TaskConfig(**source.task_config()))["id"]
    monkeypatch.setattr(api, "agent", lambda: agent)
    monkeypatch.setattr(agent, "import_ncats_solubility", lambda value: dict(source="ncats_solubility", task_id=value))
    monkeypatch.setenv("CHEMANALYZER_RESEARCH_ENABLED", "1")
    client = TestClient(app)
    assert client.get("/api/research/status").json()["solubility_task"] == source.task_config()
    sources = client.get("/api/research/sources", params=dict(endpoint=source.task_config()["endpoint"])).json()["sources"]
    reviewed = next(item for item in sources if item["id"] == "ncats_solubility")
    assert reviewed["endpoint"] == source.task_config()["endpoint"] and reviewed["license"] == "Public-Domain-US-Gov"
    result = client.post(f"/api/research/tasks/{identifier}/ncats-solubility", json={})
    assert result.status_code == 200 and result.json()["source"] == "ncats_solubility"
