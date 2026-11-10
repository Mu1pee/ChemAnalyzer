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
    parser.add_argument("--port", type=int)
    parser.add_argument("--check-network", action="store_true", help="Check bundled TLS certificates and the public ChEMBL status endpoint")
    args = parser.parse_args()

    if args.check_network:
        import json
        import traceback
        from pathlib import Path
        import certifi
        import httpx
        result = {"frozen": bool(getattr(sys, "frozen", False)),
                  "ca_file_exists": Path(certifi.where()).is_file(),
                  "certificate_env": {key: bool(os.environ.get(key)) for key in ("SSL_CERT_FILE", "SSL_CERT_DIR")}}
        try:
            with httpx.Client(timeout=20) as client:
                response = client.get("https://www.ebi.ac.uk/chembl/api/data/status.json")
                response.raise_for_status()
                result.update(ok=True, chembl_version=response.json().get("chembl_db_version"))
        except Exception as error:
            result.update(ok=False, error=type(error).__name__)
            traceback.print_exc()
        print(json.dumps(result))
        return 0 if result["ok"] else 1

    if args.port is None or not (1024 <= args.port <= 65535):
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
