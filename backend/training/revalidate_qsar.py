"""Retrospective fixed held-out QSAR validation from a verified frozen ChEMBL snapshot."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import warnings

import joblib
import numpy as np
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import matthews_corrcoef, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from app.ai_research_agent.evaluation import metrics as evaluate, scaffold_split
from app.ai_research_agent.security import write_json
from app.chemistry import fingerprints as fp, qsar_core as core
from app.chemistry.qsar_evidence import FEATURE_CONFIG, admission, describe_model
from app.model_quality import classification_reasons

ALGORITHMS = ("random_forest", "logistic_regression", "gradient_boosting")
PLAN = dict(schema_version=2, seed=42, target_id="CHEMBL230", source_version="ChEMBL_37", assay_id="panel",
            algorithms=list(ALGORITHMS), forest_trees=200, logistic_C=1., logistic_max_iter=2000,
            boosting_trees=100, boosting_depth=2, cpu_threads=1,
            label="Measured standard_value IC50 in nM <= 1000; exact relations only; missing outcomes excluded",
            pchembl_consistency_tolerance=.011, curation="Reject mixed fragments, >200 atoms, conflicting parent labels; uncharge; canonical isomeric SMILES",
            split="Whole nonchiral Murcko groups by sizes only, seed42, .64/.16/.20; all acyclic molecules share one group",
            support=dict(train_per_class=30, validation_per_class=10, test_per_class=30, min_groups_per_partition=3),
            validation_gate=dict(balanced_accuracy="strictly >0.60", roc_auc="at least .75", mcc="at least .25"),
            selection="Highest validation PR-AUC among validation-qualified fixed candidates; no tuning or seed search",
            y_randomization="Selected procedure; train-only permuted labels, three outer scaffold folds; AUC <= .60; no test data",
            test_gate="Same accuracy/AUC/MCC gates plus complete support and PR-AUC better than train-fitted prior baseline",
            final_fit="Save the exact train-only fitted selected object; no validation/test refit",
            scientific_status="Retrospective internal holdout of a previously studied panel, not independent external/prospective evidence")


def snapshot(source, output):
    original = json.loads((source / "provenance.json").read_text(encoding="utf-8"))
    if original.get("target_id") != PLAN["target_id"] or original.get("version") != PLAN["source_version"] or original.get("assay_id") != "panel":
        raise ValueError("Expected the frozen ChEMBL37 human COX-2 panel")
    payloads, files = {}, []
    for record in original["sources"]:
        name = record["file"]
        if Path(name).name != name or len(record["sha256"]) != 64:
            raise ValueError("Invalid snapshot source path/hash")
        raw = (source / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError("Frozen source checksum mismatch: " + name)
        payloads[name] = json.loads(raw)
        files.append(dict(file=name, sha256=record["sha256"], url=record["url"]))
        (output / name).write_bytes(raw)
    target = payloads["target.json"]
    if target.get("organism") != "Homo sapiens" or target.get("target_type") != "SINGLE PROTEIN":
        raise ValueError("Expected human single-protein source")
    for name in ("chembl-status.json", "chembl-status-after.json"):
        if payloads[name]["chembl_db_version"] != PLAN["source_version"]:
            raise ValueError("Source version changed or is incompatible")
    catalog = payloads["assays.json"]
    if len(catalog["assays"]) != catalog["page_meta"]["total_count"]:
        raise ValueError("Incomplete assay catalog")
    allowed = {a["assay_chembl_id"] for a in catalog["assays"]
               if a.get("target_chembl_id") == PLAN["target_id"] and a.get("assay_type") == "B" and a.get("confidence_score") == 9}
    records, total = [], None
    for name in sorted(key for key in payloads if key.startswith("activities-")):
        page = payloads[name]
        current = page["page_meta"]["total_count"]
        if current > 10000 or (total is not None and current != total) or page["page_meta"]["offset"] != len(records):
            raise ValueError("Inconsistent or incomplete frozen activity pagination")
        total = current
        records += page["activities"]
    if len(records) != total or len({r["activity_id"] for r in records}) != len(records):
        raise ValueError("Incomplete/duplicate frozen activity rows")
    return records, allowed, dict(original, sources=files, source_provenance_sha256=hashlib.sha256((source / "provenance.json").read_bytes()).hexdigest(),
                                  curation_version="3.2.9", curation_time=datetime.now(timezone.utc).isoformat()), target


def curate(records, allowed):
    rejected, buckets = Counter(), defaultdict(list)
    for row in records:
        if (row.get("assay_chembl_id") not in allowed or row.get("target_chembl_id") != PLAN["target_id"]
                or row.get("target_organism") != "Homo sapiens" or row.get("assay_type") != "B"
                or row.get("standard_type") != "IC50" or row.get("standard_units") != "nM" or row.get("standard_relation") != "="
                or row.get("data_validity_comment") or row.get("potential_duplicate") not in (0, False, None)):
            rejected["assay_or_quality_filter"] += 1
            continue
        try:
            value, pchembl = float(row["standard_value"]), float(row["pchembl_value"])
            if not math.isfinite(value) or value <= 0 or not math.isfinite(pchembl) or abs(9-math.log10(value)-pchembl) > .011:
                raise ValueError("Invalid or inconsistent measured IC50/pChEMBL")
            mol = fp.mol_from_smiles(row.get("canonical_smiles") or "")
            if mol is None or len(Chem.GetMolFrags(mol)) != 1 or mol.GetNumAtoms() > 200:
                raise ValueError("Invalid, mixed or oversized structure")
            mol = fp.standardize(mol)
            key = Chem.MolToSmiles(mol, isomericSmiles=True)
            buckets[key].append(dict(value_nM=value, label=int(value <= 1000), activity_id=row["activity_id"], assay_id=row["assay_chembl_id"]))
        except (ValueError, TypeError, KeyError):
            rejected["measurement_or_structure_error"] += 1
    rows = []
    for smiles, measurements in sorted(buckets.items()):
        if len({row["label"] for row in measurements}) != 1:
            rejected["conflicting_compound"] += 1
            continue
        mol = fp.mol_from_smiles(smiles)
        rows.append(dict(smiles=smiles, label=measurements[0]["label"], measurements=measurements,
                         scaffold=MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False) or "ACYCLIC"))
    return rows, dict(rejected)


def fit(name, X, y, groups, seed=42):
    if name == "random_forest":
        return core.fit_model(X, y, 200, seed, groups)
    if name == "logistic_regression":
        return make_pipeline(StandardScaler(), LogisticRegression(C=1., class_weight="balanced", max_iter=2000, random_state=seed)).fit(X, y)
    if name == "gradient_boosting":
        return GradientBoostingClassifier(n_estimators=100, max_depth=2, random_state=seed).fit(X, y)
    raise ValueError("Unknown fixed candidate")


def measure(model, X, y):
    result = evaluate(model, X, y, "classification")
    result.update(mcc=float(matthews_corrcoef(y, model.predict(X))), n_evaluated=len(y))
    return result


def experiment(rows, checkpoint=lambda value: None):
    X = np.stack([fp.fingerprint_array(fp.mol_from_smiles(row["smiles"])) for row in rows]).astype(np.uint8)
    y = np.asarray([row["label"] for row in rows], dtype=int)
    groups = np.asarray([row["scaffold"] for row in rows])
    tr, va, te = scaffold_split(y, groups, 42)
    support = {}
    for name, indices in (("train", tr), ("validation", va), ("test", te)):
        support[name] = dict(molecules=len(indices), positive=int((y[indices] == 1).sum()), negative=int((y[indices] == 0).sum()), scaffolds=len(np.unique(groups[indices])))
        if min(support[name]["positive"], support[name]["negative"]) < (10 if name == "validation" else 30):
            raise ValueError("Insufficient class support: " + name)
    report = dict(support=support, split=dict(train=tr.tolist(), validation=va.tolist(), test=te.tolist()),
                  test_used_for_selection=False, candidates=[], plan=PLAN)
    models = []
    with threadpool_limits(limits=1), warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        for name in ALGORITHMS:
            checkpoint("validation:" + name)
            try:
                model = fit(name, X[tr], y[tr], groups[tr])
                validation = measure(model, X[va], y[va])
                reason = classification_reasons(validation, min_auc=.75, min_mcc=.25)
                report["candidates"].append(dict(algorithm=name, validation=validation, reasons=reason))
                if not reason:
                    models.append((model, name, validation))
            except (ValueError, ConvergenceWarning) as error:
                report["candidates"].append(dict(algorithm=name, error=str(error)))
        if not models:
            return None, report, "No candidate passed validation; test remains unused", X, y, groups
        model, name, validation = max(models, key=lambda item: item[2]["pr_auc"])
        procedure = describe_model(model, groups[tr])
        report.update(selected=name, validation=validation, procedure=procedure)
        checkpoint("train_only_y_randomization:" + name)
        shuffled = np.random.default_rng(42).permutation(y[tr])
        oof = np.full(len(tr), np.nan)
        folds = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=42).split(X[tr], shuffled, groups[tr])
        for fold, (left, right) in enumerate(folds):
            null_model = fit(name, X[tr][left], shuffled[left], groups[tr][left])
            oof[right] = null_model.predict_proba(X[tr][right])[:, 1]
        if not np.isfinite(oof).all():
            raise ValueError("Incomplete train-only randomization evaluation")
        null_auc = float(roc_auc_score(shuffled, oof))
        report["y_randomization"] = dict(roc_auc=null_auc, n_evaluated=len(tr), folds=3, partition="train_only", used_for_selection=False)
        if null_auc > .60:
            return None, report, "Train-only label randomization failed; test remains unused", X, y, groups
        checkpoint("fixed_held_out_test:" + name)
        test = measure(model, X[te], y[te])
        baseline = measure(DummyClassifier(strategy="prior").fit(X[tr], y[tr]), X[te], y[te])
        report.update(test=test, baseline_test=baseline, beats_baseline=test["pr_auc"] > baseline["pr_auc"])
    return model, report, None, X, y, groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.output_dir
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("Use a fresh output directory; experiments cannot be overwritten")
    write_json(root / "PLAN.json", PLAN)  # Written before curation or performance evaluation.
    def checkpoint(stage):
        write_json(root / "state.json", dict(stage=stage, status="running"))
        print(stage, flush=True)
    records, allowed, provenance, target = snapshot(args.source_dir, root)
    rows, excluded = curate(records, allowed)
    write_json(root / "curated.json", rows)
    write_json(root / "provenance.json", provenance)
    print(json.dumps(dict(raw=len(records), accepted=len(rows), excluded=excluded)), flush=True)
    model, evaluation, reason, X, y, groups = experiment(rows, checkpoint)
    np.savez_compressed(root / "features.npz", X=X, y=y, groups=groups)
    report = dict(accepted=False, raw_rows=len(records), unique_compounds=len(rows), excluded=excluded, evaluation=evaluation,
                  provenance=provenance, plan=PLAN, reasons=[reason] if reason else [])
    if model is not None:
        tr = evaluation["split"]["train"]
        meta = dict(schema_version=2, model_id="CHEMBL230-panel-3.2.9", model_version="3.2.9", target_id="CHEMBL230",
                    assay_id="panel", label="COX-2 · IC50 ≤ 1000 nM · panel", chembl_name=target["pref_name"],
                    active_pchembl=6., active_threshold_nM=1000., n_total=len(rows), n_train=len(tr), n_test=evaluation["support"]["test"]["molecules"],
                    n_active=evaluation["support"]["train"]["positive"], n_inactive=evaluation["support"]["train"]["negative"],
                    metrics=evaluation["test"], evaluation=evaluation, provenance=provenance, feature_config=FEATURE_CONFIG,
                    procedure=evaluation["procedure"], trained_at=datetime.now(timezone.utc).isoformat(),
                    dataset_sha256=hashlib.sha256((root / "curated.json").read_bytes()).hexdigest(),
                    scientific_status=PLAN["scientific_status"])
        meta["quality"] = admission(meta)
        report["reasons"] = meta["quality"]["reasons"]
        if meta["quality"]["passed"]:
            model_file = "CHEMBL230-panel-3.2.9.joblib"
            packed = core.pack_bits(X[tr])
            joblib.dump(dict(model=model, meta=meta, train_packed=packed, train_popcount=core.popcounts(packed), train_groups=groups[tr]), root / model_file, compress=3)
            digest = hashlib.sha256((root / model_file).read_bytes()).hexdigest()
            write_json(root / "manifest.json", dict(models=[dict(meta, model_file=model_file, artifact_sha256=digest)]))
            report.update(accepted=True, model_file=model_file, artifact_sha256=digest)
    if not report["accepted"]:
        write_json(root / "manifest.json", dict(models=[]))
    write_json(root / "report.json", report)
    write_json(root / "state.json", dict(status="completed" if report["accepted"] else "declined", stage="evaluated", reasons=report["reasons"]))
    print(json.dumps(dict(accepted=report["accepted"], selected=evaluation.get("selected"), test=evaluation.get("test"), reasons=report["reasons"])), flush=True)
    return 0 if report["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
