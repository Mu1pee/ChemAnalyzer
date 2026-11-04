import csv
import io
import math
from urllib.parse import urlparse

from .config import Provenance, TaskConfig


def validate_source(task: TaskConfig, provenance: Provenance):
    if not provenance.experimental:
        raise ValueError("Only experimental labels are permitted")
    for name in ("endpoint", "units", "context"):
        if getattr(task, name) != getattr(provenance, name):
            raise ValueError(f"Incompatible {name}; separate research task required")
    for url in (provenance.source_url, provenance.license_url):
        if urlparse(url).scheme != "https" or not urlparse(url).hostname:
            raise ValueError("Provenance requires an HTTPS source and license URL")


def read_measurements(text: str, max_rows: int):
    reader = csv.DictReader(io.StringIO(text))
    if not {"smiles", "value"}.issubset(reader.fieldnames or []):
        raise ValueError("CSV requires smiles,value columns")
    rows, issues = [], []
    for number, row in enumerate(reader, 2):
        if number - 1 > max_rows:
            raise ValueError("Dataset exceeds configured row limit")
        record = dict(row, row=number)
        try:
            value = float(row.get("value") or "")
            if not math.isfinite(value):
                raise ValueError()
            record["value"] = value
        except (TypeError, ValueError):
            issues.append(dict(row=number, category="missing_label" if not row.get("value") else "measurement_error"))
            continue
        rows.append(record)
    return rows, issues
