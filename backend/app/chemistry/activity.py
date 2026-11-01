"""Прогноз спектра биологической активности по структурному сходству.

Метод: молекула сравнивается (Tanimoto по отпечаткам Моргана) с библиотекой
известных препаратов. Каждая активность получает оценку, равную максимальному
сходству среди препаратов, у которых эта активность известна.

Важно: это упрощённая оценка "по аналогии", а не вероятности PASS и не
обученная QSAR-модель. Ей нельзя заменять эксперимент.
"""

from dataclasses import dataclass
from functools import lru_cache

from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator

from app.chemistry import fingerprints as fp
from app.chemistry.reference_drugs import REFERENCE_DRUGS

MIN_SCORE = 0.25  # ниже — считаем, что аналогов нет
HIGH_SCORE = 0.65
MEDIUM_SCORE = 0.40
TOP_ACTIVITIES = 15
TOP_NEIGHBORS = 5
SUPPORT_PER_ACTIVITY = 3

_generator = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)


@dataclass(frozen=True)
class Neighbor:
    name: str
    similarity: float
    activities: tuple[str, ...]


def confidence_label(score: float) -> str:
    if score >= HIGH_SCORE:
        return "высокая"
    if score >= MEDIUM_SCORE:
        return "средняя"
    return "низкая"


def aggregate_spectrum(neighbors: list[Neighbor]) -> list[dict]:
    """Сводит соседей в спектр активностей (чистая функция, без RDKit)."""
    per_activity: dict[str, list[tuple[str, float]]] = {}

    for neighbor in neighbors:
        if neighbor.similarity < MIN_SCORE:
            continue
        for activity in neighbor.activities:
            per_activity.setdefault(activity, []).append(
                (neighbor.name, neighbor.similarity)
            )

    spectrum = []
    for activity, supports in per_activity.items():
        supports.sort(key=lambda item: item[1], reverse=True)
        score = supports[0][1]
        spectrum.append(
            {
                "name": activity,
                "score": round(score, 3),
                "confidence": confidence_label(score),
                "support": [
                    {"drug": drug, "similarity": round(sim, 3)}
                    for drug, sim in supports[:SUPPORT_PER_ACTIVITY]
                ],
            }
        )

    spectrum.sort(key=lambda item: (-item["score"], item["name"]))
    return spectrum[:TOP_ACTIVITIES]


@lru_cache(maxsize=1)
def _reference_index() -> tuple[list, list[tuple[str, tuple[str, ...]]]]:
    fingerprints = []
    meta = []

    for name, smiles, activities in REFERENCE_DRUGS:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            continue
        fingerprints.append(_generator.GetFingerprint(fp.standardize(mol)))
        meta.append((name, tuple(activities)))

    return fingerprints, meta


def predict_activity(smiles: str) -> dict:
    smiles = smiles.strip()
    mol = Chem.MolFromSmiles(smiles) if smiles else None

    if mol is None or mol.GetNumAtoms() == 0:
        raise ValueError(
            "Некорректный SMILES. Не удалось распознать химическую структуру."
        )

    mol = fp.standardize(mol)
    fingerprint = _generator.GetFingerprint(mol)
    reference_fps, meta = _reference_index()

    similarities = DataStructs.BulkTanimotoSimilarity(
        fingerprint, reference_fps
    )

    neighbors = [
        Neighbor(name=name, similarity=float(sim), activities=activities)
        for (name, activities), sim in zip(meta, similarities)
    ]
    neighbors.sort(key=lambda n: n.similarity, reverse=True)

    nearest = [
        {
            "name": n.name,
            "similarity": round(n.similarity, 3),
            "activities": list(n.activities),
        }
        for n in neighbors[:TOP_NEIGHBORS]
        if n.similarity >= MIN_SCORE
    ]

    spectrum = aggregate_spectrum(neighbors)

    return {
        "method": "Сходство Tanimoto (отпечатки Моргана, радиус 2) "
        "с библиотекой известных препаратов",
        "reference_size": len(meta),
        "activities": spectrum,
        "nearest": nearest,
        "message": None
        if spectrum
        else (
            "Близких аналогов в справочной библиотеке не найдено "
            f"(порог сходства {MIN_SCORE}). Это не означает отсутствие "
            "активности."
        ),
        "disclaimer": (
            "Оценка получена по структурному сходству с небольшой "
            "библиотекой препаратов. Это не вероятности PASS и не "
            "прогноз обученной модели — используйте только для "
            "первичной ориентации."
        ),
    }
