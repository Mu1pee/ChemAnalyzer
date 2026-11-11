"""Source validation fixtures only; these rows are never scientific training data."""
import csv
import io

import httpx
import pytest

from app.ai_research_agent import tdc_cyp as source
from app.ai_research_agent.config import TaskConfig


def test_adapter_preserves_original_labels_and_record_ids(monkeypatch):
    monkeypatch.setitem(source.FILES, "CYP1A2", (4259573, 2))
    raw = b'Drug_ID\tDrug\tY\n100\tCCO\t0\n200\tCCN\t1\n'
    rows = list(csv.DictReader(io.StringIO(source.parse_table(raw, "CYP1A2"))))
    assert [(r["record_id"], r["smiles"], r["value"]) for r in rows] == [("100", "CCO", "0"), ("200", "CCN", "1")]


@pytest.mark.parametrize("raw", [
    b'Drug_ID\tDrug\tY\n100\tCCO\t0\n',
    b'Drug_ID\tDrug\tY\n100\tCCO\t0\n100\tCCN\t1\n',
    b'Drug_ID\tDrug\tY\n100\tCCO\t0\n200\tCCN\t0.5\n',
    b'Drug_ID\tDrug\tOther\n100\tCCO\t0\n200\tCCN\t1\n',
])
def test_changed_source_rejected_instead_of_truncated_or_relabelled(monkeypatch, raw):
    monkeypatch.setitem(source.FILES, "CYP1A2", (4259573, 2))
    with pytest.raises(ValueError):
        source.parse_table(raw, "CYP1A2")


def test_untrusted_redirect_never_receives_request():
    visited = []
    def handler(request):
        visited.append(request.url.host)
        return httpx.Response(303, headers={"Location": "https://evil.example/file"})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="Untrusted"):
            source._download(client, "https://dataverse.harvard.edu/api/access/datafile/4259573")
    assert visited == ["dataverse.harvard.edu"]


def test_download_size_bound_and_reviewed_storage_redirect():
    def handler(request):
        if request.url.host == "dataverse.harvard.edu":
            return httpx.Response(303, headers={"Location": "https://dvn-cloud-iqss.s3.amazonaws.com/data"})
        return httpx.Response(200, content=b"0123456789")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="limit"):
            source._download(client, "https://dataverse.harvard.edu/data", limit=5)


def test_no_cross_isoform_or_context_import():
    task = TaskConfig(**source.task_config("CYP1A2"))
    assert source.isoform_for_task(task) == "CYP1A2"
    with pytest.raises(ValueError, match="context"):
        source.isoform_for_task(task.model_copy(update={"context": "Mixed CYP clinical interaction data"}))


def test_cyp_api_route_does_not_fall_through_generic_action(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.ai_research_agent import api
    from app.ai_research_agent.orchestrator import ResearchAgent
    agent = ResearchAgent(tmp_path)
    identifier = agent.create(TaskConfig(**source.task_config("CYP1A2")))["id"]
    monkeypatch.setattr(api, "agent", lambda: agent)
    monkeypatch.setattr(agent, "import_tdc_cyp", lambda identifier: {"source": "tdc_cyp", "task_id": identifier})
    monkeypatch.setenv("CHEMANALYZER_RESEARCH_ENABLED", "1")
    client = TestClient(app)
    assert client.get("/api/research/status").json()["cyp_tasks"]["CYP1A2"]["endpoint"] == "cyp1a2_inhibition_veith"
    response = client.post(f"/api/research/tasks/{identifier}/tdc-cyp", json={})
    assert response.status_code == 200 and response.json()["source"] == "tdc_cyp"
