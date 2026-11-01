"""BOILED-Egg и формулы ADME (RDKit не нужен).

Опорные числа взяты из рисунка SwissADME для циклогептана (C7H14) и из
опубликованных контуров модели (дополнительные материалы Daina & Zoete, 2016).
"""

import math

import pytest

from app.chemistry import adme_calc as calc
from app.chemistry import boiled_egg as egg

# Вершины опубликованных контуров (каждая 10-я) — должны лежать на подогнанных эллипсах.
WHITE_VERTICES = [(97.806, -2.227), (131.346, -1.1), (141.847, 1.323), (125.297, 4.118), (88.018, 6.216), (44.249, 6.816), (10.709, 5.689), (0.208, 3.266), (16.758, 0.471), (54.037, -1.627)]
YOLK_VERTICES = [(40.97, 0.406), (64.473, 0.986), (77.891, 2.406), (76.098, 4.123), (59.779, 5.482), (35.167, 5.964), (11.664, 5.384), (-1.754, 3.964), (0.04, 2.247), (16.359, 0.888)]


def residual(point, e):
    """Расстояние (в долях полуосей) от точки до эллипса: 0 — ровно на границе."""
    t = math.radians(e["angle"])
    dx, dy = point[0] - e["cx"], point[1] - e["cy"]
    u = dx * math.cos(t) + dy * math.sin(t)
    v = -dx * math.sin(t) + dy * math.cos(t)
    return abs(math.hypot(u / e["a"], v / e["b"]) - 1.0)


@pytest.mark.parametrize("point", WHITE_VERTICES)
def test_white_ellipse_matches_published_contour(point):
    assert residual(point, egg.WHITE) < 1e-3


@pytest.mark.parametrize("point", YOLK_VERTICES)
def test_yolk_ellipse_matches_published_contour(point):
    assert residual(point, egg.YOLK) < 1e-3


def test_cycloheptane_from_swissadme_screenshot():
    # TPSA 0.00, WLOGP 2.73: на рисунке SwissADME ЖКТ «Низкий», ГЭБ «Да».
    r = egg.classify(0.0, 2.73)
    assert r == {"gi_absorption": False, "bbb_permeant": True}


def test_classification_regions():
    assert egg.classify(60, 3) == {"gi_absorption": True, "bbb_permeant": True}
    assert egg.classify(110, 1) == {"gi_absorption": True, "bbb_permeant": False}
    assert egg.classify(200, 1) == {"gi_absorption": False, "bbb_permeant": False}
    assert egg.classify(331.43, -7.74)["gi_absorption"] is False  # стрептомицин (SwissADME)


def test_esol_matches_swissadme_screenshot():
    # SwissADME использует XLOGP3 = 4.00: logS = −2.97, 1.06e-01 мг/мл, 1.07e-03 моль/л.
    logs = calc.esol_logs(4.00, 98.19, 0, 0.0)
    assert logs == pytest.approx(-2.97, abs=0.01)
    s = calc.solubility(logs, 98.19)
    assert s["esol_mol_l"] == pytest.approx(1.07e-3, rel=0.02)
    assert s["esol_mg_ml"] == pytest.approx(1.06e-1, rel=0.03)
    assert s["esol_class"] == "растворимое"  # на рисунке «Растворимый»


def test_log_kp_matches_swissadme_screenshot():
    assert calc.log_kp(4.00, 98.19) == pytest.approx(-4.06, abs=0.01)


@pytest.mark.parametrize(
    "logs,expected",
    [(-11, "нерастворимое"), (-7, "плохо растворимое"), (-5, "умеренно растворимое"),
     (-3, "растворимое"), (-1, "хорошо растворимое"), (0.5, "очень хорошо растворимое")],
)
def test_solubility_classes(logs, expected):
    assert calc.solubility_class(logs) == expected


def test_cycloheptane_rules_match_screenshot():
    mw, wlogp, mr, atoms = 98.19, 2.73, 33.65, 21
    assert calc.lipinski(mw, wlogp, 0, 0) == {"name": "Липински", "passed": True, "violations": []}
    g = calc.ghose(mw, wlogp, mr, atoms)  # на рисунке: «Нет; 2 нарушения: MW<160, MR<40»
    assert not g["passed"] and g["violations"] == ["MW < 160", "MR < 40"]
    assert calc.veber(0, 0.0)["passed"] and calc.egan(wlogp, 0.0)["passed"]
    m = calc.muegge(mw, wlogp, 0.0, 1, 7, 0, 0, 0, 0)  # «2 нарушения: MW<200, гетероатомов<2»
    assert not m["passed"] and m["violations"] == ["MW < 200", "гетероатомов < 2"]


def test_lipinski_allows_one_violation_only():
    assert calc.lipinski(600, 3, 1, 1)["passed"] is True
    two = calc.lipinski(600, 6, 1, 1)
    assert two["passed"] is False and len(two["violations"]) == 2


def test_lead_likeness():
    ok = calc.lead_likeness(300, 3.0, 5)
    assert ok["passed"] and ok["violations"] == []
    bad = calc.lead_likeness(98, 4.0, 0)
    assert bad["violations"] == ["MW < 250", "логP > 3.5"]


def test_radar_ranges():
    axes = {a["key"]: a for a in calc.radar(2.73, 98.19, 0.0, -2.17, 1.0, 0)}
    assert list(axes) == ["LIPO", "SIZE", "POLAR", "INSOLU", "INSATU", "FLEX"]
    assert axes["LIPO"]["in_range"] and axes["INSATU"]["in_range"] and axes["FLEX"]["in_range"]
    assert not axes["SIZE"]["in_range"]       # 98 < 150
    assert not axes["POLAR"]["in_range"]      # TPSA 0 < 20
    assert axes["INSOLU"]["value"] == pytest.approx(2.17, abs=1e-6)
    assert all(a["ok_min"] < a["ok_max"] for a in axes.values())
    assert all("display_min" not in a for a in axes.values())
