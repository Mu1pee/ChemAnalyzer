"""One reviewed ToxCast assay; unmeasured cells are never negative labels."""
import csv
import io
import json
from collections import Counter

import httpx

from .security import checksum, utcnow
from .tdc_cyp import _download

ASSAY = "APR_HepG2_CellLoss_24h_dn"
ROWS = 8576
SCHEMA_SHA256 = "1732d5600ac678905499ab4c072043c674b398018b8eff86eaa88afaddf64076"
LABEL_COUNTS = {"": 7542, "0.0": 734, "1.0": 300}
SOURCE = "https://dataverse.harvard.edu/api/access/datafile/4259613"
DOCUMENTATION = "https://tdcommons.ai/single_pred_tasks/tox/"
DOI = "10.1021/acs.chemrestox.6b00135"
ASSAY_REFERENCE = "https://pmc.ncbi.nlm.nih.gov/articles/PMC6280881/"


def task_config():
    return dict(name="ToxCast: HepG2 proliferation decrease, 24 h", domain="admet",
                endpoint="hepg2_cellloss_24h_toxcast", units="0/1", kind="classification",
                context="TDC ToxCast benchmark; APR_HepG2_CellLoss_24h_dn. Human liver HepG2 cell line, "
                        "24-hour proliferation decrease/cell-loss assay; original binary hit calls. "
                        "Unmeasured outcomes excluded. Not confirmed cell death, general cytotoxicity, "
                        "clinical liver injury, anticancer efficacy or acetaminophen rescue.",
                seed=42, max_rows=2000, max_seconds=1800, max_ram_mb=3072)


def validate_task(task):
    expected = task_config()
    if any(getattr(task, key) != expected[key] for key in ("endpoint", "context", "domain", "kind", "units")):
        raise ValueError("HepG2 source requires the reviewed 24-hour proliferation assay task")


def parse_table(raw):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), delimiter="\t")
    fields = reader.fieldnames or []
    if (checksum("\t".join(fields).encode()) != SCHEMA_SHA256
            or not {"X", "ID", ASSAY}.issubset(fields)):
        raise ValueError("ToxCast schema changed; renewed source review required")
    rows = list(reader)
    if len(rows) != ROWS:
        raise ValueError("ToxCast row count changed; renewed source review required")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["record_id", "smiles", "value", "reference", "notes"])
    writer.writeheader()
    identifiers, counts = set(), Counter()
    for row in rows:
        if None in row or any(row[key] is None for key in ("X", "ID", ASSAY)):
            raise ValueError("Malformed ToxCast record")
        identifier, smiles, label = row["ID"].strip(), row["X"].strip(), row[ASSAY].strip()
        if not identifier or identifier in identifiers or not smiles or label not in ("", "0.0", "1.0"):
            raise ValueError("Invalid ToxCast identity or binary hit call")
        identifiers.add(identifier)
        counts[label] += 1
        if not label:
            continue
        writer.writerow(dict(record_id=identifier, smiles=smiles, value="1" if label == "1.0" else "0",
                             reference=DOI, notes=ASSAY + "; original ToxCast binary hit call"))
    if dict(counts) != LABEL_COUNTS:
        raise ValueError("HepG2 measurement counts changed; renewed source review required")
    return output.getvalue(), dict(source_rows=len(rows), measured_rows=counts["0.0"] + counts["1.0"],
                                  missing_excluded=counts[""], negative=counts["0.0"], positive=counts["1.0"])


def fetch_hepg2():
    with httpx.Client(timeout=httpx.Timeout(30, connect=8), headers={"User-Agent": "ChemAnalyzer-Research/0.3"}) as client:
        metadata = _download(client, "https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=doi:10.7910/DVN/21LKWG")
        if json.loads(metadata)["data"]["latestVersion"].get("license", {}).get("rightsIdentifier") != "CC0-1.0":
            raise ValueError("Dataverse license changed; source review required")
        raw = _download(client, SOURCE, limit=20_000_000)
    text, curation = parse_table(raw)
    config = task_config()
    provenance = dict(source_url=SOURCE, doi=DOI, license="CC-BY-4.0", license_url=DOCUMENTATION,
                      source_version="Dataverse 4259613; sha256:" + checksum(raw)[:16], retrieved_at=utcnow(),
                      endpoint=config["endpoint"], units=config["units"], context=config["context"],
                      experimental=True, curator="Reviewed single-assay TDC ToxCast adapter")
    evidence = dict(curation, raw_sha256=checksum(raw), metadata_sha256=checksum(metadata), assay=ASSAY,
                    assay_reference=ASSAY_REFERENCE, dataverse_license="CC0-1.0", tdc_license="CC-BY-4.0",
                    epa_license_url="https://edg.epa.gov/EPA_Data_License.html",
                    attribution="US EPA ToxCast; Richard et al. (2016), doi:10.1021/acs.chemrestox.6b00135; TDC contributors.",
                    limitations="Older TDC benchmark snapshot, not current EPA invitrodb. One assay and exposure time only. "
                                "Missing measurements excluded before structure preparation; no derived potency cutoff. "
                                "Proliferation decrease is not proof of cell death or clinical toxicity.")
    return text, provenance, raw, metadata, evidence
