"""One federal NCATS HLM assay; source stability labels, not clinical half-life."""
import csv
import io
import json
import math
import time
from collections import Counter
from urllib.parse import urlsplit

import httpx

from .security import checksum, utcnow

AID = 1963597
ROWS = 900
RAW_SHA256 = "9e941510888f92efc4eeb7cc455acc4329717636dcc0b2e2b4ab52b23a08a010"
BASE = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/aid/{AID}/"
POLICY = "https://www.ncbi.nlm.nih.gov/home/about/policies/"
DOI = "10.3390/pharmaceutics16101257"
FIELDS = ["PUBCHEM_RESULT_TAG", "PUBCHEM_SID", "PUBCHEM_CID", "PUBCHEM_EXT_DATASOURCE_SMILES",
          "PUBCHEM_ACTIVITY_OUTCOME", "PUBCHEM_ACTIVITY_SCORE", "PUBCHEM_ACTIVITY_URL",
          "PUBCHEM_ASSAYDATA_COMMENT", "Phenotype", "Half-life", "Analysis Comment"]


def task_config():
    return dict(name="NCATS HLM: metabolic stability >30 min", domain="admet",
                endpoint="human_hlm_stability_30min_ncats", kind="classification", units="0/1",
                context="NCATS PubChem AID 1963597 v1 revision 1; human liver microsomal substrate-depletion assay. "
                        "Source phenotype Stable (t1/2 >30 min), PubChem Active, NCATS Class=0 maps to model Y=1; "
                        "Unstable (t1/2 <30 min), Inactive, Class=1 maps to Y=0. "
                        "1 uM test article; 0.5 mg/mL HLM; NADPH; pH 7.4; 37 C; sampling 0-60 min. "
                        "Exact 30-min boundary requires review. Source half-lives are not uncensored regression labels. "
                        "Not clinical half-life, intrinsic clearance, CYP inhibition or antidote activity.",
                seed=42, max_rows=2000, max_seconds=1800, max_ram_mb=3072)


def validate_task(task):
    expected = task_config()
    if any(getattr(task, key) != expected[key] for key in ("endpoint", "context", "domain", "kind", "units")):
        raise ValueError("NCATS HLM import requires the reviewed human 30-minute stability task")


def _download(client, url, limit=2_000_000):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in ("pubchem.ncbi.nlm.nih.gov", "www.ncbi.nlm.nih.gov")
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("Untrusted NCATS download destination")
    with client.stream("GET", url, follow_redirects=False) as response:
        response.raise_for_status()
        if response.is_redirect:
            raise ValueError("Unexpected NCATS source redirect")
        chunks, size = [], 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > limit:
                raise ValueError("NCATS source exceeds download limit")
            chunks.append(chunk)
    return b"".join(chunks)


def _parse_source(raw, metadata):
    if checksum(raw) != RAW_SHA256:
        raise ValueError("NCATS HLM source snapshot changed; renewed review required")
    description = json.loads(metadata)["PC_AssayContainer"][0]["assay"]["descr"]
    source = description["aid_source"]["db"]
    if (description["aid"] != {"id": AID, "version": 1} or description["revision"] != 1
            or source["name"] != "NCGC" or source["source_id"]["str"] != "ADME-HLM1"):
        raise ValueError("NCATS assay identity, depositor or version changed")
    protocol = " ".join(description["protocol"]).lower()
    if not all(term in protocol for term in ("human liver microsomes", "0.5 mg/ml", "1 mum", "ph 7.4", "37 degrees c")):
        raise ValueError("NCATS HLM assay conditions changed")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if reader.fieldnames != FIELDS:
        raise ValueError("Unexpected NCATS HLM source schema")
    all_rows = list(reader)
    if ([r["PUBCHEM_RESULT_TAG"] for r in all_rows[:3]] != ["RESULT_TYPE", "RESULT_DESCR", "RESULT_UNIT"]
            or all_rows[2]["Half-life"] != "MINUTES"):
        raise ValueError("NCATS HLM result definitions or measurement units changed")
    rows = all_rows[3:]
    if len(rows) != ROWS:
        raise ValueError("NCATS HLM source row count changed")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["record_id", "smiles", "value", "reference", "notes"])
    writer.writeheader()
    sids, cids, tags, counts = set(), set(), set(), Counter()
    for row in rows:
        if None in row or any(row.get(key) is None for key in FIELDS):
            raise ValueError("Malformed NCATS HLM source record")
        sid, cid, tag = (row[key].strip() for key in ("PUBCHEM_SID", "PUBCHEM_CID", "PUBCHEM_RESULT_TAG"))
        smiles, phenotype = row["PUBCHEM_EXT_DATASOURCE_SMILES"].strip(), row["Phenotype"].strip()
        if (not all(x.isdecimal() for x in (sid, cid, tag)) or sid in sids or cid in cids or tag in tags
                or not smiles or len(smiles) > 4000 or phenotype not in ("Stable", "Unstable")):
            raise ValueError("Invalid or repeated NCATS HLM identity/phenotype")
        stable = phenotype == "Stable"
        half_life = float(row["Half-life"])
        if (not math.isfinite(half_life) or half_life <= 0 or half_life == 30
                or stable != (half_life > 30)
                or row["PUBCHEM_ACTIVITY_OUTCOME"] != ("Active" if stable else "Inactive")
                or row["Analysis Comment"] != ("Class=0" if stable else "Class=1")):
            raise ValueError("NCATS phenotype, outcome, class and half-life cross-check failed")
        sids.add(sid)
        cids.add(cid)
        tags.add(tag)
        counts[phenotype] += 1
        writer.writerow(dict(record_id="SID:" + sid, smiles=smiles, value="1" if stable else "0", reference=DOI,
                             notes=f"AID {AID}; CID {cid}; {phenotype}; {row['Analysis Comment']}; "
                                   f"source half-life {row['Half-life']} min, not used as exact regression target"))
    if set(counts) != {"Stable", "Unstable"}:
        raise ValueError("NCATS HLM source requires both phenotype classes")
    return output.getvalue(), dict(source_rows=len(rows), stable=counts["Stable"], unstable=counts["Unstable"],
                                  boundary_30min_rows=0, source_class_mapping={"Class=0": "Y=1 stable", "Class=1": "Y=0 unstable"})


def parse_source(raw, metadata):
    try:
        return _parse_source(raw, metadata)
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError("Malformed NCATS assay metadata or records") from error


def fetch_hlm():
    with httpx.Client(timeout=httpx.Timeout(30, connect=8), headers={"User-Agent": "ChemAnalyzer-Research/0.3"}) as client:
        metadata = _download(client, BASE + "description/JSON")
        time.sleep(.35)
        raw = _download(client, BASE + "CSV")
        policy = _download(client, POLICY)
    if b"public domain" not in policy or b"PubChem" not in policy:
        raise ValueError("NCBI source rights policy requires renewed review")
    text, curation = parse_source(raw, metadata)
    config = task_config()
    provenance = dict(source_url=BASE + "CSV", doi=DOI, license="Public-Domain-US-Gov", license_url=POLICY,
                      source_version=f"AID {AID} v1.r1; sha256:" + checksum(raw)[:16], retrieved_at=utcnow(),
                      endpoint=config["endpoint"], units=config["units"], context=config["context"],
                      experimental=True, curator="Reviewed NCATS federal-depositor HLM source adapter")
    evidence = dict(curation, raw_sha256=checksum(raw), metadata_sha256=checksum(metadata), policy_sha256=checksum(policy),
                    attribution="NCATS/NIH; PubChem AID 1963597 (NCGC ADME-HLM1); Shah et al. (2024), doi:" + DOI,
                    rights_basis="Federal NCATS-authored assay deposited by NCGC; NCBI public-domain government-works policy. "
                                 "No source-specific restriction indicated in this assay. This is not a blanket public-domain claim for PubChem or third-party data. "
                                 "No CC0 dedication is inferred. Paper separately states CC BY 4.0; no government endorsement claimed.",
                    limitations="Only the public 900-compound subset, not the authors' full 6648-compound model. "
                                "Source phenotype/outcome/class/half-life cross-checked; source values at 120 min may be upper-capped. "
                                "Only binary stability is modelled; no clinical half-life or clearance inference. "
                                "No rat data, predicted rat stability or externally downloaded models used.")
    return text, provenance, raw, metadata, policy, evidence
