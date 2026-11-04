"""Smoke test a real frozen backend with curated CSV; never activates models."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time

import httpx


def main():
    parser = argparse.ArgumentParser()
    for name in ("exe", "csv", "provenance", "storage"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    args.storage.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, CHEMANALYZER_DATA_DIR=str(args.storage.resolve()),
                       CHEMANALYZER_RESEARCH_ENABLED="1", CHEMANALYZER_DESKTOP="1")
    log = (args.storage / "backend.log").open("w", encoding="utf-8")
    process = subprocess.Popen([str(args.exe.resolve()), "--port", str(port)], env=environment,
                               stdout=log, stderr=subprocess.STDOUT,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    result = {}
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=60) as client:
            for _ in range(90):
                if process.poll() is not None:
                    raise RuntimeError("Frozen backend exited; inspect backend.log")
                try:
                    response = client.get("/health")
                    if response.is_success:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(1)
            else:
                raise RuntimeError("Frozen backend startup timeout")

            def post(path, body):
                response = client.post(path, json=body)
                response.raise_for_status()
                return response.json()

            result["health"] = response.json()
            result["formula"] = post("/api/molecules/analyze", {"smiles": "CC(=O)Oc1ccccc1C(=O)O"})["formula"]
            assert result["formula"] == "C9H8O4"
            provenance = json.loads(args.provenance.read_text(encoding="utf-8"))
            task = post("/api/research/tasks", dict(name="Frozen FreeSolv smoke",
                        endpoint=provenance["endpoint"], units=provenance["units"], context=provenance["context"]))
            post(f"/api/research/tasks/{task['id']}/import", dict(
                csv_text=args.csv.read_text(encoding="utf-8"), provenance=provenance))
            run = post(f"/api/research/tasks/{task['id']}/train", {})
            for _ in range(180):
                state = client.get(f"/api/research/runs/{run['id']}").json()
                if state["status"] not in ("queued", "running"):
                    break
                time.sleep(1)
            assert state["status"] == "completed", state
            identifier = state["model_id"]
            result["model_id"] = identifier
            result["evaluation"] = state["result"]["evaluation"]
            result["prediction"] = post(f"/api/research/models/{identifier}/predict", {"smiles": "CCO"})
            assert result["prediction"]["status"] == "experimental"
            assert len(client.get("/api/research/models").json()) == 1
            run = post(f"/api/research/tasks/{task['id']}/train", {})
            result["cancellation"] = post(f"/api/research/runs/{run['id']}/cancel", {})["status"]
            assert result["cancellation"] == "cancelled"
            result["passed"] = True
            (args.storage / "smoke_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(dict(passed=True, model_id=identifier, test=result["evaluation"]["test"], cancellation=result["cancellation"]), indent=2))
    finally:
        process.terminate()
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        log.close()


if __name__ == "__main__":
    main()
