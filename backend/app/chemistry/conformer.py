"""Построение 3D-конформера малой молекулы (RDKit ETKDGv3 + MMFF94)."""

from rdkit import Chem
from rdkit.Chem import AllChem

from app.chemistry import fingerprints as fp

MAX_HEAVY_ATOMS = 120


def generate_conformer(smiles: str, seed: int = 42) -> dict:
    mol = fp.mol_from_smiles(smiles)
    if mol is None:
        raise ValueError(
            "Некорректный SMILES. Не удалось распознать химическую структуру."
        )

    mol = fp.standardize(mol)
    if mol.GetNumHeavyAtoms() > MAX_HEAVY_ATOMS:
        raise ValueError(
            f"Молекула слишком большая для построения 3D "
            f"(более {MAX_HEAVY_ATOMS} тяжёлых атомов)."
        )

    warnings: list[str] = []

    try:
        centers = Chem.FindMolChiralCenters(
            mol, includeUnassigned=True
        )
        unassigned = [c for c in centers if c[1] == "?"]
        if unassigned:
            warnings.append(
                f"Не задана конфигурация стереоцентров ({len(unassigned)}): "
                "показан один из возможных стереоизомеров."
            )
    except Exception:
        pass

    mol_h = Chem.AddHs(mol)

    params = AllChem.ETKDGv3()
    params.randomSeed = seed
    status = AllChem.EmbedMolecule(mol_h, params)
    if status != 0:
        params.useRandomCoords = True
        status = AllChem.EmbedMolecule(mol_h, params)
    if status != 0:
        raise ValueError(
            "3D-конформация не была построена: для этой структуры RDKit не "
            "смог подобрать геометрию. Проверьте валентности и заряды."
        )

    method = "ETKDGv3"
    try:
        if AllChem.MMFFHasAllMoleculeParams(mol_h):
            AllChem.MMFFOptimizeMolecule(mol_h, maxIters=2000)
            method += " + MMFF94"
        else:
            AllChem.UFFOptimizeMolecule(mol_h, maxIters=2000)
            method += " + UFF"
            warnings.append(
                "Для молекулы нет параметров MMFF94, геометрия "
                "оптимизирована полем UFF (менее точным)."
            )
    except Exception:
        warnings.append(
            "Оптимизация геометрии не удалась: показан неоптимизированный "
            "конформер."
        )

    mol_h.SetProp("_Name", "ChemAnalyzer")
    molblock = Chem.MolToMolBlock(mol_h)

    return {
        "molblock": molblock,
        "sdf": molblock + "$$$$\n",
        "pdb": Chem.MolToPDBBlock(mol_h),
        "num_atoms": mol_h.GetNumAtoms(),
        "method": method,
        "seed": seed,
        "warnings": warnings,
        "note": (
            "Это один расчётный конформер в вакууме, а не экспериментальная "
            "структура и не обязательно биологически активная форма."
        ),
    }
