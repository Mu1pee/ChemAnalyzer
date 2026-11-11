"""Reviewed, text-only TDC/Veith CYP inhibition adapters; one task per isoform."""
import csv
import io
import json
from urllib.parse import urlsplit

import httpx

from .security import checksum, utcnow

DOCUMENTATION = "https://tdcommons.ai/single_pred_tasks/adme/"
DATASET_DOI = "doi:10.7910/DVN/21LKWG"
PAPER_DOI = "10.1038/nbt.1581"
# IDs and counts reviewed against the TDC team's public metadata, not executed.
FILES = {
    "CYP1A2": (4259573, 12579), "CYP2C9": (4259577, 12092),
    "CYP2C19": (4259576, 12665), "CYP2D6": (4259580, 13130),
    "CYP3A4": (4259582, 12328),
}


def task_config(isoform):
    if isoform not in FILES:
        raise ValueError("Unsupported CYP isoform")
    return dict(name=f"TDC Veith: human {isoform} inhibition", domain="admet",
                endpoint=f"{isoform.lower()}_inhibition_veith", units="0/1", kind="classification",
                context=f"Human {isoform}; TDC/Veith biochemical inhibition benchmark (10.1038/nbt.1581). "
                        "Use original TDC binary inhibitory outcomes, Y=1 inhibitor and Y=0 non-inhibitor; "
                        "no invented concentration cutoff, clinical interaction or antidote interpretation.",
                seed=42, max_rows=20000, max_seconds=1800)


def isoform_for_task(task):
    for isoform in FILES:
        expected = task_config(isoform)
        if task.endpoint == expected["endpoint"]:
            if any(getattr(task, key) != expected[key] for key in ("context", "kind", "units", "domain")):
                raise ValueError("CYP source requires the reviewed isoform-specific task context")
            return isoform
    raise ValueError("Select a reviewed TDC CYP task before import")


def _download(client, url, limit=4_000_000):
    # Only the fixed Dataverse API and its reviewed storage bucket, with no credentials.
    for _ in range(3):
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname not in ("dataverse.harvard.edu", "dvn-cloud-iqss.s3.amazonaws.com")
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            raise ValueError("Untrusted TDC download destination")
        with client.stream("GET", url, follow_redirects=False) as response:
            if response.is_redirect:
                location = response.headers.get("location", "")
                # Reject relative redirects and credentials; next iteration validates host.
                url = location
                continue
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > limit:
                    raise ValueError("TDC source exceeds download limit")
                chunks.append(chunk)
            return b"".join(chunks)
    raise ValueError("Too many TDC source redirects")


def parse_table(raw, isoform):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), delimiter="\t")
    if set(reader.fieldnames or []) != {"Drug_ID", "Drug", "Y"}:
        raise ValueError("Unexpected TDC CYP table schema")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["record_id", "smiles", "value", "reference", "notes"])
    writer.writeheader()
    count, labels, identifiers = 0, set(), set()
    for row in reader:
        label, identifier, smiles = row["Y"].strip(), row["Drug_ID"].strip(), row["Drug"].strip()
        if label not in ("0", "1") or not identifier or not smiles or identifier in identifiers:
            raise ValueError("Invalid or repeated TDC CYP record; manual review required")
        identifiers.add(identifier)
        writer.writerow(dict(record_id=identifier, smiles=smiles, value=label, reference=PAPER_DOI,
                             notes=f"TDC {isoform} original binary outcome; no new activity threshold"))
        labels.add(label)
        count += 1
    if count != FILES[isoform][1] or labels != {"0", "1"}:
        raise ValueError(f"TDC {isoform} source row count or labels changed; review new version before import")
    return output.getvalue()


def fetch_cyp(isoform):
    expected = task_config(isoform)
    file_id = FILES[isoform][0]
    source_url = f"https://dataverse.harvard.edu/api/access/datafile/{file_id}"
    with httpx.Client(timeout=httpx.Timeout(30, connect=8), headers={"User-Agent": "ChemAnalyzer-Research/0.2"}) as client:
        metadata = _download(client, "https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=doi:10.7910/DVN/21LKWG")
        payload = json.loads(metadata)["data"]["latestVersion"]
        if payload.get("license", {}).get("rightsIdentifier") != "CC0-1.0":
            raise ValueError("Dataverse license changed; source requires renewed review")
        raw = _download(client, source_url)
    text = parse_table(raw, isoform)
    provenance = dict(source_url=source_url, doi=PAPER_DOI, license="CC-BY-4.0",
                      license_url=DOCUMENTATION, source_version=f"Dataverse file {file_id}; sha256:{checksum(raw)[:16]}",
                      retrieved_at=utcnow(), endpoint=expected["endpoint"], units=expected["units"],
                      context=expected["context"], experimental=True, curator="Reviewed TDC Veith text adapter")
    evidence = dict(raw_sha256=checksum(raw), metadata_sha256=checksum(metadata),
                    dataset_doi=DATASET_DOI, dataverse_license="CC0-1.0", tdc_license="CC-BY-4.0",
                    attribution="Veith et al. (2009), Nature Biotechnology, doi:10.1038/nbt.1581; Therapeutics Data Commons contributors.",
                    limitations="Preprocessed binary benchmark labels; assay artifacts/counter-screens not independently reviewed. "
                                "No universal potency cutoff or clinical DDI implication. Salts/mixtures and conflicting duplicates are rejected by preparation. "
                                "Internal scaffold holdout is not external validation.")
    return text, provenance, raw, metadata, evidence
