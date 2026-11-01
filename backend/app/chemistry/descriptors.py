from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors


def analyze_molecule(smiles: str) -> dict:
    smiles = smiles.strip()
    molecule = Chem.MolFromSmiles(smiles) if smiles else None

    # MolFromSmiles("") возвращает пустую молекулу, а не None.
    if molecule is None or molecule.GetNumAtoms() == 0:
        raise ValueError(
            "Некорректный SMILES. Не удалось распознать химическую структуру."
        )

    canonical_smiles = Chem.MolToSmiles(molecule)
    formula = rdMolDescriptors.CalcMolFormula(molecule)
    molecular_weight = Descriptors.MolWt(molecule)
    logp = Crippen.MolLogP(molecule)
    tpsa = rdMolDescriptors.CalcTPSA(molecule)
    hbd = Lipinski.NumHDonors(molecule)
    hba = Lipinski.NumHAcceptors(molecule)
    rotatable_bonds = Lipinski.NumRotatableBonds(molecule)
    rings = rdMolDescriptors.CalcNumRings(molecule)
    heavy_atoms = molecule.GetNumHeavyAtoms()

    aromatic_atoms = sum(
        1 for atom in molecule.GetAtoms() if atom.GetIsAromatic()
    )

    fragments = len(Chem.GetMolFrags(molecule))
    atom_count = molecule.GetNumAtoms()
    bond_count = molecule.GetNumBonds()

    # Классическое правило пяти Липинского:
    # MW <= 500, LogP <= 5, HBD <= 5, HBA <= 10.
    violations = sum(
        [
            molecular_weight > 500,
            logp > 5,
            hbd > 5,
            hba > 10,
        ]
    )

    return {
        "input_smiles": smiles,
        "canonical_smiles": canonical_smiles,
        "formula": formula,
        "molecular_weight": round(molecular_weight, 3),
        "logp": round(logp, 3),
        "tpsa": round(tpsa, 3),
        "hbd": hbd,
        "hba": hba,
        "rotatable_bonds": rotatable_bonds,
        "rings": rings,
        "heavy_atoms": heavy_atoms,
        "aromatic_atoms": aromatic_atoms,
        "atom_count": atom_count,
        "bond_count": bond_count,
        "fragments": fragments,
        "lipinski_violations": violations,
        "lipinski_passes": violations == 0,
    }
