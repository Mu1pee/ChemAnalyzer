"""Small source validation fixtures, never real scientific training data."""
import csv
import io

import pytest

from app.ai_research_agent import tdc_hiv as source
from app.ai_research_agent.config import TaskConfig


def tables(monkeypatch, source_rows, reference_rows):
    monkeypatch.setattr(source, "ROWS", len(source_rows))
    raw = "Drug_ID\tDrug\tY\n" + "\n".join("\t".join(row) for row in source_rows)
    reference = "smiles,activity,HIV_active\n" + "\n".join(",".join(row) for row in reference_rows)
    return raw.encode(), reference.encode()


def test_primary_labels_and_equivalent_smiles(monkeypatch):
    raw, reference = tables(monkeypatch, [("1", "CCO", "0"), ("2", "CCN", "1"), ("3", "CCC", "1")],
                            [("OCC", "CI", "0"), ("CCN", "CA", "1"), ("CCC", "CM", "1")])
    text, evidence = source.parse_tables(raw, reference)
    rows = list(csv.DictReader(io.StringIO(text)))
    assert [r["value"] for r in rows] == ["0", "1", "1"]
    assert evidence["reference_equivalent_variants"] == 1
    assert evidence["excluded_reference_disagreements"] == []


def test_disagreeing_structures_excluded_before_training(monkeypatch):
    raw, reference = tables(monkeypatch, [("1", "CCO", "0"), ("2", "CCN", "1"), ("3", "CCC", "1")],
                            [("CCO", "CI", "0"), ("CCN", "CA", "1"), ("CCCl", "CM", "1")])
    text, evidence = source.parse_tables(raw, reference)
    assert len(list(csv.DictReader(io.StringIO(text)))) == 2
    assert evidence["excluded_reference_disagreements"][0]["record_id"] == "3"
    monkeypatch.setattr(source, "MAX_REFERENCE_DISAGREEMENTS", 0)
    with pytest.raises(ValueError, match="disagreements"):
        source.parse_tables(raw, reference)


@pytest.mark.parametrize("category,label,reference_label", [("CI", "1", "1"), ("CA", "0", "0"), ("CA", "1", "0"), ("OTHER", "1", "1")])
def test_changed_category_or_label_rejected(monkeypatch, category, label, reference_label):
    raw, reference = tables(monkeypatch, [("1", "CCO", label)], [("CCO", category, reference_label)])
    with pytest.raises(ValueError, match="cross-check"):
        source.parse_tables(raw, reference)


def test_context_cannot_be_replaced_with_general_antiviral():
    task = TaskConfig(**source.task_config())
    source.validate_task(task)
    with pytest.raises(ValueError):
        source.validate_task(task.model_copy(update={"context": "General antiviral or clinical HIV efficacy"}))
