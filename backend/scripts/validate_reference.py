"""Проверка справочной библиотеки препаратов.

Запуск из папки backend (venv активирован):
    python scripts/validate_reference.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rdkit import Chem  # noqa: E402

from app.chemistry.reference_drugs import REFERENCE_DRUGS  # noqa: E402

bad = 0
names = set()
for name, smiles, activities in REFERENCE_DRUGS:
    if name in names:
        print(f"ДУБЛЬ: {name}")
        bad += 1
    names.add(name)
    if not activities:
        print(f"НЕТ АКТИВНОСТЕЙ: {name}")
        bad += 1
    if Chem.MolFromSmiles(smiles) is None:
        print(f"НЕВАЛИДНЫЙ SMILES: {name}: {smiles}")
        bad += 1

print(f"Всего записей: {len(REFERENCE_DRUGS)}, проблем: {bad}")
sys.exit(1 if bad else 0)
