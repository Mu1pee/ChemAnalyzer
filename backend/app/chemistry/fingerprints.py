"""Единая featurization для обучения и предсказания.

Обучение (training/) и предсказание (app/) обязаны использовать ОДНИ И ТЕ ЖЕ
функции, иначе модель получит признаки не того вида. Поэтому они живут здесь.
"""

import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator
from rdkit.Chem.MolStandardize import rdMolStandardize
from rdkit.Chem.Scaffolds import MurckoScaffold

N_BITS = 2048
RADIUS = 2

_generator = rdFingerprintGenerator.GetMorganGenerator(
    radius=RADIUS, fpSize=N_BITS
)


def mol_from_smiles(smiles: str) -> Chem.Mol | None:
    smiles = (smiles or "").strip()
    if not smiles:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None or mol.GetNumAtoms() == 0:
        return None
    return mol


def standardize(mol: Chem.Mol) -> Chem.Mol:
    """Наибольший фрагмент (убираем соли) + нейтрализация зарядов."""
    try:
        mol = rdMolStandardize.LargestFragmentChooser().choose(mol)
        mol = rdMolStandardize.Uncharger().uncharge(mol)
    except Exception:
        pass
    return mol


def fingerprint_array(mol: Chem.Mol) -> np.ndarray:
    fp = _generator.GetFingerprint(mol)
    array = np.zeros((N_BITS,), dtype=np.uint8)
    DataStructs.ConvertToNumpyArray(fp, array)
    return array


def scaffold_smiles(mol: Chem.Mol) -> str:
    """Скаффолд Мердока; для ациклических молекул — сам SMILES."""
    try:
        scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol)
    except Exception:
        scaffold = ""
    return scaffold or Chem.MolToSmiles(mol)
