"""ADME-профиль в духе SwissADME: BOILED-Egg, радар биодоступности и ключевые свойства.

Что считается здесь (RDKit): физико-химические дескрипторы, WLOGP (Crippen),
ESOL, Log Kp, правила Lipinski/Ghose/Veber/Egan/Muegge, lead-likeness,
PAINS/Brenk, BOILED-Egg. Что НЕ считается: субстрат P-gp и ингибиторы CYP —
это модели SwissADME на закрытых данных; значения не выдумываются.

Отличия от SwissADME (явно сообщаются пользователю): вместо XLOGP3/iLOGP/
MLOGP используется WLOGP (Crippen), поэтому ESOL, Log Kp, Lipinski,
lead-likeness и радар могут отличаться от значений SwissADME.
"""

import os
import sys

from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors

from app.chemistry import adme_calc as calc
from app.chemistry import boiled_egg
from app.chemistry import fingerprints as fp
from app.chemistry.druglikeness import list_alerts

NOT_COMPUTED = [
    "Субстрат P-gp",
    "Ингибиторы CYP1A2, CYP2C19, CYP2C9, CYP2D6, CYP3A4",
]

NOTES = [
    "Липофильность — WLOGP (метод Крипена). SwissADME дополнительно использует "
    "iLOGP, XLOGP3, MLOGP и SILICOS-IT, поэтому ESOL, Log Kp, радар, "
    "Lipinski и lead-likeness могут отличаться от значений SwissADME.",
    "TPSA здесь учитывает атомы S и P (как в оригинальной модели BOILED-Egg); "
    "для молекул с S или P значение отличается от вкладки «Свойства».",
    "Молярная рефракция считается по Крипену (RDKit) и может немного "
    "отличаться от значения SwissADME (например, у циклогептана ≈32 против 33.65).",
    "Субстрат P-gp и ингибиторы CYP не рассчитываются: для них нужны обученные "
    "модели на экспериментальных данных.",
    "BOILED-Egg предсказывает пассивную диффузию; активный транспорт и "
    "метаболизм он не учитывает.",
]


def _synthetic_accessibility(mol: Chem.Mol) -> float | None:
    """Оценка синтетической доступности Эртла (1 — легко, 10 — очень сложно).

    Модуль sascorer входит в Contrib RDKit и есть не во всех сборках —
    тогда значение просто не показывается.
    """
    try:
        from rdkit.Chem import RDConfig

        path = os.path.join(RDConfig.RDContribDir, "SA_Score")
        if path not in sys.path:
            sys.path.append(path)
        import sascorer  # type: ignore

        return round(float(sascorer.calculateScore(mol)), 2)
    except Exception:
        return None


def compute_adme(smiles: str) -> dict:
    mol = fp.mol_from_smiles(smiles)
    if mol is None:
        raise ValueError(
            "Некорректный SMILES. Не удалось распознать химическую структуру."
        )
    mol = fp.standardize(mol)

    # ---- дескрипторы
    mw = Descriptors.MolWt(mol)
    heavy = mol.GetNumHeavyAtoms()
    aromatic_heavy = sum(1 for a in mol.GetAtoms() if a.GetIsAromatic())
    fsp3 = rdMolDescriptors.CalcFractionCSP3(mol)
    rotb = Lipinski.NumRotatableBonds(mol)
    hba = Lipinski.NumHAcceptors(mol)
    hbd = Lipinski.NumHDonors(mol)
    mr = Crippen.MolMR(mol)
    wlogp = Crippen.MolLogP(mol)
    tpsa = rdMolDescriptors.CalcTPSA(mol, includeSandP=True)
    rings = rdMolDescriptors.CalcNumRings(mol)
    carbons = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() == 6)
    heteroatoms = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() not in (1, 6))
    total_atoms = Chem.AddHs(mol).GetNumAtoms()

    # ---- растворимость и кожа
    ap = aromatic_heavy / heavy if heavy else 0.0
    logs = calc.esol_logs(wlogp, mw, rotb, ap)

    # ---- BOILED-Egg
    egg = boiled_egg.classify(tpsa, wlogp)

    return {
        "boiled_egg": {
            "tpsa": round(tpsa, 2),
            "wlogp": round(wlogp, 2),
            "gi_absorption": egg["gi_absorption"],
            "bbb_permeant": egg["bbb_permeant"],
            "white": boiled_egg.WHITE,
            "yolk": boiled_egg.YOLK,
            "source": boiled_egg.SOURCE,
        },
        "radar": calc.radar(wlogp, mw, tpsa, logs, fsp3, rotb),
        "physchem": {
            "formula": rdMolDescriptors.CalcMolFormula(mol),
            "molecular_weight": round(mw, 2),
            "heavy_atoms": heavy,
            "aromatic_heavy_atoms": aromatic_heavy,
            "fsp3": round(fsp3, 2),
            "rotatable_bonds": rotb,
            "hba": hba,
            "hbd": hbd,
            "molar_refractivity": round(mr, 2),
            "tpsa": round(tpsa, 2),
            "wlogp": round(wlogp, 2),
        },
        "solubility": calc.solubility(logs, mw),
        "pharmacokinetics": {
            "gi_absorption": "высокое" if egg["gi_absorption"] else "низкое",
            "bbb_permeant": "да" if egg["bbb_permeant"] else "нет",
            "log_kp": round(calc.log_kp(wlogp, mw), 2),
        },
        "druglikeness": [
            calc.lipinski(mw, wlogp, hbd, hba),
            calc.ghose(mw, wlogp, mr, total_atoms),
            calc.veber(rotb, tpsa),
            calc.egan(wlogp, tpsa),
            calc.muegge(mw, wlogp, tpsa, rings, carbons, heteroatoms, rotb, hba, hbd),
        ],
        "medchem": {
            "pains": list_alerts(mol, "pains"),
            "brenk": list_alerts(mol, "brenk"),
            "lead_likeness": calc.lead_likeness(mw, wlogp, rotb),
            "synthetic_accessibility": _synthetic_accessibility(mol),
        },
        "not_computed": NOT_COMPUTED,
        "notes": NOTES,
    }
