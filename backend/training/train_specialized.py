"""Train endpoint-specific models for ПК «Антидот-Прогноз».

Run from backend:
    python -m training.train_specialized
    python -m training.train_specialized --domain antidote

Data sources must be curated and traceable. Each endpoint/context is trained
as a separate binary task. No model is emitted unless sample-size and CV
quality gates pass.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from rdkit import Chem
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    balanced_accuracy_score,
    matthews_corrcoef,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold

from app import config
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

    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - headers
        if missing:
            return report, ["В CSV отсутствуют столбцы: " + ", ".join(sorted(missing))]

        for line_number, row in enumerate(reader, start=2):
            if not any((value or "").strip() for value in row.values()):
                continue
            report["rows_read"] += 1
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
                mol = fp.standardize(mol)
                canonical = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
                if not canonical:
                    raise ValueError("не удалось канонизировать SMILES")
                scaffold = fp.scaffold_smiles(mol)
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


def fit_endpoint(domain: str, task: dict, min_per_class: int, min_auc: float, seed: int) -> tuple[tuple[str, dict] | None, str | None, dict]:
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
    if n_active < min_per_class or n_inactive < min_per_class:
        reasons.append(f"нужно не менее {min_per_class} примеров каждого класса; получено {n_active}/{n_inactive}")
    if min(unique_groups_by_class.values()) < MODEL_MIN_SCAFFOLDS_PER_CLASS:
        reasons.append(f"нужно не менее {MODEL_MIN_SCAFFOLDS_PER_CLASS} разных скаффолдов каждого класса")
    if reasons:
        report["reasons"] = reasons
        return None, "; ".join(reasons), report

    X = np.stack([fp.fingerprint_array(row["mol"]) for row in rows]).astype(np.uint8)
    n_splits = min(5, unique_groups_by_class[0], unique_groups_by_class[1])
    oof = np.full(len(y), np.nan, dtype=float)
    cv_failures = []
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)

    try:
        split_iterator = splitter.split(X, y, groups)
        for fold, (train_idx, test_idx) in enumerate(split_iterator, start=1):
            if len(np.unique(y[train_idx])) != 2:
                cv_failures.append(f"fold {fold}: обучающая часть содержит один класс")
                continue
            model = RandomForestClassifier(
                n_estimators=200,
                class_weight="balanced_subsample",
                n_jobs=-1,
                random_state=seed + fold,
                min_samples_leaf=2,
            )
            model.fit(X[train_idx], y[train_idx])
            classes = list(model.classes_)
            if 1 not in classes:
                cv_failures.append(f"fold {fold}: модель не обучила положительный класс")
                continue
            oof[test_idx] = model.predict_proba(X[test_idx])[:, classes.index(1)]
    except Exception as error:
        message = f"не удалось выполнить scaffold cross-validation: {error}"
        report["reasons"] = [message]
        return None, message, report

    mask = np.isfinite(oof)
    if mask.sum() == 0 or len(np.unique(y[mask])) != 2:
        message = "не удалось получить проверяемые out-of-fold прогнозы"
        report["reasons"] = [message, *cv_failures]
        return None, message, report

    y_true = y[mask]
    y_prob = oof[mask]
    y_pred = (y_prob >= 0.5).astype(np.int8)
    metrics = {
        "roc_auc": round(float(roc_auc_score(y_true, y_prob)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred)), 4),
        "mcc": round(float(matthews_corrcoef(y_true, y_pred)), 4),
        "n_evaluated": int(mask.sum()),
        "cv_folds": n_splits,
    }
    report["metrics"] = metrics
    if metrics["roc_auc"] < min_auc:
        reasons.append(f"ROC-AUC {metrics['roc_auc']} ниже порога {min_auc}")
    if metrics["balanced_accuracy"] < MODEL_MIN_BALANCED_ACC:
        reasons.append(f"balanced accuracy {metrics['balanced_accuracy']} ниже {MODEL_MIN_BALANCED_ACC}")
    if metrics["mcc"] < MODEL_MIN_MCC:
        reasons.append(f"MCC {metrics['mcc']} ниже {MODEL_MIN_MCC}")
    if reasons:
        report["reasons"] = reasons
        return None, "; ".join(reasons), report

    final_model = RandomForestClassifier(
        n_estimators=400,
        class_weight="balanced_subsample",
        n_jobs=-1,
        random_state=seed,
        min_samples_leaf=2,
    )
    final_model.fit(X, y)
    packed = core.pack_bits(X)
    source_values = sorted({source for row in rows for source in row["sources"]})
    model_key = hashlib.sha256(f"{domain}\0{task['endpoint']}\0{task['context']}".encode("utf-8")).hexdigest()[:16]
    model_file = f"{domain}_{model_key}.joblib"
    meta = {
        "domain": domain,
        "endpoint": task["endpoint"],
        "context": task["context"],
        "model_version": "1.0",
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sklearn_version": sklearn.__version__,
        "n_train": int(len(y)),
        "n_active": n_active,
        "n_inactive": n_inactive,
        "metrics": metrics,
        "decision_threshold": 0.5,
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
    report["accepted"] = True
    report["model_file"] = model_file
    return (model_file, bundle), None, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", choices=["all", *DOMAINS], default="all")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--models-dir", type=Path, default=config.models_dir() / "specialized_activity")
    parser.add_argument("--min-per-class", type=int, default=MODEL_MIN_PER_CLASS)
    parser.add_argument("--min-auc", type=float, default=MODEL_MIN_AUC_DEFAULT)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.min_per_class < 10:
        parser.error("--min-per-class не может быть меньше 10: для исследований нужна минимальная выборка")
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
                result, reason, task_report = fit_endpoint(
                    domain, task, args.min_per_class, args.min_auc, args.seed
                )
            except Exception as error:
                result, reason = None, f"ошибка обучения: {error}"
                task_report = {"domain": domain, "endpoint": task.get("endpoint"), "context": task.get("context"), "accepted": False, "reasons": [reason]}
            if result:
                model_file, bundle = result
                joblib.dump(bundle, args.models_dir / model_file, compress=3)
                accepted.append({"domain": domain, "model_file": model_file, **bundle["meta"]})
            else:
                rejected.append({**task_report, "reason": reason or "модель отклонена"})

    # Если обучается только одно направление, не удаляем уже обученные модели
    # другого направления из manifest. Для --domain all заменяем оба набора.
    preserved = []
    previous_manifest = args.models_dir / "manifest.json"
    if previous_manifest.is_file():
        try:
            old_records = json.loads(previous_manifest.read_text(encoding="utf-8")).get("models", [])
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
        except (OSError, ValueError, TypeError):
            preserved = []

    manifest = {
        "schema_version": 1,
        "application": "ПК Антидот-Прогноз",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "models": [*preserved, *accepted],
    }
    (args.models_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        "application": "ПК Антидот-Прогноз",
        "data_dir": str(args.data_dir),
        "models_dir": str(args.models_dir),
        "accepted_count": len(accepted),
        "preserved_count": len(preserved),
        "manifest_model_count": len(manifest["models"]),
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
        "note": "Модель сохраняется только после endpoint-specific scaffold CV и прохождения заданных порогов. Это не подтверждение экспериментальной активности.",
    }
    (args.models_dir / "training_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"accepted": len(accepted), "preserved": len(preserved), "rejected": len(rejected), "manifest_models": len(manifest["models"]), "models_dir": str(args.models_dir)}, ensure_ascii=False, indent=2))
    return 0 if accepted else 1


def DOMAINS_FILE(domain: str) -> str:
    return "antidote.csv" if domain == "antidote" else "growth_regulating.csv"


if __name__ == "__main__":
    sys.exit(main())
