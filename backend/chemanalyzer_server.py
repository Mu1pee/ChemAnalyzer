"""Точка входа backend для desktop-сборки (PyInstaller) и запуска вручную.

    python chemanalyzer_server.py --port 8765

Слушает только 127.0.0.1 — наружу в сеть сервер не открывается.
"""

import argparse
import multiprocessing
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="ChemAnalyzer backend")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()

    if not (1024 <= args.port <= 65535):
        print("Некорректный порт", file=sys.stderr)
        return 2

    # Для надёжности даже при ошибке запуска вручную.
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    import uvicorn

    from app.main import app

    uvicorn.run(
        app,
        host="127.0.0.1",  # намеренно не настраивается
        port=args.port,
        log_level="warning",
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()  # нужно для замороженного приложения
    sys.exit(main())
