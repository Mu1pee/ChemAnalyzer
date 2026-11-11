"""Source integrity fixtures; never scientific training data."""
import csv
import io

import pytest

from app.ai_research_agent import tdc_hepg2 as source
from app.ai_research_agent.config import TaskConfig
from app.ai_research_agent.security import checksum


def table(monkeypatch, labels=("", "0.0", "1.0")):
    header = "X\t" + source.ASSAY + "\tID"
    monkeypatch.setattr(source, "SCHEMA_SHA256", checksum(header.encode()))
    monkeypatch.setattr(source, "ROWS", len(labels))
    monkeypatch.setattr(source, "LABEL_COUNTS", {"": 1, "0.0": 1, "1.0": 1})
    return (header + "\n" + "\n".join(f"CC{'C' * i}\t{label}\tDrug {i}" for i, label in enumerate(labels))).encode()


def test_unmeasured_outcomes_are_not_negative(monkeypatch):
    text, evidence = source.parse_table(table(monkeypatch))
    rows = list(csv.DictReader(io.StringIO(text)))
    assert [(r["record_id"], r["value"]) for r in rows] == [("Drug 1", "0"), ("Drug 2", "1")]
    assert evidence == dict(source_rows=3, measured_rows=2, missing_excluded=1, negative=1, positive=1)


@pytest.mark.parametrize("label", ["nan", "-1", "0.5", "1", "NA"])
def test_ambiguous_labels_never_coerced(monkeypatch, label):
    with pytest.raises(ValueError, match="binary hit"):
        source.parse_table(table(monkeypatch, ("", "0.0", label)))


def test_duplicate_identity_and_changed_measurement_counts_rejected(monkeypatch):
    raw = table(monkeypatch)
    with pytest.raises(ValueError, match="identity"):
        source.parse_table(raw.replace(b"Drug 2", b"Drug 1"))
    with pytest.raises(ValueError, match="counts"):
        source.parse_table(raw.replace(b"1.0", b"0.0"))


def test_exposure_time_or_toxicity_context_cannot_be_substituted():
    task = TaskConfig(**source.task_config())
    source.validate_task(task)
    for changed in ({"context": "HepG2, 72 h"}, {"endpoint": "apap_rescue"}, {"domain": "qsar"}):
        with pytest.raises(ValueError):
            source.validate_task(task.model_copy(update=changed))
