"""Train a traceable human single-protein IC50 research classifier from ChEMBL."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics

import httpx
import joblib
import numpy as np
from rdkit import Chem
import sklearn

from app.chemistry import fingerprints as fp, qsar_core as core

BASE = "https://www.ebi.ac.uk/chembl/api/data"


def prepare(records, target, assay):
    compounds = defaultdict(list)
    rejected = defaultdict(int)
    for row in records:
        if (row.get("target_chembl_id") != target or (assay is not None and row.get("assay_chembl_id") != assay)
                or row.get("standard_type") != "IC50" or row.get("standard_relation") != "="
                or row.get("standard_units") != "nM" or row.get("target_organism") != "Homo sapiens"
                or row.get("assay_type") != "B" or row.get("data_validity_comment")
                or row.get("potential_duplicate") not in (0, False, None)):
            rejected["assay_or_quality_filter"] += 1
            continue
        try:
            value = float(row["pchembl_value"])
            if not np.isfinite(value):
                raise ValueError("Non-finite activity")
            mol = fp.mol_from_smiles(row.get("canonical_smiles") or "")
            if mol is None:
                raise ValueError("Invalid SMILES")
            mol = fp.standardize(mol)
            key = Chem.MolToSmiles(mol, isomericSmiles=True)
            compounds[key].append((value, mol, row["activity_id"], row["assay_chembl_id"]))
        except (ValueError, TypeError, KeyError):
            rejected["invalid_structure_or_value"] += 1
    rows = []
    for smiles, measurements in sorted(compounds.items()):
        if len({item[0] >= 6.0 for item in measurements}) != 1:
            rejected["conflicting_compound"] += 1
            continue
        value = statistics.median(item[0] for item in measurements)
        mol = measurements[0][1]
        rows.append(dict(smiles=smiles, pchembl=value, label=int(value >= 6.0),
                         activity_ids=[item[2] for item in measurements],
                         assay_ids=sorted({item[3] for item in measurements}),
                         scaffold=fp.scaffold_smiles(mol)))
    return rows, dict(rejected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="CHEMBL230")
    parser.add_argument("--assay", default="panel", help="ChEMBL assay ID, or panel for all confidence-9 IC50 binding assays")
    parser.add_argument("--source-dir", type=Path, help="Optional previously downloaded assay/activity JSON snapshots")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--seed", default=42, type=int)
    args = parser.parse_args()
    if not all(value.startswith("CHEMBL") and value[6:].isdigit() for value in [args.target, *([] if args.assay == "panel" else [args.assay])]):
        raise ValueError("Expected ChEMBL target and assay identifiers")
    root = args.output_dir
    root.mkdir(parents=True, exist_ok=True)
    if (root / "report.json").exists():
        raise ValueError("Use a fresh output directory; previous reports are immutable")
    sources = []
    cached_provenance = {}
    if args.source_dir and (args.source_dir / "provenance.json").is_file():
        cached_provenance = json.loads((args.source_dir / "provenance.json").read_text(encoding="utf-8"))
        if cached_provenance.get("target_id") != args.target or cached_provenance.get("assay_id") != args.assay:
            raise ValueError("Cached provenance does not match requested target/assay")
    with httpx.Client(timeout=90, follow_redirects=False) as client:
        def fetch(name, endpoint, params=None):
            cached_name = name
            if name.startswith("activities-"):
                cached_name = f"activities-{int(name[11:-5])}.json"
            cached = args.source_dir / name if args.source_dir else None
            if cached and not cached.is_file():
                cached = args.source_dir / cached_name
            if cached_provenance and cached and not cached.is_file():
                raise ValueError(f"Incomplete frozen dataset snapshot: {name}")
            if cached and cached.is_file():
                raw = cached.read_bytes()
                url = str(client.build_request("GET", BASE + endpoint, params=params).url)
            else:
                response = client.get(BASE + endpoint, params=params)
                response.raise_for_status()
                raw, url = response.content, str(response.url)
            payload = json.loads(raw)
            (root / name).write_bytes(raw)
            sources.append(dict(file=name, url=url, sha256=hashlib.sha256(raw).hexdigest(), cached=bool(cached and cached.is_file())))
            return payload
        status = fetch("chembl-status.json", "/status.json")
        target = fetch("target.json", f"/target/{args.target}.json")
        if args.assay == "panel":
            catalog = fetch("assays.json", "/assay.json", {"target_chembl_id": args.target, "confidence_score": 9, "assay_type": "B", "limit": 1000})
            if len(catalog["assays"]) != catalog["page_meta"]["total_count"]:
                raise ValueError("Assay catalog exceeds import page limit")
            assays = catalog["assays"]
        else:
            assays = [fetch("assay.json", f"/assay/{args.assay}.json")]
        if (any(a.get("target_chembl_id") != args.target or a.get("assay_type") != "B" or a.get("confidence_score") != 9 for a in assays)
                or target.get("organism") != "Homo sapiens"
                or target.get("target_type") != "SINGLE PROTEIN"):
            raise ValueError("Expected high-confidence human single-protein binding assay")
        records = []
        for offset in range(0, 10000, 1000):
            page = fetch(f"activities-{offset:05d}.json", "/activity.json", {
                "target_chembl_id": args.target, **({"assay_chembl_id": args.assay} if args.assay != "panel" else {"assay_type": "B"}),
                "standard_type": "IC50", "standard_relation": "=", "standard_units": "nM",
                "pchembl_value__isnull": "false", "order_by": "activity_id", "limit": 1000, "offset": offset,
            })
            if page["page_meta"]["total_count"] > 10000:
                raise ValueError("Assay exceeds bounded import limit")
            records.extend(page["activities"])
            if len(records) >= page["page_meta"]["total_count"]:
                break
        final_status = fetch("chembl-status-after.json", "/status.json")
        if status["chembl_db_version"] != final_status["chembl_db_version"]:
            raise ValueError("ChEMBL version changed during download")
    allowed = {a["assay_chembl_id"] for a in assays}
    eligible = [row for row in records if row["assay_chembl_id"] in allowed]
    rows, excluded = prepare(eligible, args.target, None if args.assay == "panel" else args.assay)
    excluded["assay_confidence"] = len(records) - len(eligible)
    provenance = dict(source="ChEMBL", version=status["chembl_db_version"], target_id=args.target,
                      assay_id=args.assay, assays=[dict(id=a["assay_chembl_id"], description=a.get("description"), document=a.get("document_chembl_id")) for a in assays if a["assay_chembl_id"] in {r["assay_chembl_id"] for r in eligible}], endpoint="IC50", units="nM",
                      organism="Homo sapiens", retrieved_at=cached_provenance.get("retrieved_at", datetime.now(timezone.utc).isoformat()),
                      license="CC-BY-SA-3.0", license_url="https://creativecommons.org/licenses/by-sa/3.0/",
                      attribution="ChEMBL contributors, EMBL-EBI", sources=sources)
    (root / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    (root / "curated.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    y = np.array([row["label"] for row in rows], dtype=int)
    n_active = int(y.sum())
    n_inactive = len(y) - n_active
    report = dict(target_id=args.target, assay_id=args.assay, raw_rows=len(records), unique_compounds=len(rows),
                  active=n_active, inactive=n_inactive, excluded=excluded, threshold="pChEMBL >= 6 (IC50 <= 1 micromolar)",
                  provenance=provenance, accepted=False, seed=args.seed,
                  limitations=["Internal scaffold cross-validation only; no independent external validation.",
                               "Assays use the same human target and IC50 endpoint but protocols may differ; no assay-held-out validation.",
                               "Small and imbalanced data; similarity applicability rule is heuristic."])
    groups = np.array([row["scaffold"] for row in rows])
    group_counts = {label: len({groups[i] for i in range(len(y)) if y[i] == label}) for label in (0, 1)}
    report["scaffolds_by_class"] = group_counts
    print(json.dumps({k: report[k] for k in ["raw_rows", "unique_compounds", "active", "inactive", "scaffolds_by_class"]}), flush=True)
    if min(n_active, n_inactive) < 30 or min(group_counts.values(), default=0) < 5:
        report["reasons"] = ["Insufficient compounds or scaffolds per class"]
    else:
        X = np.stack([fp.fingerprint_array(fp.mol_from_smiles(row["smiles"])) for row in rows]).astype(np.uint8)
        metrics = core.cross_validate(X, y, groups, seed=args.seed)
        randomized = core.y_randomization_auc(X, y, groups, seed=args.seed)
        reasons = core.quality_gate(metrics, n_active, n_inactive, randomized)
        if metrics is None or metrics.get("n_evaluated") != len(y):
            reasons.append("Incomplete out-of-fold evaluation")
        if randomized is None:
            reasons.append("Label randomization evaluation unavailable")
        report.update(metrics=metrics, y_random_auc=randomized, reasons=reasons)
        if not reasons:
            model = core.train_final(X, y, seed=args.seed)
            packed = core.pack_bits(X)
            label = "COX-2" if args.target == "CHEMBL230" else target["pref_name"]
            meta = dict(target_id=args.target, label=label + " · IC50 · " + args.assay, chembl_name=target["pref_name"],
                        model_id=f"{args.target}-{args.assay}-3.2.1", model_version="3.2.1", assay_id=args.assay,
                        active_pchembl=6.0, n_train=len(y), n_active=n_active, n_inactive=n_inactive,
                        metrics=metrics, y_random_auc=randomized, trained_at=datetime.now(timezone.utc).isoformat(),
                        sklearn_version=sklearn.__version__, n_bits=fp.N_BITS, radius=fp.RADIUS, provenance=provenance,
                        scientific_status="experimental; internal quality gates passed")
            model_file = f"{args.target}-{args.assay}-3.2.1.joblib"
            joblib.dump(dict(model=model, train_packed=packed, train_popcount=core.popcounts(packed), meta=meta), root / model_file, compress=3)
            report.update(accepted=True, model_file=model_file)
            digest = hashlib.sha256((root / model_file).read_bytes()).hexdigest()
            (root / "manifest.json").write_text(json.dumps({"models": [{**meta, "model_file": model_file, "artifact_sha256": digest}]}, indent=2), encoding="utf-8")
    (root / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report.get(k) for k in ["accepted", "metrics", "y_random_auc", "reasons"]}), flush=True)
    return 0 if report["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
