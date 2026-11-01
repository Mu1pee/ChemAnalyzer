"""Сквозная самопроверка backend на настоящем стеке (RDKit + FastAPI).

Запуск из папки backend, venv активирован:
    python scripts/selftest.py

Что проверяется:
  - три эталонные молекулы (этанол, бензол, аспирин): формула, масса, LogP, TPSA, HBD, HBA;
  - некорректный SMILES и пустой ввод;
  - PubChem и ChEMBL недоступны -> локальный анализ всё равно работает;
  - QSAR-модели отсутствуют -> честное сообщение «QSAR-модель не обучена»;
  - 3D: успех и понятные ошибки; SVG-изображение; health;
  - ADME / BOILED-Egg: циклогептан со скриншота SwissADME (ЖКТ низкое, ГЭБ да, нарушения Ghose/Muegge).
Интернет не нужен: сетевые вызовы подменяются.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Пустая папка моделей: гарантированно «модель не обучена».
os.environ["CHEMANALYZER_MODELS_DIR"] = tempfile.mkdtemp(prefix="chemanalyzer-nomodels-")
os.environ.pop("CHEMANALYZER_DESKTOP", None)

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api import chembl, pubchem  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    mark = "OK  " if condition else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def close(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


class OfflineClient:
    """Подмена httpx.AsyncClient: любая попытка обратиться к сети — сбой."""

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, *args, **kwargs):
        raise httpx.ConnectError("нет сети (самопроверка)")

    async def post(self, *args, **kwargs):
        raise httpx.ConnectError("нет сети (самопроверка)")


pubchem.httpx.AsyncClient = OfflineClient
chembl.httpx.AsyncClient = OfflineClient

# ---------------------------------------------------------------- эталоны

REFERENCE = [
    # название, SMILES, формула, масса, допуск массы, HBD, TPSA, допуск TPSA, диапазон LogP, HBA или None
    ("Этанол", "CCO", "C2H6O", 46.069, 0.01, 1, 20.23, 0.05, (-0.5, 0.5), 1),
    ("Бензол", "c1ccccc1", "C6H6", 78.114, 0.01, 0, 0.0, 0.01, (1.3, 2.0), 0),
    ("Аспирин", "CC(=O)Oc1ccccc1C(=O)O", "C9H8O4", 180.159, 0.01, 1, 63.6, 0.1, (1.0, 1.7), None),
]

print("\n== Три обязательные молекулы ==")
rows = []
for name, smiles, formula, mw, mw_tol, hbd, tpsa, tpsa_tol, logp_range, hba in REFERENCE:
    print(f"\n{name}  {smiles}")
    r = client.post("/api/molecules/analyze", json={"smiles": smiles})
    check("HTTP 200", r.status_code == 200, str(r.status_code))
    if r.status_code != 200:
        continue
    d = r.json()
    rows.append((name, d))
    check(f"формула {formula}", d["formula"] == formula, d["formula"])
    check(f"масса ≈ {mw}", close(d["molecular_weight"], mw, mw_tol), str(d["molecular_weight"]))
    check(f"LogP в диапазоне {logp_range}", logp_range[0] <= d["logp"] <= logp_range[1], str(d["logp"]))
    check(f"TPSA ≈ {tpsa}", close(d["tpsa"], tpsa, tpsa_tol), str(d["tpsa"]))
    check(f"HBD = {hbd}", d["hbd"] == hbd, str(d["hbd"]))
    if hba is not None:
        check(f"HBA = {hba}", d["hba"] == hba, str(d["hba"]))
    check("Липински: нарушений нет", d["lipinski_violations"] == 0 and d["lipinski_passes"])
    check("канонический SMILES непустой", bool(d["canonical_smiles"]))
    check("в ответе нет блока identification (PubChem отделён)", "identification" not in d)

print("\n== Сводная таблица (значения RDKit) ==")
print(f"{'вещество':<10}{'SMILES':<26}{'формула':<10}{'MW':>9}{'LogP':>8}{'TPSA':>8}{'HBD':>5}{'HBA':>5}")
for name, d in rows:
    print(f"{name:<10}{d['canonical_smiles']:<26}{d['formula']:<10}{d['molecular_weight']:>9}"
          f"{d['logp']:>8}{d['tpsa']:>8}{d['hbd']:>5}{d['hba']:>5}")

# ---------------------------------------------------------------- ошибки ввода

print("\n== Некорректный ввод ==")
r = client.post("/api/molecules/analyze", json={"smiles": "C1CC("})
check("битый SMILES -> 400", r.status_code == 400, str(r.status_code))
check("сообщение понятное, без «500»", "распознать химическую структуру" in r.json().get("detail", ""))
r = client.post("/api/molecules/analyze", json={"smiles": "   "})
check("пробелы вместо SMILES -> 400", r.status_code == 400, str(r.status_code))
r = client.post("/api/molecules/analyze", json={"smiles": ""})
check("пустая строка -> 422 (проверка схемы)", r.status_code == 422, str(r.status_code))

# ---------------------------------------------------------------- внешние сервисы недоступны

print("\n== PubChem / ChEMBL недоступны ==")
r = client.post("/api/molecules/analyze", json={"smiles": "CC(=O)Oc1ccccc1C(=O)O"})
check("локальный анализ работает без интернета", r.status_code == 200 and r.json()["formula"] == "C9H8O4")

r = client.post("/api/molecules/identify", json={"smiles": "CC(=O)Oc1ccccc1C(=O)O"})
d = r.json()
check("identify: HTTP 200", r.status_code == 200)
check("статус unavailable (а не not_found)", d["status"] == "unavailable", d["status"])
check("название НЕ присвоено", d["found"] is False and d.get("title") is None)
check("текст: PubChem недоступен — локальный анализ выполнен.",
      d["message"] == "PubChem недоступен — локальный анализ выполнен.", str(d["message"]))

r = client.post("/api/molecules/chembl", json={"smiles": "CC(=O)Oc1ccccc1C(=O)O"})
d = r.json()
check("chembl: HTTP 200, available=False", r.status_code == 200 and d["available"] is False)
check("chembl: данные не выдуманы", not d.get("targets") and not d.get("mechanisms"))
check("chembl: есть понятное сообщение", "недоступен" in (d.get("message") or ""), str(d.get("message")))

# ---------------------------------------------------------------- QSAR

print("\n== QSAR без обученных моделей ==")
r = client.post("/api/molecules/activity", json={"smiles": "CC(=O)Oc1ccccc1C(=O)O"})
d = r.json()
check("activity: HTTP 200", r.status_code == 200, str(r.status_code))
q = d["qsar"]
check("qsar.status = not_trained", q["status"] == "not_trained", q["status"])
check("qsar.available = False, предсказаний нет", q["available"] is False and q["predictions"] == [])
check("текст «QSAR-модель не обучена»", "QSAR-модель не обучена" in (q["message"] or ""))
check("честная оговорка про similarity", "не экспериментальное подтверждение" in (q["message"] or ""))
check("similarity-оценка при этом доступна", len(d["activities"]) > 0)
check("drug-likeness посчитан (QED)", 0 <= d["druglikeness"]["qed"] <= 1)

# ---------------------------------------------------------------- 3D и изображение

print("\n== 3D и изображение ==")
r = client.post("/api/molecules/conformer", json={"smiles": "CC(=O)Oc1ccccc1C(=O)O"})
d = r.json()
check("3D аспирина: HTTP 200", r.status_code == 200, str(r.status_code))
if r.status_code == 200:
    check("21 атом (с водородами)", d["num_atoms"] == 21, str(d["num_atoms"]))
    check("molblock и SDF непустые", "V2000" in d["molblock"] and d["sdf"].endswith("$$$$\n"))
    r2 = client.post("/api/molecules/conformer", json={"smiles": "CC(=O)Oc1ccccc1C(=O)O", "seed": 7})
    check("перестроение с другим seed работает", r2.status_code == 200 and r2.json()["seed"] == 7)

r = client.post("/api/molecules/conformer", json={"smiles": "C" * 130})
check("слишком большая молекула -> 400 с понятным текстом",
      r.status_code == 400 and "слишком большая" in r.json()["detail"], r.text[:80])
r = client.post("/api/molecules/conformer", json={"smiles": "C1CC("})
check("3D для битого SMILES -> 400", r.status_code == 400)

r = client.post("/api/molecules/depict", json={"smiles": "CCO"})
check("SVG-изображение структуры", r.status_code == 200 and "<svg" in r.text)

# ---------------------------------------------------------------- ADME

print("\n== ADME / BOILED-Egg (эталон: циклогептан со скриншота SwissADME) ==")
r = client.post("/api/molecules/adme", json={"smiles": "C1CCCCCC1"})
check("ADME циклогептана: HTTP 200", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
if r.status_code == 200:
    d = r.json()
    pc = d["physchem"]
    check("формула C7H14", pc["formula"] == "C7H14", pc["formula"])
    check("масса ≈ 98.19", close(pc["molecular_weight"], 98.19, 0.02), str(pc["molecular_weight"]))
    check("тяжёлых атомов 7, ароматических 0", pc["heavy_atoms"] == 7 and pc["aromatic_heavy_atoms"] == 0)
    check("Fsp3 = 1.0, вращаемых связей 0", pc["fsp3"] == 1.0 and pc["rotatable_bonds"] == 0)
    check("HBA = 0, HBD = 0, TPSA = 0", pc["hba"] == 0 and pc["hbd"] == 0 and pc["tpsa"] == 0.0)
    check("WLOGP ≈ 2.73", close(pc["wlogp"], 2.73, 0.05), str(pc["wlogp"]))
    check("молярная рефракция в разумных пределах (SwissADME: 33.65)", 30 <= pc["molar_refractivity"] <= 36,
          str(pc["molar_refractivity"]))

    egg = d["boiled_egg"]
    check("BOILED-Egg: ЖКТ — низкое (как на скриншоте)", egg["gi_absorption"] is False)
    check("BOILED-Egg: ГЭБ — да (как на скриншоте)", egg["bbb_permeant"] is True)
    check("передаются параметры эллипсов", {"cx", "cy", "a", "b", "angle"} <= set(egg["white"]) and {"cx", "cy", "a", "b", "angle"} <= set(egg["yolk"]))

    rules = {x["name"]: x for x in d["druglikeness"]}
    check("Липински: проходит", rules["Липински"]["passed"])
    check("Гхош: нет, нарушения MW<160 и MR<40",
          not rules["Гхош"]["passed"] and rules["Гхош"]["violations"] == ["MW < 160", "MR < 40"],
          str(rules["Гхош"]["violations"]))
    check("Вебер и Иган: проходят", rules["Вебер"]["passed"] and rules["Иган"]["passed"])
    check("Мюгге: нет, нарушения MW<200 и гетероатомов<2",
          not rules["Мюгге"]["passed"] and rules["Мюгге"]["violations"] == ["MW < 200", "гетероатомов < 2"],
          str(rules["Мюгге"]["violations"]))
    check("PAINS и Brenk: 0 предупреждений", d["medchem"]["pains"] == [] and d["medchem"]["brenk"] == [])
    check("ESOL log S ≈ −2.17 (SwissADME: −2.97 при XLOGP3 = 4.0)", close(d["solubility"]["esol_logs"], -2.17, 0.1),
          str(d["solubility"]["esol_logs"]))
    check("радар: 6 осей LIPO, SIZE, POLAR, INSOLU, INSATU, FLEX",
          [a["key"] for a in d["radar"]] == ["LIPO", "SIZE", "POLAR", "INSOLU", "INSATU", "FLEX"])
    axes = {a["key"]: a for a in d["radar"]}
    check("радар: SIZE и POLAR вне зоны, INSATU и FLEX в зоне",
          not axes["SIZE"]["in_range"] and not axes["POLAR"]["in_range"]
          and axes["INSATU"]["in_range"] and axes["FLEX"]["in_range"])
    check("P-gp и CYP честно помечены как не рассчитываемые", len(d["not_computed"]) == 2)
    print(f"      (справочно) синтетическая доступность: {d['medchem']['synthetic_accessibility']} "
          "[SwissADME: 1.43; None — модуль SA_Score недоступен в этой сборке RDKit]")

r = client.post("/api/molecules/adme", json={"smiles": "C1CC("})
check("ADME для битого SMILES -> 400", r.status_code == 400)
r = client.post("/api/molecules/activity", json={"smiles": "CC(=O)Oc1ccccc1C(=O)O"})
dl = r.json()["druglikeness"]
a = client.post("/api/molecules/adme", json={"smiles": "CC(=O)Oc1ccccc1C(=O)O"}).json()
check("вкладки Drug-likeness и ADME не противоречат (ЖКТ/ГЭБ из одной модели)",
      (dl["gi_absorption"] == "высокая") == a["boiled_egg"]["gi_absorption"]
      and (dl["bbb_permeant"] == "вероятно") == a["boiled_egg"]["bbb_permeant"])

# ---------------------------------------------------------------- служебное

print("\n== Служебные эндпоинты ==")
r = client.get("/health")
check("/health: application=ChemAnalyzer", r.status_code == 200 and r.json().get("application") == "ChemAnalyzer")
r = client.get("/api/app/info")
check("/api/app/info: версия есть, секретов нет",
      r.status_code == 200 and "version" in r.json() and "key" not in r.text.lower())

print()
if failures:
    print(f"ПРОВАЛЕНО проверок: {len(failures)}")
    for name in failures:
        print("  -", name)
    sys.exit(1)
print("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")
