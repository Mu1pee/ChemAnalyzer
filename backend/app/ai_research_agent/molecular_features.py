import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import Crippen, Descriptors, Lipinski, rdFingerprintGenerator, rdMolDescriptors
from rdkit.Chem.Scaffolds import MurckoScaffold

FEATURE_CONFIG = {"morgan_radius": 2, "morgan_bits": 1024, "chirality": True,
                  "descriptors": ["MolWt", "MolLogP", "TPSA", "HBD", "HBA", "RotatableBonds"],
                  "standardization": "sanitize; canonical isomeric SMILES; reject mixtures/salts; preserve charges and stereochemistry"}
GENERATOR = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=1024, includeChirality=True)


def molecule(smiles):
    if not isinstance(smiles, str) or not smiles.strip() or len(smiles) > 4000:
        raise ValueError("Missing or oversized SMILES")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None or mol.GetNumAtoms() == 0 or mol.GetNumAtoms() > 200:
        raise ValueError("Invalid or oversized molecular structure")
    if len(Chem.GetMolFrags(mol)) != 1:
        raise ValueError("Multiple fragments: explicit salt/mixture curation required")
    return mol


def vector(mol):
    bits = np.zeros(1024, dtype=np.uint8)
    DataStructs.ConvertToNumpyArray(GENERATOR.GetFingerprint(mol), bits)
    desc = [Descriptors.MolWt(mol), Crippen.MolLogP(mol), rdMolDescriptors.CalcTPSA(mol),
            Lipinski.NumHDonors(mol), Lipinski.NumHAcceptors(mol), Lipinski.NumRotatableBonds(mol)]
    return np.concatenate([bits, desc]).astype(np.float32)


def prepare(rows, initial_issues=()):
    issues, transformations, buckets = list(initial_issues), [], {}
    for row in rows:
        try:
            mol = molecule(row.get("smiles"))
            canonical = Chem.MolToSmiles(mol, isomericSmiles=True)
            # Stereo variants share a leakage group; exact identity retains stereo.
            scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False) or "ACYCLIC"
            transformations.append(dict(row=row["row"], original=row["smiles"], canonical=canonical,
                                        action="canonicalized" if canonical != row["smiles"] else "unchanged"))
            buckets.setdefault(canonical, []).append((row, mol, scaffold))
        except (ValueError, RuntimeError) as error:
            issues.append(dict(row=row["row"], category="structure_error", message=str(error)))
    records, features, groups, labels = [], [], [], []
    for canonical, entries in sorted(buckets.items()):
        values = {entry[0]["value"] for entry in entries}
        if len(values) != 1:
            issues.extend(dict(row=e[0]["row"], category="conflicting_duplicate") for e in entries)
            continue
        row, mol, group = entries[0]
        issues.extend(dict(row=e[0]["row"], category="duplicate", retained_row=row["row"]) for e in entries[1:])
        records.append(dict(row, canonical_smiles=canonical, scaffold=group))
        features.append(vector(mol))
        groups.append(group)
        labels.append(row["value"])
    return (np.asarray(features, dtype=np.float32), np.asarray(labels), np.asarray(groups),
            dict(accepted=len(records), records=records, issues=issues, transformations=transformations))
