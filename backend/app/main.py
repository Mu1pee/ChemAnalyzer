import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__, config
from app.api.assistant import router as assistant_router
from app.api.molecules import router as molecules_router
from app.api.structure import router as structure_router

DESKTOP = config.is_desktop()
FRONTEND = config.frontend_dist()

app = FastAPI(
    title="ChemAnalyzer API",
    description=(
        "Анализ химических структур (RDKit), идентификация в PubChem, "
        "данные ChEMBL, QSAR, ПК «Антидот-Прогноз» и 3D."
    ),
    version=__version__,
    # В desktop-режиме интерактивная документация API не нужна.
    docs_url=None if DESKTOP else "/docs",
    redoc_url=None if DESKTOP else "/redoc",
    openapi_url=None if DESKTOP else "/openapi.json",
)

if DESKTOP:
    # Desktop: интерфейс и API на одном origin (127.0.0.1:порт), поэтому CORS
    # не нужен вообще, а чужие сайты в браузере не получают доступа к API.
    # Проверка Host защищает от DNS rebinding.
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"]
    )
else:
    # Dev: Vite на другом порту (5173, при занятости 5174...).
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(
    molecules_router, prefix="/api/molecules", tags=["Molecules"]
)
app.include_router(assistant_router)
app.include_router(structure_router)


@app.get("/health")
def health():
    # Поле application позволяет Electron убедиться, что на порту именно
    # наш backend, а не посторонний сервис.
    return {
        "status": "healthy",
        "application": "ChemAnalyzer",
        "version": __version__,
    }


@app.get("/api/app/info")
def app_info():
    """Справочная информация для строки состояния (без секретов)."""
    return {
        "name": "ChemAnalyzer",
        "version": __version__,
        "desktop": DESKTOP,
        "assistant_configured": config.anthropic_api_key() is not None,
        "models_dir": str(config.models_dir()) if DESKTOP else None,
    }


if FRONTEND is not None:
    # Собранный интерфейс отдаётся самим backend. Монтируем ПОСЛЕ всех
    # маршрутов API, иначе статика перехватит их.
    app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="ui")
else:

    @app.get("/")
    def root():
        return {
            "status": "ok",
            "application": "ChemAnalyzer",
            "version": __version__,
        }
