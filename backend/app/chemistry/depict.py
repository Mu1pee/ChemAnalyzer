"""2D-изображение структуры (SVG) средствами RDKit — для экспорта и отчётов."""

from rdkit.Chem import rdDepictor
from rdkit.Chem.Draw import rdMolDraw2D

from app.chemistry import fingerprints as fp


def depict_svg(smiles: str, width: int = 480, height: int = 360) -> str:
    mol = fp.mol_from_smiles(smiles)
    if mol is None:
        raise ValueError(
            "Некорректный SMILES. Не удалось распознать химическую структуру."
        )

    mol = fp.standardize(mol)
    rdDepictor.Compute2DCoords(mol)

    drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
    drawer.DrawMolecule(mol)
    drawer.FinishDrawing()
    return drawer.GetDrawingText()
