"""Загрузка данных об активности из ChEMBL.

Запуск из папки backend:
    python -m training.fetch_data                      # все мишени
    python -m training.fetch_data --targets CHEMBL230,CHEMBL203
    python -m training.fetch_data --force              # перекачать заново

Данные кладутся в training/data/<CHEMBL_ID>.csv. Уже скачанное пропускается,
поэтому прерванную загрузку можно просто запустить снова.
"""

import argparse
import csv
import json
import sys
import time

import httpx

from training.config import (
    ACTIVITY_TYPES,
    DATA_DIR,
    MAX_RECORDS_PER_TARGET,
    TARGETS,
)

BASE = "https://www.ebi.ac.uk/chembl/api/data"
HOST = "https://www.ebi.ac.uk"
PAGE_SIZE = 1000
PAUSE = 0.4  # пауза между запросами, не нагружаем публичный сервис
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ChemAnalyzerModern-training/2.2 (+local use)",
}
FIELDS = ["molecule_chembl_id", "smiles", "pchembl", "standard_type"]


def parse_activity_page(payload: dict) -> list[dict]:
    """Достаёт из страницы ответа ChEMBL нужные поля (чистая функция)."""
    rows = []
    for item in (payload or {}).get("activities") or []:
        smiles = item.get("canonical_smiles")
        pchembl = item.get("pchembl_value")
        if not smiles or pchembl in (None, ""):
            continue
        try:
            float(pchembl)
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                "molecule_chembl_id": item.get("molecule_chembl_id"),
                "smiles": smiles,
                "pchembl": pchembl,
                "standard_type": item.get("standard_type"),
            }
        )
    return rows


def next_page_url(payload: dict) -> str | None:
    nxt = ((payload or {}).get("page_meta") or {}).get("next")
    if not nxt:
        return None
    return nxt if nxt.startswith("http") else f"{HOST}{nxt}"


def _get(client: httpx.Client, url: str, params: dict | None = None):
    """GET с повторами при 429/5xx и сетевых сбоях."""
    for attempt in range(5):
        try:
            response = client.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 * (attempt + 1))
                continue
            return None
        except (httpx.HTTPError, ValueError):
            time.sleep(2 * (attempt + 1))
    return None


def resolve_target_name(client: httpx.Client, target_id: str) -> str | None:
    payload = _get(client, f"{BASE}/target/{target_id}.json")
    return (payload or {}).get("pref_name")


def fetch_target(
    client: httpx.Client, target_id: str, max_records: int
) -> list[dict]:
    rows: list[dict] = []
    url: str | None = f"{BASE}/activity.json"
    params: dict | None = {
        "target_chembl_id": target_id,
        "standard_type__in": ACTIVITY_TYPES,
        "standard_relation": "=",
        "pchembl_value__gte": 1,
        "limit": PAGE_SIZE,
    }

    while url and len(rows) < max_records:
        payload = _get(client, url, params)
        if payload is None:
            print("    ! запрос не удался, сохраняю то, что успели скачать")
            break
        rows.extend(parse_activity_page(payload))
        url, params = next_page_url(payload), None
        print(f"    скачано записей: {len(rows)}", end="\r")
        time.sleep(PAUSE)

    print()
    return rows[:max_records]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", help="ID через запятую (по умолчанию все)")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-records", type=int, default=MAX_RECORDS_PER_TARGET)
    parser.add_argument(
        "--accept-mismatch",
        action="store_true",
        help="не пропускать мишени, у которых название не совпало с ожидаемым",
    )
    args = parser.parse_args()

    wanted = set(args.targets.split(",")) if args.targets else None
    targets = [t for t in TARGETS if wanted is None or t[0] in wanted]
    if not targets:
        print("Нет подходящих мишеней.")
        return 1

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    done = skipped = failed = 0

    with httpx.Client(timeout=httpx.Timeout(40.0, connect=10.0), headers=HEADERS) as client:
        for index, (target_id, label, expected) in enumerate(targets, 1):
            csv_path = DATA_DIR / f"{target_id}.csv"
            print(f"[{index}/{len(targets)}] {target_id} — {label}")

            if csv_path.exists() and not args.force:
                print("    уже скачано, пропускаю (--force чтобы перекачать)")
                skipped += 1
                continue

            actual = resolve_target_name(client, target_id)
            if actual is None:
                print("    ! не удалось получить мишень (нет доступа к ChEMBL?)")
                failed += 1
                continue
            print(f"    название в ChEMBL: {actual}")

            if expected not in actual.lower() and not args.accept_mismatch:
                print(
                    f"    ! название не содержит «{expected}» — пропускаю. "
                    "Проверьте ID в training/config.py "
                    "или запустите с --accept-mismatch"
                )
                failed += 1
                continue

            rows = fetch_target(client, target_id, args.max_records)
            if not rows:
                print("    ! данных нет")
                failed += 1
                continue

            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)

            meta = {"target_id": target_id, "label": label, "chembl_name": actual,
                    "records": len(rows)}
            (DATA_DIR / f"{target_id}.meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"    сохранено {len(rows)} записей")
            done += 1

    print(f"\nГотово: скачано {done}, пропущено {skipped}, ошибок {failed}")
    return 0 if (done or skipped) else 1


if __name__ == "__main__":
    sys.exit(main())
