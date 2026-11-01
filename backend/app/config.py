"""Настройки из переменных окружения и файла .env.

В desktop-режиме Electron задаёт CHEMANALYZER_DATA_DIR (папка данных
пользователя, например %APPDATA%\\ChemAnalyzer). Туда кладутся:
  .env      — секреты (ANTHROPIC_API_KEY), только на стороне backend
  models\\   — обученные QSAR-модели
"""

import os
from pathlib import Path

DEFAULT_MODEL = "claude-sonnet-5-5"
BACKEND_DIR = Path(__file__).resolve().parent.parent


def data_dir() -> Path | None:
    value = os.environ.get("CHEMANALYZER_DATA_DIR", "").strip()
    return Path(value) if value else None


def is_desktop() -> bool:
    return os.environ.get("CHEMANALYZER_DESKTOP", "") == "1"


def frontend_dist() -> Path | None:
    value = os.environ.get("CHEMANALYZER_FRONTEND_DIST", "").strip()
    path = Path(value) if value else None
    return path if path and path.is_dir() else None


def models_dir() -> Path:
    override = os.environ.get("CHEMANALYZER_MODELS_DIR", "").strip()
    if override:
        return Path(override)
    base = data_dir()
    return (base / "models") if base else (BACKEND_DIR / "models")


def _load_env_file() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # python-dotenv не обязателен: можно задать переменные в системе
        return

    base = data_dir()
    if base and (base / ".env").is_file():
        load_dotenv(base / ".env")
    load_dotenv()  # .env рядом с backend (dev-режим); не перезаписывает заданное


_load_env_file()


def anthropic_api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return key or None


def claude_model() -> str:
    return os.environ.get("CLAUDE_MODEL", "").strip() or DEFAULT_MODEL


def assistant_max_tokens() -> int:
    try:
        return max(200, min(4000, int(os.environ.get("ASSISTANT_MAX_TOKENS", "1500"))))
    except ValueError:
        return 1500
