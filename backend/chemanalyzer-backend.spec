# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: backend ChemAnalyzer (FastAPI + RDKit + scikit-learn).
#
# Сборка (из папки backend, venv активирован):
#   pyinstaller --noconfirm --clean chemanalyzer-backend.spec
#
# Режим onedir (папка, а не один файл): быстрее стартует и реже вызывает
# ложные срабатывания антивируса, чем onefile.
from PyInstaller.utils.hooks import collect_all, collect_submodules
from pathlib import Path
import ssl

datas, binaries, hiddenimports = [], [], []

# This Python distribution augments SSLContext with a public CA rejection list.
# Frozen ssl.__file__ lives in _internal; preserve its adjacent runtime resource.
# Normal Python distributions have no such file. Never disable verification.
runtime_ca = Path(ssl.__file__).with_name("codex-rejected-cas.pem")
if runtime_ca.is_file():
    datas.append((str(runtime_ca), "."))

# Пакеты с нативными библиотеками и данными собираем целиком.
for package in ("rdkit", "sklearn", "scipy", "numpy", "joblib", "threadpoolctl"):
    d, b, h = collect_all(package, filter_submodules=lambda name: not any(
        part in ("tests", "test", "conftest") for part in name.split(".")
    ))
    datas += d
    binaries += b
    hiddenimports += h

# uvicorn подгружает протоколы и циклы по имени строки.
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("anyio")
hiddenimports += collect_submodules("app.ai_research_agent")
hiddenimports += collect_submodules("psutil")
hiddenimports += ["dotenv", "anthropic", "httpx", "multipart"]

a = Analysis(
    ["chemanalyzer_server.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # training/ и тесты в поставку не нужны.
    excludes=["tkinter", "IPython", "pytest", "training", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="chemanalyzer-backend",
    debug=False,
    strip=False,
    upx=False,          # UPX чаще вызывает ложные срабатывания антивирусов
    console=True,       # консоль скрывает Electron (windowsHide), а stdout нужен для логов
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="chemanalyzer-backend",
)
