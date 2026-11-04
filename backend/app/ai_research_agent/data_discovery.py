"""Read-only discovery; only reviewed FreeSolv text is downloaded automatically."""
import csv
import io

import httpx

from .config import FREESOLV_TASK
from .security import checksum, utcnow

CATALOG = [
    {"id": "freesolv", "name": "FreeSolv", "endpoint": "hydration_free_energy",
     "url": "https://github.com/MobleyLab/FreeSolv", "license": "CC-BY-4.0",
     "status": "supported_text_adapter"},
    {"id": "pubchem", "name": "PubChem BioAssay", "url": "https://pubchem.ncbi.nlm.nih.gov/",
     "status": "discovery_lead_requires_assay_and_license_review"},
    {"id": "chembl", "name": "ChEMBL", "url": "https://www.ebi.ac.uk/chembl/",
     "status": "discovery_lead_requires_endpoint_and_context_review"},
    {"id": "zenodo", "name": "Zenodo", "url": "https://zenodo.org/",
     "status": "discovery_lead_requires_experimental_data_review"},
]


def discover(endpoint: str):
    return {"endpoint": endpoint, "sources": CATALOG,
            "message": "Only FreeSolv has an automatic import adapter. Other sources are leads, not verified datasets."}


def _fetch(url, limit=4_000_000):
    # URLs constructed internally from a fixed host, never from user input.
    with httpx.stream("GET", url, timeout=30, follow_redirects=False,
                      headers={"User-Agent": "ChemAnalyzer-Research/0.1"}) as response:
        response.raise_for_status()
        if response.is_redirect:
            raise ValueError("Redirect not permitted")
        chunks, size = [], 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > limit:
                raise ValueError("Source exceeds download limit")
            chunks.append(chunk)
    return b"".join(chunks)


def fetch_freesolv():
    import json
    import re
    commit = json.loads(_fetch("https://api.github.com/repos/MobleyLab/FreeSolv/commits/master"))["sha"]
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Invalid source revision")
    base = f"https://raw.githubusercontent.com/MobleyLab/FreeSolv/{commit}"
    license_data = _fetch(base + "/LICENSE")
    if b"Attribution 4.0" not in license_data and b"CC BY 4.0" not in license_data:
        raise ValueError("Source license requires manual review")
    raw = _fetch(base + "/database.txt")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["record_id", "smiles", "value", "reference", "uncertainty", "notes"])
    writer.writeheader()
    for line in raw.decode("utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        fields = [part.strip() for part in line.split(";")]
        if len(fields) < 10:
            raise ValueError("Unexpected FreeSolv record format")
        writer.writerow(dict(record_id=fields[0], smiles=fields[1], value=fields[3],
                             reference=fields[7], uncertainty=fields[4], notes=";".join(fields[9:])))
    provenance = dict(source_url=base + "/database.txt", doi="10.1007/s10822-014-9747-x",
                      license="CC-BY-4.0", license_url=base + "/LICENSE", source_version=commit,
                      retrieved_at=utcnow(), endpoint=FREESOLV_TASK["endpoint"],
                      units=FREESOLV_TASK["units"], context=FREESOLV_TASK["context"],
                      experimental=True, curator="FreeSolv reviewed text adapter")
    evidence = dict(raw_sha256=checksum(raw), license_sha256=checksum(license_data),
                    attribution="Mobley DL, Guthrie JP. FreeSolv (2014); MobleyLab contributors.",
                    limitations="Source conditions are not uniform; per-record references retained. Default uncertainty may be assigned by source. No calculated labels imported.")
    return output.getvalue(), provenance, raw, license_data, evidence
