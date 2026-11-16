"""Reviewed NCATS kinetic-solubility classes; never use censored values as regression targets."""
import csv
import io
import json
import math
import re
import time
from collections import Counter

import httpx

from .ncats_hlm import _download, POLICY
from .security import checksum, utcnow

AID = 1645848
ROWS = 2532
RAW_SHA256 = "081904a6292637bb16a59de66b8d648729dd1b583a566c532ff32e60fceba1a2"
METADATA_SHA256 = "da0eb7b21678d3169f692b1681b1f00e1ca8faf649217d0f4ab6ebfcb6c00588"
BASE = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/aid/{AID}/"
DOI = "10.1016/j.bmc.2019.05.037"
FIELDS = ["PUBCHEM_RESULT_TAG", "PUBCHEM_SID", "PUBCHEM_CID", "PUBCHEM_EXT_DATASOURCE_SMILES",
          "PUBCHEM_ACTIVITY_OUTCOME", "PUBCHEM_ACTIVITY_SCORE", "PUBCHEM_ACTIVITY_URL",
          "PUBCHEM_ASSAYDATA_COMMENT", "Phenotype", "Kinetic Aqueous Solubility (ug/mL)", "Analysis Comment"]
VALUE_FIELD = "Kinetic Aqueous Solubility (ug/mL)"


def task_config():
    return dict(name="NCATS: low kinetic solubility at pH 7.4", domain="admet",
                endpoint="kinetic_low_solubility_10ugml_ncats_ph74", kind="classification", units="0/1",
                context="NCATS PubChem AID 1645848 v2 revision 1; kinetic aqueous solubility, Pion microSOL. "
                        "150 uM test compound; pH 7.4, 100 mM phosphate buffer; room temperature, 6 h; "
                        "vacuum filtration, UV 250-498 nm; duplicates. Y=1: source Low, solubility <=10 ug/mL, "
                        "Inactive, class=1; Y=0: Moderate/High, >10 ug/mL, Active, class=0. "
                        "N/A and censored intervals crossing the cutoff excluded; conflicting structures excluded, "
                        "same-class duplicates collapsed. Not thermodynamic/intrinsic solubility, numerical logS, "
                        "permeability, bioavailability or clinical efficacy.",
                seed=42, max_rows=5000, max_seconds=1800, max_ram_mb=3072)


def validate_task(task):
    expected = task_config()
    if any(getattr(task, key) != expected[key] for key in ("endpoint", "context", "domain", "kind", "units")):
        raise ValueError("NCATS solubility import requires the reviewed kinetic pH 7.4 classification task")


def interval_class(value):
    """1=definitely <=10, 0=definitely >10, None=interval crosses the source cutoff."""
    if not isinstance(value, str):
        raise ValueError("Invalid solubility interval")
    match = re.fullmatch(r"([<>]?)([0-9]+(?:\.[0-9]+)?)", value.strip())
    if not match:
        raise ValueError("Invalid solubility interval")
    relation, number = match.groups()
    bound = float(number)
    if not math.isfinite(bound):
        raise ValueError("Non-finite solubility interval")
    if relation == "<":
        return 1 if bound <= 10 else None
    if relation == ">":
        return 0 if bound >= 10 else None
    return int(bound <= 10)


def _parse_source(raw, metadata):
    if checksum(raw) != RAW_SHA256 or checksum(metadata) != METADATA_SHA256:
        raise ValueError("NCATS solubility source snapshot changed; renewed review required")
    description = json.loads(metadata)["PC_AssayContainer"][0]["assay"]["descr"]
    depositor = description["aid_source"]["db"]
    if (description["aid"] != {"id": AID, "version": 2} or description["revision"] != 1
            or depositor["name"] != "NCGC" or depositor["source_id"]["str"] != "ADME-solubility1"):
        raise ValueError("NCATS solubility identity, depositor or version changed")
    protocol = " ".join(description["protocol"]).lower()
    if not all(term in protocol for term in ("kinetic", "150 microm", "ph 7.4", "6 h", "duplicates")):
        raise ValueError("NCATS solubility conditions changed")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if reader.fieldnames != FIELDS:
        raise ValueError("Unexpected NCATS solubility source schema")
    all_rows = list(reader)
    if ([row["PUBCHEM_RESULT_TAG"] for row in all_rows[:2]] != ["RESULT_TYPE", "RESULT_DESCR"]
            or all_rows[0][VALUE_FIELD] != "STRING"):
        raise ValueError("NCATS solubility result definitions changed")
    rows = all_rows[2:]
    if len(rows) != ROWS:
        raise ValueError("NCATS solubility source row count changed")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["record_id", "smiles", "value", "reference", "notes"])
    writer.writeheader()
    sids, tags, cids, counts, exclusions = set(), set(), set(), Counter(), []
    for row in rows:
        if None in row or any(row.get(key) is None for key in FIELDS):
            raise ValueError("Malformed NCATS solubility source record")
        sid, cid, tag = (row[key].strip() for key in ("PUBCHEM_SID", "PUBCHEM_CID", "PUBCHEM_RESULT_TAG"))
        smiles = row["PUBCHEM_EXT_DATASOURCE_SMILES"].strip()
        if (not all(item.isdecimal() and int(item) > 0 for item in (sid, cid, tag))
                or sid in sids or tag in tags or not smiles or len(smiles) > 4000):
            raise ValueError("Invalid or repeated NCATS solubility source identity")
        # Different SIDs can point to the same CID; preparation, not test scores,
        # resolves exact structure duplicates and excludes conflicting labels.
        sids.add(sid)
        tags.add(tag)
        cids.add(cid)
        phenotype, value = row["Phenotype"].strip(), row[VALUE_FIELD].strip()
        if phenotype == "N/A":
            if row["PUBCHEM_ACTIVITY_OUTCOME"] != "Inconclusive" or value != "N/A" or row["Analysis Comment"].strip():
                raise ValueError("NCATS missing outcome definitions changed")
            exclusions.append(dict(sid=sid, cid=cid, reason="unmeasured_or_inconclusive"))
            continue
        if phenotype not in ("Low", "Moderate/High"):
            raise ValueError("Unknown NCATS solubility phenotype")
        low = phenotype == "Low"
        if (row["PUBCHEM_ACTIVITY_OUTCOME"] != ("Inactive" if low else "Active")
                or row["Analysis Comment"].strip() != ("class = 1" if low else "class = 0")):
            raise ValueError("NCATS phenotype, outcome and class disagree")
        determined = interval_class(value)
        if determined is None:
            exclusions.append(dict(sid=sid, cid=cid, reason="censored_interval_crosses_cutoff", source_value=value))
            continue
        if determined != int(low):
            raise ValueError("NCATS solubility measurement contradicts its phenotype")
        counts[phenotype] += 1
        writer.writerow(dict(record_id="SID:" + sid, smiles=smiles, value="1" if low else "0", reference=DOI,
                             notes=f"AID {AID}; CID {cid}; {phenotype}; {row['Analysis Comment']}; "
                                   f"source kinetic solubility {value} ug/mL; binary class only"))
    if set(counts) != {"Low", "Moderate/High"}:
        raise ValueError("NCATS solubility source requires both source-defined classes")
    return output.getvalue(), dict(source_rows=len(rows), unique_source_cids=len(cids),
                                  low=counts["Low"], moderate_high=counts["Moderate/High"],
                                  exclusions=exclusions, retained_before_structure_curation=sum(counts.values()),
                                  source_class_mapping={"class=1 / Inactive": "Y=1 Low", "class=0 / Active": "Y=0 Moderate/High"})


def parse_source(raw, metadata):
    try:
        return _parse_source(raw, metadata)
    except (KeyError, TypeError, IndexError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Malformed NCATS solubility metadata or records") from error


def fetch_solubility():
    with httpx.Client(timeout=httpx.Timeout(30, connect=8), headers={"User-Agent": "ChemAnalyzer-Research/0.3"}) as client:
        metadata = _download(client, BASE + "description/JSON")
        time.sleep(.4)
        raw = _download(client, BASE + "CSV")
        policy = _download(client, POLICY)
    if b"public domain" not in policy.lower() or b"PubChem" not in policy:
        raise ValueError("NCBI source rights policy requires renewed review")
    text, curation = parse_source(raw, metadata)
    config = task_config()
    provenance = dict(source_url=BASE + "CSV", doi=DOI, license="Public-Domain-US-Gov", license_url=POLICY,
                      source_version=f"AID {AID} v2.r1; sha256:" + checksum(raw)[:16], retrieved_at=utcnow(),
                      endpoint=config["endpoint"], units=config["units"], context=config["context"], experimental=True,
                      curator="Reviewed NCATS federal-depositor kinetic solubility source adapter")
    evidence = dict(curation, raw_sha256=checksum(raw), metadata_sha256=checksum(metadata), policy_sha256=checksum(policy),
                    attribution="NCATS/NIH; PubChem AID 1645848 (NCGC ADME-solubility1); Sun et al. (2019), doi:" + DOI,
                    rights_basis="Federal NCATS-authored experimental assay deposited by NCGC; NCBI government-works policy. "
                                 "No source-specific restriction indicated in this assay. Not a blanket license for PubChem, "
                                 "third-party data, the assay method or the Elsevier article/supplements; no government endorsement.",
                    limitations="Public 2532-record/2530-CID subset, not the authors' full 11780 or portal 36171 compounds. "
                                "N/A and intervals crossing 10 ug/mL are excluded, never inactive. Censored values remain "
                                "intervals and do not supply regression targets. Preparation excludes structure conflicts and "
                                "collapses matching duplicates. Only this kinetic protocol and source-defined cutoff are modeled.")
    return text, provenance, raw, metadata, policy, evidence
