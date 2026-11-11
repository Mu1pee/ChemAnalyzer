"""Reviewed NCI/MoleculeNet HIV replication-screen data, not general antiviral efficacy."""
import csv
import io
import json

import httpx
from rdkit import Chem

from .security import checksum, utcnow
from .tdc_cyp import _download

ROWS = 41127
MAX_REFERENCE_DISAGREEMENTS = 5
SOURCE = "https://dataverse.harvard.edu/api/access/datafile/4259593"
REFERENCE = "https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/HIV.csv"
DOCUMENTATION = "https://tdcommons.ai/single_pred_tasks/hts/"
DOI = "10.1039/C7SC02664A"


def task_config():
    return dict(name="NCI/MoleculeNet: HIV replication inhibition", domain="qsar",
                endpoint="hiv_replication_inhibition_nci", units="0/1", kind="classification",
                context="NCI DTP AIDS Antiviral Screen, TDC/MoleculeNet binary benchmark. "
                        "Original confirmed active (CA) and moderately active (CM) are positive; confirmed inactive (CI) is negative. "
                        "Cell-based screening conclusion, not clinical efficacy, general antiviral activity or quantitative potency.",
                seed=42, max_rows=50000, max_seconds=1800, max_ram_mb=3072)


def validate_task(task):
    expected = task_config()
    if any(getattr(task, key) != expected[key] for key in ("endpoint", "context", "domain", "kind", "units")):
        raise ValueError("HIV source requires the reviewed NCI replication-screen task")


def parse_tables(raw, reference):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), delimiter="\t")
    controls = csv.DictReader(io.StringIO(reference.decode("utf-8-sig")))
    if set(reader.fieldnames or []) != {"Drug_ID", "Drug", "Y"} or set(controls.fieldnames or []) != {"smiles", "activity", "HIV_active"}:
        raise ValueError("Unexpected HIV source schema")
    rows, original = list(reader), list(controls)
    if len(rows) != ROWS or len(original) != ROWS:
        raise ValueError("HIV source row count changed; renewed source review required")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["record_id", "smiles", "value", "reference", "notes"])
    writer.writeheader()
    seen, labels, excluded, equivalent = set(), set(), [], 0
    for index, (row, control) in enumerate(zip(rows, original)):
        identifier, smiles, label = row["Drug_ID"].strip(), row["Drug"].strip(), row["Y"].strip()
        category = control["activity"]
        if (not identifier or identifier in seen or not smiles or category not in ("CA", "CM", "CI")
                or label not in ("0", "1") or label != control["HIV_active"]
                or label != ("0" if category == "CI" else "1")):
            raise ValueError("HIV identity or original binary-label cross-check failed")
        seen.add(identifier)
        if smiles != control["smiles"]:
            left = Chem.MolFromSmiles(smiles) if len(smiles) <= 4000 else None
            right = Chem.MolFromSmiles(control["smiles"]) if len(control["smiles"]) <= 4000 else None
            if left is None or right is None or Chem.MolToSmiles(left, isomericSmiles=True) != Chem.MolToSmiles(right, isomericSmiles=True):
                excluded.append(dict(record_id=identifier, source_row=index + 2, reason="reference_structure_disagreement_or_invalid"))
                continue
            equivalent += 1
        labels.add(label)
        writer.writerow(dict(record_id=identifier, smiles=smiles, value=label, reference=DOI, notes="Original NCI/MoleculeNet outcome: " + category))
    if len(excluded) > MAX_REFERENCE_DISAGREEMENTS:
        raise ValueError("HIV reference structure disagreements exceed the reviewed source limit")
    if labels != {"0", "1"}:
        raise ValueError("HIV source must contain both binary classes")
    return output.getvalue(), dict(source_rows=len(rows), reference_equivalent_variants=equivalent,
                                  excluded_reference_disagreements=excluded, accepted_before_structure_preparation=len(rows) - len(excluded))


def fetch_hiv():
    config = task_config()
    with httpx.Client(timeout=httpx.Timeout(30, connect=8), headers={"User-Agent": "ChemAnalyzer-Research/0.3"}) as client:
        metadata = _download(client, "https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=doi:10.7910/DVN/21LKWG")
        if json.loads(metadata)["data"]["latestVersion"].get("license", {}).get("rightsIdentifier") != "CC0-1.0":
            raise ValueError("Dataverse license changed; source review required")
        raw = _download(client, SOURCE)
        # Fixed primary-maintainer reference URL; never follows a redirect or user input.
        with client.stream("GET", REFERENCE, follow_redirects=False) as response:
            response.raise_for_status()
            if response.is_redirect:
                raise ValueError("Unexpected HIV reference redirect")
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > 8_000_000:
                    raise ValueError("HIV reference exceeds download limit")
                chunks.append(chunk)
            reference = b"".join(chunks)
    text, curation = parse_tables(raw, reference)
    provenance = dict(source_url=SOURCE, doi=DOI, license="CC-BY-4.0", license_url=DOCUMENTATION,
                      source_version="Dataverse 4259593; sha256:" + checksum(raw)[:16], retrieved_at=utcnow(),
                      endpoint=config["endpoint"], units=config["units"], context=config["context"],
                      experimental=True, curator="Reviewed TDC HIV adapter with primary-maintainer label cross-check")
    evidence = dict(curation, raw_sha256=checksum(raw), metadata_sha256=checksum(metadata), reference_sha256=checksum(reference),
                    reference_url=REFERENCE, dataverse_license="CC0-1.0", tdc_license="CC-BY-4.0",
                    attribution="NCI DTP AIDS Antiviral Screen; Wu et al., MoleculeNet (2018), doi:10.1039/C7SC02664A; TDC contributors.",
                    limitations="Rare positive class; preserve CA/CM aggregation and source screening conclusions. "
                                "No uniform potency cutoff, clinical efficacy or generalization to other viruses. "
                                "Reference structure disagreements are excluded before scaffold preparation; remaining assay artifacts are not independently remeasured.")
    return text, provenance, raw, metadata, reference, evidence
