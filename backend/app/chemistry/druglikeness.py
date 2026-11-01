"""Drug-likeness, оценка ADMET-свойств и структурные алерты (эвристики)."""

from functools import lru_cache

from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, Lipinski, QED, rdMolDescriptors
from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams

from app.chemistry import boiled_egg
from app.chemistry import fingerprints as fp

MAX_ALERTS = 12


@lru_cache(maxsize=2)
def _catalog(kind: str) -> FilterCatalog:
    params = FilterCatalogParams()
    catalogs = FilterCatalogParams.FilterCatalogs
    if kind == "pains":
        params.AddCatalog(catalogs.PAINS)
    else:
        params.AddCatalog(catalogs.BRENK)
    return FilterCatalog(params)


def _alerts(mol: Chem.Mol, kind: str) -> list[str]:
    seen: list[str] = []
    for entry in _catalog(kind).GetMatches(mol):
        description = entry.GetDescription()
        if description not in seen:
            seen.append(description)
    return seen[:MAX_ALERTS]


def list_alerts(mol: Chem.Mol, kind: str) -> list[str]:
    """Структурные алерты: kind = "pains" или "brenk"."""
    return _alerts(mol, kind)


def _rule(name: str, checks: list[tuple[str, bool]]) -> dict:
    violations = [text for text, ok in checks if not ok]
    return {
        "name": name,
        "passed": not violations,
        "violations": violations,
    }


def _qed_label(value: float) -> str:
    if value >= 0.67:
        return "высокая"
    if value >= 0.34:
        return "средняя"
    return "низкая"


def assess_druglikeness(smiles: str) -> dict:
    smiles = smiles.strip()
    mol = Chem.MolFromSmiles(smiles) if smiles else None

    if mol is None or mol.GetNumAtoms() == 0:
        raise ValueError(
            "Некорректный SMILES. Не удалось распознать химическую структуру."
        )

    # Единая стандартизация для всех вкладок: наибольший фрагмент + нейтрализация.
    mol = fp.standardize(mol)

    mw = Descriptors.MolWt(mol)
    logp = Crippen.MolLogP(mol)
    mr = Crippen.MolMR(mol)
    tpsa = rdMolDescriptors.CalcTPSA(mol)
    hbd = Lipinski.NumHDonors(mol)
    hba = Lipinski.NumHAcceptors(mol)
    rotb = Lipinski.NumRotatableBonds(mol)
    total_atoms = Chem.AddHs(mol).GetNumAtoms()

    rules = [
        _rule(
            "Липински",
            [
                (f"масса {mw:.1f} > 500", mw <= 500),
                (f"LogP {logp:.2f} > 5", logp <= 5),
                (f"доноры H-связи {hbd} > 5", hbd <= 5),
                (f"акцепторы H-связи {hba} > 10", hba <= 10),
            ],
        ),
        _rule(
            "Вебер",
            [
                (f"вращаемых связей {rotb} > 10", rotb <= 10),
                (f"TPSA {tpsa:.1f} > 140", tpsa <= 140),
            ],
        ),
        _rule(
            "Иган",
            [
                (f"TPSA {tpsa:.1f} > 131.6", tpsa <= 131.6),
                (f"LogP {logp:.2f} > 5.88", logp <= 5.88),
            ],
        ),
        _rule(
            "Гхош",
            [
                (f"масса {mw:.1f} вне 160–480", 160 <= mw <= 480),
                (f"LogP {logp:.2f} вне −0.4…5.6", -0.4 <= logp <= 5.6),
                (f"молярная рефракция {mr:.1f} вне 40–130", 40 <= mr <= 130),
                (f"число атомов {total_atoms} вне 20–70", 20 <= total_atoms <= 70),
            ],
        ),
    ]

    qed_value = float(QED.qed(mol))

    # ЖКТ и ГЭБ — по модели BOILED-Egg (TPSA с учётом S и P), как во вкладке ADME.
    egg = boiled_egg.classify(rdMolDescriptors.CalcTPSA(mol, includeSandP=True), logp)
    gi_high = egg["gi_absorption"]
    bbb_likely = egg["bbb_permeant"]

    return {
        "qed": round(qed_value, 3),
        "qed_label": _qed_label(qed_value),
        "rules": rules,
        "gi_absorption": "высокая" if gi_high else "низкая",
        "bbb_permeant": "вероятно" if bbb_likely else "маловероятно",
        "pains_alerts": _alerts(mol, "pains"),
        "brenk_alerts": _alerts(mol, "brenk"),
        "disclaimer": (
            "Правила и ADMET-оценки — упрощённые эвристики по "
            "физико-химическим дескрипторам, а не результат моделирования."
        ),
    }


def structure_keys(smiles: str) -> dict:
    """Канонический SMILES и InChIKey (для поиска в ChEMBL)."""
    smiles = smiles.strip()
    mol = Chem.MolFromSmiles(smiles) if smiles else None

    if mol is None or mol.GetNumAtoms() == 0:
        raise ValueError(
            "Некорректный SMILES. Не удалось распознать химическую структуру."
        )

    # Единая стандартизация для всех вкладок: наибольший фрагмент + нейтрализация.
    mol = fp.standardize(mol)

    try:
        inchikey = Chem.MolToInchiKey(mol) or None
    except Exception:
        inchikey = None

    return {"smiles": Chem.MolToSmiles(mol), "inchikey": inchikey}
