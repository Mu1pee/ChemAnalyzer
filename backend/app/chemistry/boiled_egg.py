"""BOILED-Egg (Daina & Zoete, ChemMedChem 2016, 11, 1117–1121).

Модель в координатах «TPSA (x) – WLOGP (y)»:
  белок  — область высокого пассивного всасывания в ЖКТ (HIA);
  желток — область проникновения через гематоэнцефалический барьер (BBB).
Области не взаимоисключающие (желток может выходить за пределы белка).

Контуры в статье заданы эллипсами. Параметры ниже получены подгонкой по
опубликованным в дополнительных материалах статьи координатам контуров
(невязка подгонки нулевая) и независимо проверены по рисунку SwissADME.

Важно: в оригинальной модели TPSA считается С УЧЁТОМ S и P
(RDKit: CalcTPSA(mol, includeSandP=True)), а WLOGP — это логP по
Уайлдману–Крипену, то есть Crippen MolLogP в RDKit.
"""

import math

# центр (cx, cy), полуоси a (длинная) и b, угол наклона длинной оси в градусах
# в координатах данных (против часовой стрелки от оси TPSA).
WHITE = {"cx": 71.027362, "cy": 2.294541, "a": 71.017809, "b": 4.355863, "angle": 178.954871}
YOLK = {"cx": 38.068649, "cy": 3.184948, "a": 41.031823, "b": 2.777643, "angle": 179.841462}

SOURCE = (
    "Daina A., Zoete V. A BOILED-Egg to predict gastrointestinal absorption "
    "and brain penetration of small molecules. ChemMedChem 2016, 11, 1117–1121."
)


def inside(tpsa: float, wlogp: float, ellipse: dict) -> bool:
    """Лежит ли точка (TPSA, WLOGP) внутри эллипса (границы включаются)."""
    theta = math.radians(ellipse["angle"])
    dx, dy = tpsa - ellipse["cx"], wlogp - ellipse["cy"]
    u = dx * math.cos(theta) + dy * math.sin(theta)
    v = -dx * math.sin(theta) + dy * math.cos(theta)
    return (u / ellipse["a"]) ** 2 + (v / ellipse["b"]) ** 2 <= 1.0


def classify(tpsa: float, wlogp: float) -> dict:
    return {
        "gi_absorption": inside(tpsa, wlogp, WHITE),
        "bbb_permeant": inside(tpsa, wlogp, YOLK),
    }
