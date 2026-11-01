"""Обучение QSAR-моделей по скачанным данным ChEMBL.

Запуск из папки backend:
    python -m training.train
    python -m training.train --targets CHEMBL230 --active 6.5

Для каждой мишени:
  1. стандартизация молекул, усреднение повторных измерений (медиана);
  2. метка «активен», если pChEMBL >= порога;
  3. кросс-валидация с разбиением по скаффолдам (честнее случайной);
  4. Y-рандомизация (проверка на утечку данных);
  5. «ворота качества»: слабые модели НЕ попадают в приложение;
  6. финальная калиброванная модель + обучающая выборка для области
     применимости -> models/<CHEMBL_ID>.joblib.
"""

import argparse
import csv
import json
import statistics
import sys
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import sklearn
from rdkit import Chem

from app.chemistry import fingerprints as fp
from app.chemistry import qsar_core as core
from training import config


def load_dataset(csv_path):
    """Читает CSV -> (X, pchembl, scaffold_groups) по уникальным молекулам."""
    values: dict[str, list[float]] = {}
    mols: dict[str, Chem.Mol] = {}

    with csv_path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            mol = fp.mol_from_smiles(row["smiles"])
            if mol is None:
                continue
            mol = fp.standardize(mol)
            key = Chem.MolToSmiles(mol)
            if not key:
                continue
            mols.setdefault(key, mol)
            values.setdefault(key, []).append(float(row["pchembl"]))

    keys = sorted(values)
    pchembl = np.array([statistics.median(values[k]) for k in keys])
    X = np.stack([fp.fingerprint_array(mols[k]) for k in keys]).astype(np.uint8)

    scaffold_ids: dict[str, int] = {}
    groups = np.array(
        [scaffold_ids.setdefault(fp.scaffold_smiles(mols[k]), len(scaffold_ids))
         for k in keys]
    )
    return X, pchembl, groups


def train_target(target_id, label, active_threshold, args):
    csv_path = config.DATA_DIR / f"{target_id}.csv"
    if not csv_path.exists():
        return None, f"нет файла данных {csv_path.name} (сначала fetch_data)"

    meta_path = config.DATA_DIR / f"{target_id}.meta.json"
    chembl_name = label
    if meta_path.exists():
        chembl_name = json.loads(meta_path.read_text(encoding="utf-8")).get(
            "chembl_name", label
        )

    X, pchembl, groups = load_dataset(csv_path)
    y = (pchembl >= active_threshold).astype(int)
    n_active, n_inactive = int(y.sum()), int((1 - y).sum())
    print(f"    молекул: {len(y)}  (активных {n_active}, неактивных {n_inactive}), "
          f"скаффолдов: {len(set(groups))}")

    if min(n_active, n_inactive) < config.MIN_PER_CLASS:
        reasons = core.quality_gate(None, n_active, n_inactive, None)
        return None, "; ".join(reasons)

    n_splits = int(min(5, n_active, n_inactive))
    metrics = core.cross_validate(X, y, groups, n_splits=n_splits, seed=args.seed)
    y_rand = core.y_randomization_auc(X, y, groups, seed=args.seed)
    print(f"    CV по скаффолдам: {metrics}")
    print(f"    Y-рандомизация AUC: {y_rand}")

    reasons = core.quality_gate(
        metrics, n_active, n_inactive, y_rand,
        min_auc=args.min_auc, min_mcc=config.MIN_MCC,
        min_per_class=config.MIN_PER_CLASS,
    )
    if reasons:
        return None, "; ".join(reasons)

    model = core.train_final(X, y, seed=args.seed)
    packed = core.pack_bits(X)
    bundle = {
        "model": model,
        "train_packed": packed,
        "train_popcount": core.popcounts(packed),
        "meta": {
            "target_id": target_id,
            "label": label,
            "chembl_name": chembl_name,
            "active_pchembl": active_threshold,
            "n_train": int(len(y)),
            "n_active": n_active,
            "n_inactive": n_inactive,
            "metrics": metrics,
            "y_random_auc": y_rand,
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sklearn_version": sklearn.__version__,
            "n_bits": fp.N_BITS,
            "radius": fp.RADIUS,
        },
    }
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, config.MODELS_DIR / f"{target_id}.joblib", compress=3)
    return bundle["meta"], None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", help="ID через запятую (по умолчанию все)")
    parser.add_argument("--active", type=float, default=config.ACTIVE_PCHEMBL,
                        help="порог pChEMBL для класса «активен»")
    parser.add_argument("--min-auc", type=float, default=config.MIN_AUC)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    wanted = set(args.targets.split(",")) if args.targets else None
    targets = [t for t in config.TARGETS if wanted is None or t[0] in wanted]

    accepted, rejected = [], []
    started = time.time()

    for index, (target_id, label, _) in enumerate(targets, 1):
        print(f"[{index}/{len(targets)}] {target_id} — {label}")
        try:
            meta, reason = train_target(target_id, label, args.active, args)
        except Exception as error:  # одна мишень не должна ронять весь запуск
            meta, reason = None, f"ошибка: {error}"

        if meta:
            accepted.append(meta)
            print(f"    ПРИНЯТА  AUC={meta['metrics']['roc_auc']}  "
                  f"MCC={meta['metrics']['mcc']}")
        else:
            rejected.append({"target_id": target_id, "label": label, "reason": reason})
            print(f"    ОТКЛОНЕНА: {reason}")

    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    (config.MODELS_DIR / "manifest.json").write_text(
        json.dumps({"models": accepted}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (config.MODELS_DIR / "training_report.json").write_text(
        json.dumps({"accepted": accepted, "rejected": rejected,
                    "active_pchembl": args.active}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\nИтог: принято {len(accepted)}, отклонено {len(rejected)} "
          f"({(time.time() - started) / 60:.1f} мин)")
    print(f"Манифест: {config.MODELS_DIR / 'manifest.json'}")
    return 0 if accepted else 1


if __name__ == "__main__":
    sys.exit(main())
