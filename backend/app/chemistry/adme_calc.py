"""Формулы ADME без RDKit (их можно тестировать на любых числах).

Источники: ESOL — Delaney, J. Chem. Inf. Comput. Sci. 2004; Log Kp — Potts &
Guy, Pharm. Res. 1992; радар биодоступности, классы растворимости и правила
Muegge / lead-likeness — по описанию SwissADME (Daina et al., Sci. Rep. 2017).
Все формулы сверены со значениями на рисунке SwissADME (см. tests/test_adme_calc.py).
"""

import math

# ---------------------------------------------------------------- растворимость и кожа


def esol_logs(clogp: float, mw: float, rotb: int, aromatic_proportion: float) -> float:
    """ESOL: logS = 0.16 − 0.63·cLogP − 0.0062·MW + 0.066·RB − 0.74·AP."""
    return 0.16 - 0.63 * clogp - 0.0062 * mw + 0.066 * rotb - 0.74 * aromatic_proportion


def solubility_class(logs: float) -> str:
    """Шкала SwissADME: insoluble < −10 < poorly < −6 < moderately < −4 < soluble
    < −2 < very soluble < 0 < highly soluble."""
    if logs < -10:
        return "нерастворимое"
    if logs < -6:
        return "плохо растворимое"
    if logs < -4:
        return "умеренно растворимое"
    if logs < -2:
        return "растворимое"
    if logs < 0:
        return "хорошо растворимое"
    return "очень хорошо растворимое"


def solubility(logs: float, mw: float) -> dict:
    mol_l = 10 ** logs
    return {
        "esol_logs": round(logs, 2),
        "esol_mol_l": mol_l,
        "esol_mg_ml": mol_l * mw,  # г/л == мг/мл
        "esol_class": solubility_class(logs),
    }


def log_kp(clogp: float, mw: float) -> float:
    """Проницаемость кожи (Potts & Guy), см/с: logKp = 0.71·logP − 0.0061·MW − 6.3."""
    return 0.71 * clogp - 0.0061 * mw - 6.3


# ---------------------------------------------------------------- радар биодоступности

# key, подпись, зона «оптимума» по SwissADME (центр радара = нижняя граница,
# край розового шестиугольника = верхняя граница)
_RADAR = [
    ("LIPO", "Липофильность (логP)", -0.7, 5.0, ""),
    ("SIZE", "Размер (масса)", 150.0, 500.0, "г/моль"),
    ("POLAR", "Полярность (TPSA)", 20.0, 130.0, "Å²"),
    ("INSOLU", "Растворимость (−logS)", 0.0, 6.0, ""),
    ("INSATU", "Насыщенность (Fsp3)", 0.25, 1.0, ""),
    ("FLEX", "Гибкость (вращ. связи)", 0.0, 9.0, ""),
]


def radar(wlogp: float, mw: float, tpsa: float, logs: float, fsp3: float, rotb: int) -> list[dict]:
    values = {
        "LIPO": wlogp,
        "SIZE": mw,
        "POLAR": tpsa,
        "INSOLU": -logs,
        "INSATU": fsp3,
        "FLEX": float(rotb),
    }
    axes = []
    for key, label, ok_min, ok_max, unit in _RADAR:
        value = values[key]
        axes.append(
            {
                "key": key,
                "label": label,
                "value": round(value, 3),
                "ok_min": ok_min,
                "ok_max": ok_max,
                "in_range": ok_min <= value <= ok_max,
                "unit": unit,
            }
        )
    return axes


# ---------------------------------------------------------------- правила


def rule(name: str, checks: list[tuple[str, bool]], max_violations: int = 0) -> dict:
    """checks: (описание нарушения, выполнено ли условие)."""
    violations = [text for text, ok in checks if not ok]
    return {
        "name": name,
        "passed": len(violations) <= max_violations,
        "violations": violations,
    }


def lipinski(mw: float, wlogp: float, hbd: int, hba: int) -> dict:
    # Правило допускает одно нарушение.
    return rule(
        "Липински",
        [
            (f"масса {mw:.1f} > 500", mw <= 500),
            (f"логP {wlogp:.2f} > 5", wlogp <= 5),
            (f"доноры H-связи {hbd} > 5", hbd <= 5),
            (f"акцепторы H-связи {hba} > 10", hba <= 10),
        ],
        max_violations=1,
    )


def ghose(mw: float, wlogp: float, mr: float, atoms: int) -> dict:
    return rule(
        "Гхош",
        [
            ("MW < 160" if mw < 160 else "MW > 480", 160 <= mw <= 480),
            ("логP < −0.4" if wlogp < -0.4 else "логP > 5.6", -0.4 <= wlogp <= 5.6),
            ("MR < 40" if mr < 40 else "MR > 130", 40 <= mr <= 130),
            ("атомов < 20" if atoms < 20 else "атомов > 70", 20 <= atoms <= 70),
        ],
    )


def veber(rotb: int, tpsa: float) -> dict:
    return rule(
        "Вебер",
        [
            (f"вращаемых связей {rotb} > 10", rotb <= 10),
            (f"TPSA {tpsa:.1f} > 140", tpsa <= 140),
        ],
    )


def egan(wlogp: float, tpsa: float) -> dict:
    return rule(
        "Иган",
        [
            (f"логP {wlogp:.2f} > 5.88", wlogp <= 5.88),
            (f"TPSA {tpsa:.1f} > 131.6", tpsa <= 131.6),
        ],
    )


def muegge(
    mw: float, wlogp: float, tpsa: float, rings: int, carbons: int,
    heteroatoms: int, rotb: int, hba: int, hbd: int,
) -> dict:
    return rule(
        "Мюгге",
        [
            ("MW < 200" if mw < 200 else "MW > 600", 200 <= mw <= 600),
            ("логP < −2" if wlogp < -2 else "логP > 5", -2 <= wlogp <= 5),
            ("TPSA > 150", tpsa <= 150),
            ("колец > 7", rings <= 7),
            ("атомов углерода ≤ 4", carbons > 4),
            ("гетероатомов < 2", heteroatoms > 1),
            ("вращаемых связей > 15", rotb <= 15),
            ("HBA > 10", hba <= 10),
            ("HBD > 5", hbd <= 5),
        ],
    )


def lead_likeness(mw: float, wlogp: float, rotb: int) -> dict:
    return rule(
        "Lead-likeness",
        [
            ("MW < 250" if mw < 250 else "MW > 350", 250 <= mw <= 350),
            ("логP > 3.5", wlogp <= 3.5),
            ("вращаемых связей > 7", rotb <= 7),
        ],
    )


def is_finite(*values: float) -> bool:
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in values)
