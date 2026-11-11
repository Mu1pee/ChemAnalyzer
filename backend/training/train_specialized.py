"""Train endpoint-specific models for ПК «Антидот-Прогноз».

Run from backend:
    python -m training.train_specialized
    python -m training.train_specialized --domain antidote

Data sources must be curated and traceable. Each endpoint/context is trained
as a separate binary task. No model is emitted unless sample-size and held-out
quality gates pass on a test excluded from model selection. A matching protocol
sidecar with source rights and experimental conditions is required.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import joblib
import numpy as np
import sklearn
from rdkit import Chem
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.dummy import DummyClassifier
from sklearn.metrics import matthews_corrcoef
from threadpoolctl import threadpool_limits
from rdkit.Chem.Scaffolds import MurckoScaffold

from app import config
from app.model_quality import classification_reasons, finite, held_out_quality
from app.ai_research_agent.evaluation import metrics as evaluate_metrics, scaffold_split
from app.ai_research_agent.security import write_json
from app.chemistry.specialized_evidence import FEATURE_CONFIG, SpecializedProtocol, quality
from app.chemistry import fingerprints as fp
from app.chemistry import qsar_core as core

DATA_DIR = Path(__file__).resolve().parent / "specialized_data"
DOMAINS = {
    "antidote": "antidote.csv",
    "growth_regulating": "growth_regulating.csv",
}
REQUIRED_COLUMNS = {"smiles", "label", "endpoint", "context", "source", "source_id"}
MODEL_MIN_PER_CLASS = 30
MODEL_MIN_SCAFFOLDS_PER_CLASS = 5
MODEL_MIN_AUC_DEFAULT = 0.70
MODEL_MIN_BALANCED_ACC = 0.60
MODEL_MIN_MCC = 0.10

ALGORITHMS = ("random_forest", "logistic_regression", "gradient_boosting")


def create_model(algorithm: str, seed: int, final: bool = False):
    if algorithm == "logistic_regression":
        return LogisticRegression(class_weight="balanced", max_iter=2000, random_state=seed)
    if algorithm == "gradient_boosting":
        return GradientBoostingClassifier(n_estimators=100, max_depth=2, random_state=seed)
    if algorithm != "random_forest":
        raise ValueError(f"Unknown algorithm: {algorithm}")
    return RandomForestClassifier(n_estimators=200,
                                  class_weight="balanced_subsample", n_jobs=1,
                                  random_state=seed, min_samples_leaf=2)


def parse_label(value: str) -> int:
    raw = str(value).strip().lower()
    if raw in {"1", "active", "активен", "активная", "positive", "положительный"}:
        return 1
    if raw in {"0", "inactive", "неактивен", "неактивная", "negative", "отрицательный"}:
        return 0
    raise ValueError("label должен быть 0/1 (неактивный/активный по выбранному endpoint).")


def read_dataset(path: Path) -> tuple[dict, list[str]]:
    report = {"file": path.name, "rows_read": 0, "rows_used": 0, "invalid_rows": 0,
              "conflicting_duplicates": 0, "groups": [], "errors": []}
    tasks: dict[tuple[str, str], dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    if not path.is_file():
        return report, [f"Файл данных не найден: {path}"]

    with path.open("rb") as handle:
        raw = handle.read(8_000_001)
    if len(raw) > 8_000_000:
        return report, ["Dataset exceeds 8 MB limit"]
    report["dataset_sha256"] = hashlib.sha256(raw).hexdigest()
    with io.StringIO(raw.decode("utf-8-sig"), newline="") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        if len(headers) != len(reader.fieldnames or []):
            return report, ["Duplicate CSV column names are not permitted"]
        missing = REQUIRED_COLUMNS - headers
        if missing:
            return report, ["В CSV отсутствуют столбцы: " + ", ".join(sorted(missing))]

        for line_number, row in enumerate(reader, start=2):
            if None not in row and not any((value or "").strip() for value in row.values()):
                continue
            report["rows_read"] += 1
            if report["rows_read"] > 50000:
                return report, ["Dataset exceeds 50,000-row limit"]
            if None in row:
                report["invalid_rows"] += 1
                report["errors"].append(f"Строка {line_number}: лишние поля CSV")
                continue
            try:
                smiles = (row.get("smiles") or "").strip()
                endpoint = (row.get("endpoint") or "").strip()
                context = (row.get("context") or "").strip()
                source = (row.get("source") or "").strip()
                source_id = (row.get("source_id") or "").strip()
                if not all((smiles, endpoint, context, source, source_id)):
                    raise ValueError("smiles, endpoint, context, source и source_id обязательны")
                label = parse_label(row.get("label") or "")
                mol = fp.mol_from_smiles(smiles)
                if mol is None:
                    raise ValueError("некорректный SMILES")
                if len(Chem.GetMolFrags(mol)) != 1 or mol.GetNumAtoms() > 200:
                    raise ValueError("соль, смесь или слишком большая структура: нужна явная курация")
                mol = fp.standardize(mol)
                canonical = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
                if not canonical:
                    raise ValueError("не удалось канонизировать SMILES")
                scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False) or "ACYCLIC"
                tasks[(endpoint, context)][canonical].append({
                    "label": label, "mol": mol, "scaffold": scaffold,
                    "source": source, "source_id": source_id,
                })
            except Exception as error:
                report["invalid_rows"] += 1
                report["errors"].append(f"Строка {line_number}: {error}")

    prepared = []
    for (endpoint, context), records in tasks.items():
        unique = []
        conflicts = 0
        for canonical, observations in records.items():
            labels = {item["label"] for item in observations}
            if len(labels) != 1:
                conflicts += 1
                continue
            item = observations[0]
            unique.append({
                "smiles": canonical, "mol": item["mol"], "label": item["label"],
                "scaffold": item["scaffold"],
                "sources": sorted({f"{o['source']} — {o['source_id']}" for o in observations}),
            })
        report["conflicting_duplicates"] += conflicts
        if unique:
            prepared.append({"endpoint": endpoint, "context": context, "rows": unique})
    report["rows_used"] = sum(len(task["rows"]) for task in prepared)
    report["groups"] = [
        {
            "endpoint": task["endpoint"],
            "context": task["context"],
            "unique_compounds": len(task["rows"]),
            "active": sum(row["label"] == 1 for row in task["rows"]),
            "inactive": sum(row["label"] == 0 for row in task["rows"]),
        }
        for task in prepared
    ]
    return {"report": report, "tasks": prepared}, []


def fit_endpoint(domain: str, task: dict, min_per_class: int, min_auc: float, seed: int, algorithm: str = "auto") -> tuple[tuple[str, dict] | None, str | None, dict]:
    rows = task["rows"]
    y = np.asarray([row["label"] for row in rows], dtype=np.int8)
    n_active = int(y.sum())
    n_inactive = int(len(y) - n_active)
    scaffold_values = [row["scaffold"] for row in rows]
    groups = np.asarray([hashlib.sha1(v.encode("utf-8")).hexdigest()[:16] for v in scaffold_values])
    unique_groups_by_class = {
        cls: len({groups[i] for i, value in enumerate(y) if int(value) == cls})
        for cls in (0, 1)
    }

    report = {
        "domain": domain,
        "endpoint": task["endpoint"],
        "context": task["context"],
        "n_train": len(rows),
        "n_active": n_active,
        "n_inactive": n_inactive,
        "unique_scaffolds": len(set(groups.tolist())),
        "scaffolds_by_class": {str(k): v for k, v in unique_groups_by_class.items()},
        "accepted": False,
        "reasons": [],
    }

    reasons = []
    if min_per_class < MODEL_MIN_PER_CLASS or not finite(min_auc) or not MODEL_MIN_AUC_DEFAULT <= min_auc <= 1:
        reasons.append("Нельзя ослаблять пороги: минимум 30 соединений класса и ROC-AUC >= 0.70")
    if n_active < min_per_class or n_inactive < min_per_class:
        reasons.append(f"нужно не менее {min_per_class} примеров каждого класса; получено {n_active}/{n_inactive}")
    if min(unique_groups_by_class.values()) < MODEL_MIN_SCAFFOLDS_PER_CLASS:
        reasons.append(f"нужно не менее {MODEL_MIN_SCAFFOLDS_PER_CLASS} разных скаффолдов каждого класса")
    if reasons:
        report["reasons"] = reasons
        return None, "; ".join(reasons), report

    try:
        protocol = SpecializedProtocol.model_validate(task.get("protocol"))
        if any(getattr(protocol, key) != value for key, value in
               (("domain", domain), ("endpoint", task["endpoint"]), ("context", task["context"]))):
            raise ValueError("Protocol must match the complete endpoint/context task")
        algorithms = ALGORITHMS if algorithm == "auto" else (algorithm,)
        if any(name not in ALGORITHMS for name in algorithms):
            raise ValueError("Unknown algorithm")
        X = np.stack([fp.fingerprint_array(row["mol"]) for row in rows]).astype(np.uint8)
        train_idx, validation_idx, test_idx = scaffold_split(y, groups, seed)
        split = dict(train=train_idx, validation=validation_idx, test=test_idx)
        support = {}
        for name, indices in split.items():
            support[name] = dict(molecules=len(indices), scaffolds=len(np.unique(groups[indices])),
                                 positive=int((y[indices] == 1).sum()), negative=int((y[indices] == 0).sum()))
            minimum = min_per_class if name == "train" else 10 if name == "test" else 5
            if min(support[name]["positive"], support[name]["negative"]) < minimum:
                raise ValueError(f"Insufficient {name} class support: need {minimum} compounds/class")
        if any(len(np.unique(groups[train_idx][y[train_idx] == cls])) < MODEL_MIN_SCAFFOLDS_PER_CLASS for cls in (0, 1)):
            raise ValueError("Training partition needs at least five scaffold groups/class")
        def measure(estimator, indices):
            result = evaluate_metrics(estimator, X[indices], y[indices], "classification")
            result.update(mcc=float(matthews_corrcoef(y[indices], estimator.predict(X[indices]))), n_evaluated=len(indices))
            return result
        candidates = []
        with threadpool_limits(limits=1):
            for name in algorithms:
                candidate = create_model(name, seed)
                candidate.fit(X[train_idx], y[train_idx])
                validation = measure(candidate, validation_idx)
                candidates.append((candidate, dict(algorithm=name, validation=validation)))
            eligible = [item for item in candidates if not classification_reasons(item[1]["validation"], min_auc, MODEL_MIN_MCC)]
            if not eligible:
                raise ValueError("No candidate passed validation quality; held-out test remains unused")
            final_model, winner = max(eligible, key=lambda item: item[1]["validation"]["pr_auc"])
            # Never refit after this evaluation: the shipped object is exactly
            # the train-only fitted model evaluated here, including tree count.
            metrics = measure(final_model, test_idx)
            baseline = DummyClassifier(strategy="prior").fit(X[train_idx], y[train_idx])
            baseline_metrics = measure(baseline, test_idx)
        evaluation = dict(test=metrics, baseline_test=baseline_metrics, support=support,
                          validation=winner["validation"], candidates=[item[1] for item in candidates], selected=winner["algorithm"],
                          split={name: indices.tolist() for name, indices in split.items()},
                          split_method="scaffold groups by size only; fixed train/validation/test; no post-test refit",
                          test_used_for_selection=False, beats_baseline=metrics["pr_auc"] > baseline_metrics["pr_auc"])
        report.update(metrics=metrics, evaluation=evaluation)
        reasons = held_out_quality("classification", evaluation)["reasons"] + classification_reasons(metrics, min_auc, MODEL_MIN_MCC)
        if reasons:
            raise ValueError("; ".join(dict.fromkeys(reasons)))
    except ValueError as error:
        report["reasons"] = [str(error)]
        return None, str(error), report
    packed = core.pack_bits(X[train_idx])
    source_values = sorted({source for row in rows for source in row["sources"]})
    model_key = uuid4().hex
    model_file = f"{domain}_{model_key}.joblib"
    meta = {
        "domain": domain,
        "endpoint": task["endpoint"],
        "context": task["context"],
        "schema_version": 2,
        "model_version": "2.0",
        "algorithm": winner["algorithm"],
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sklearn_version": sklearn.__version__,
        "n_train": len(train_idx),
        "n_total": len(rows),
        "n_active": support["train"]["positive"],
        "n_inactive": support["train"]["negative"],
        "n_test": len(test_idx),
        "metrics": metrics,
        "evaluation": evaluation,
        "protocol": protocol.model_dump(),
        "dataset_sha256": protocol.dataset_sha256,
        "feature_config": FEATURE_CONFIG,
        "scientific_status": "experimental; internal held-out test, no external validation; uncalibrated probabilities",
        "decision_threshold": 0.5,
        "decision_rule": "estimator.predict with fixed class ordering 0/1; no threshold tuning",
        "domain_edge_threshold": core.DOMAIN_EDGE,
        "dataset_source": " | ".join(source_values[:10]),
        "source_count": len(source_values),
        "fingerprint_bits": fp.N_BITS,
        "fingerprint_radius": fp.RADIUS,
        "label_definition": "label=1 означает активность по endpoint/context, как определено источником данных; label=0 — неактивность по тому же протоколу.",
    }
    bundle = {
        "model": final_model,
        "train_packed": packed,
        "train_popcount": core.popcounts(packed),
        "meta": meta,
    }
    admission = quality(meta)
    if not admission["passed"]:
        report["reasons"] = admission["reasons"]
        return None, "; ".join(admission["reasons"]), report
    report["accepted"] = True
    report["curated_records"] = [{key: row[key] for key in ("smiles", "label", "scaffold", "sources")} for row in rows]
    report["model_file"] = model_file
    return (model_file, bundle), None, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", choices=["all", *DOMAINS], default="all")
    parser.add_argument("--algorithm", choices=["auto", *ALGORITHMS], default="auto")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--models-dir", type=Path, default=config.models_dir() / "specialized_activity")
    parser.add_argument("--min-per-class", type=int, default=MODEL_MIN_PER_CLASS)
    parser.add_argument("--min-auc", type=float, default=MODEL_MIN_AUC_DEFAULT)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.min_per_class < MODEL_MIN_PER_CLASS or not finite(args.min_auc) or not MODEL_MIN_AUC_DEFAULT <= args.min_auc <= 1:
        parser.error("Требуется --min-per-class >= 30 и конечное 0.70 <= --min-auc <= 1")
    args.models_dir.mkdir(parents=True, exist_ok=True)

    domains = list(DOMAINS) if args.domain == "all" else [args.domain]
    accepted, rejected, summaries = [], [], []
    for domain in domains:
        path = args.data_dir / DOMAINS_FILE(domain)
        loaded, errors = read_dataset(path)
        if errors:
            rejected.append({"domain": domain, "file": path.name, "reason": "; ".join(errors)})
            summaries.append(loaded)
            continue
        summaries.append(loaded["report"])
        if not loaded["tasks"]:
            rejected.append({
                "domain": domain,
                "file": path.name,
                "reason": "нет пригодных экспериментальных строк; шаблон пуст или все строки некорректны",
            })
        for task in loaded["tasks"]:
            try:
                protocol_path = path.with_suffix(".protocol.json")
                protocol = SpecializedProtocol.model_validate_json(protocol_path.read_text(encoding="utf-8"))
                if protocol.dataset_sha256 != loaded["report"]["dataset_sha256"]:
                    raise ValueError("CSV checksum does not match the reviewed protocol sidecar")
                task["protocol"] = protocol.model_dump()
                result, reason, task_report = fit_endpoint(
                    domain, task, args.min_per_class, args.min_auc, args.seed, args.algorithm
                )
            except Exception as error:
                result, reason = None, f"ошибка обучения: {error}"
                task_report = {"domain": domain, "endpoint": task.get("endpoint"), "context": task.get("context"), "accepted": False, "reasons": [reason]}
            if result:
                model_file, bundle = result
                joblib.dump(bundle, args.models_dir / model_file, compress=3)
                accepted.append({"domain": domain, "model_file": model_file, **bundle["meta"],
                                 "artifact_sha256": hashlib.sha256((args.models_dir / model_file).read_bytes()).hexdigest()})
            else:
                rejected.append({**task_report, "reason": reason or "модель отклонена"})

    # Если обучается только одно направление, не удаляем уже обученные модели
    # другого направления из manifest. Для --domain all заменяем оба набора.
    preserved = []
    manifest_problem = None
    previous_manifest = args.models_dir / "manifest.json"
    if previous_manifest.is_file():
        try:
            old_manifest = json.loads(previous_manifest.read_text(encoding="utf-8"))
            if not isinstance(old_manifest, dict) or not isinstance(old_manifest.get("models", []), list):
                raise ValueError("Invalid previous manifest structure")
            old_records = old_manifest.get("models", [])
            accepted_domains = {record.get("domain") for record in accepted}
            for old in old_records if isinstance(old_records, list) else []:
                if not isinstance(old, dict):
                    continue
                old_domain = old.get("domain")
                # Replace a domain's old models only if at least one newly trained
                # model passed quality gates. If training failed, retain the last
                # known-good model but report the failed retraining in the report.
                should_preserve = old_domain not in domains or old_domain not in accepted_domains
                filename = old.get("model_file")
                if (should_preserve and isinstance(filename, str)
                        and Path(filename).name == filename
                        and "\\" not in filename and "/" not in filename
                        and (args.models_dir / filename).is_file()):
                    preserved.append(old)
        except (OSError, ValueError, TypeError) as error:
            manifest_problem = f"Previous manifest is unreadable and was preserved: {type(error).__name__}"

    manifest = {
        "schema_version": 2,
        "application": "ПК Антидот-Прогноз",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "models": [*preserved, *accepted],
    }
    if manifest_problem is None:
        write_json(args.models_dir / "manifest.json", manifest)
    report = {
        "application": "ПК Антидот-Прогноз",
        "data_dir": str(args.data_dir),
        "models_dir": str(args.models_dir),
        "accepted_count": len(accepted),
        "preserved_count": len(preserved),
        "manifest_model_count": len(manifest["models"]),
        "manifest_updated": manifest_problem is None,
        "manifest_error": manifest_problem,
        "rejected_count": len(rejected),
        "summaries": summaries,
        "accepted": accepted,
        "rejected": rejected,
        "thresholds": {
            "min_per_class": args.min_per_class,
            "min_auc": args.min_auc,
            "min_balanced_accuracy": MODEL_MIN_BALANCED_ACC,
            "min_mcc": MODEL_MIN_MCC,
        },
        "note": "Фиксированное разделение каркасов на train/validation/test. Алгоритм выбирается по validation, веса не переобучаются после test. Источник и права требуют независимой проверки; прогноз исследовательский.",
    }
    write_json(args.models_dir / "training_report.json", report)
    print(json.dumps({"accepted": len(accepted), "preserved": len(preserved), "rejected": len(rejected), "manifest_models": len(manifest["models"]), "models_dir": str(args.models_dir)}, ensure_ascii=False, indent=2))
    return 0 if accepted and manifest_problem is None else 1


def DOMAINS_FILE(domain: str) -> str:
    return "antidote.csv" if domain == "antidote" else "growth_regulating.csv"


if __name__ == "__main__":
    sys.exit(main())
