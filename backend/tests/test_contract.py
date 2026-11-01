"""Контракт «код backend ↔ схемы Pydantic ↔ типы TypeScript» (RDKit не нужен).

Тест разбирает исходники через ast/регулярные выражения и ловит расхождения,
которые иначе проявились бы только в рантайме: поле, которое функция не
возвращает (FastAPI ответит 500), или поле во frontend, которого нет в API.
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FRONT_TYPES = ROOT.parent / "frontend" / "src" / "types" / "molecule.ts"
SCHEMAS = ROOT / "app" / "schemas" / "molecule.py"


# ---------------------------------------------------------------- схемы

def load_schemas() -> dict[str, dict[str, dict]]:
    """класс -> поле -> {required, ann}"""
    tree = ast.parse(SCHEMAS.read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            fields = {}
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    default = item.value
                    required = default is None or (
                        isinstance(default, ast.Call)
                        and getattr(default.func, "id", "") == "Field"
                        and default.args
                        and isinstance(default.args[0], ast.Constant)
                        and default.args[0].value is Ellipsis
                    )
                    fields[item.target.id] = {"required": required, "ann": ast.unparse(item.annotation)}
            out[node.name] = fields
    return out


SCHEMA = load_schemas()


def dict_literal(path: str, func: str, var: str | None = None) -> ast.Dict:
    """Словарь-литерал, который возвращает функция (или присваивается переменной var)."""
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func:
            for sub in ast.walk(node):
                if var is None and isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict):
                    return sub.value
                if var is not None and isinstance(sub, (ast.Assign, ast.AnnAssign)):
                    target = sub.targets[0] if isinstance(sub, ast.Assign) else sub.target
                    if isinstance(target, ast.Name) and target.id == var and isinstance(sub.value, ast.Dict):
                        return sub.value
    raise AssertionError(f"не найден словарь в {path}:{func}")


def keys_of(d: ast.Dict) -> dict[str, ast.AST]:
    return {k.value: v for k, v in zip(d.keys, d.values) if isinstance(k, ast.Constant)}


def check(d: ast.Dict, cls: str, *, provided_elsewhere: tuple[str, ...] = (), path: str = "") -> list[str]:
    problems = []
    fields = SCHEMA[cls]
    given = keys_of(d)
    for name, spec in fields.items():
        if spec["required"] and name not in given and name not in provided_elsewhere:
            problems.append(f"{path}{cls}.{name}: обязательное поле не возвращается")
    for name, value in given.items():
        if name not in fields:
            problems.append(f"{path}{cls}: лишний ключ «{name}» (нет в схеме)")
            continue
        nested = re.fullmatch(r"([A-Z]\w+)", fields[name]["ann"])
        if nested and nested.group(1) in SCHEMA and isinstance(value, ast.Dict):
            problems += check(value, nested.group(1), path=f"{path}{cls}.{name}.")
    return problems


CASES = [
    ("app/chemistry/descriptors.py", "analyze_molecule", None, "MoleculeResponse", ()),
    ("app/chemistry/druglikeness.py", "assess_druglikeness", None, "Druglikeness", ()),
    ("app/chemistry/activity.py", "predict_activity", None, "ActivityResponse", ("druglikeness", "qsar")),
    ("app/chemistry/qsar.py", "predict_qsar", "base", "QsarResult", ()),
    ("app/chemistry/adme.py", "compute_adme", None, "AdmeResponse", ()),
    ("app/chemistry/conformer.py", "generate_conformer", None, "ConformerResponse", ()),
    ("app/api/pubchem.py", "_empty_result", None, "IdentificationResult", ()),
    ("app/api/chembl.py", "fetch_chembl_profile", "profile", "ChemblResponse", ()),
]


@pytest.mark.parametrize("path,func,var,cls,elsewhere", CASES)
def test_function_output_matches_schema(path, func, var, cls, elsewhere):
    problems = check(dict_literal(path, func, var), cls, provided_elsewhere=elsewhere)
    assert problems == [], "\n".join(problems)


# ---------------------------------------------------------------- TypeScript

# TS-интерфейс -> класс схемы (если имена различаются)
TS_TO_SCHEMA = {
    "BoiledEgg": "BoiledEggModel",
    "BoiledEggModel": "BoiledEggModel",
}
# Поля, которые есть только на стороне frontend (состояние интерфейса, не ответ API).
TS_ONLY = {"HistoryItem", "AsyncState", "ChatMessage", "AssistantStatus", "TargetProtein",
           "TargetProteins", "ProteinStructure", "ChemblMechanism", "ChemblIndication",
           "ChemblTarget", "ChemblSimilar", "ActivitySupport"}


def ts_interfaces() -> dict[str, set[str]]:
    text = FRONT_TYPES.read_text(encoding="utf-8")
    result = {}
    for m in re.finditer(r"export interface (\w+)(?:<[^>]*>)? \{(.*?)\n\}", text, re.S):
        body = m.group(2)
        # только поля верхнего уровня (вложенные { ... } вырезаем)
        flat, depth = [], 0
        for ch in body:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            elif depth == 0:
                flat.append(ch)
        names = set(re.findall(r"^\s*(\w+)\??:", "".join(flat), re.M))
        # поля, объявленные во вложенных объектах, считаем частью родителя целиком —
        # поэтому сравниваем только корневые имена из регулярного выражения по исходному телу
        names |= set(re.findall(r"^  (\w+)\??:", body, re.M))
        result[m.group(1)] = names
    return result


TS = ts_interfaces()


@pytest.mark.parametrize("ts_name", sorted(n for n in TS if TS_TO_SCHEMA.get(n, n) in SCHEMA))
def test_typescript_fields_match_schema(ts_name):
    schema_name = TS_TO_SCHEMA.get(ts_name, ts_name)
    ts_fields, py_fields = TS[ts_name], set(SCHEMA[schema_name])
    only_ts = ts_fields - py_fields
    only_py = py_fields - ts_fields
    assert not only_ts, f"{ts_name}: во frontend есть поля, которых нет в API: {sorted(only_ts)}"
    assert not only_py, f"{ts_name}: API отдаёт поля, которых нет в типах frontend: {sorted(only_py)}"
