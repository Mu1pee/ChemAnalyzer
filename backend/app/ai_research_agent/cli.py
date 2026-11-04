"""python -m app.ai_research_agent.cli demo | list | run TASK_ID. Ctrl+C cancels."""
import argparse
import json
import multiprocessing
import time
from pathlib import Path

from .config import FREESOLV_TASK, TaskConfig, Provenance
from .orchestrator import ResearchAgent
from .model_registry import Registry


def main():
    parser = argparse.ArgumentParser(description="ChemAnalyzer AI Research Agent")
    parser.add_argument("command", choices=["demo", "list", "create", "import", "run", "prepare", "predict"])
    parser.add_argument("identifier", nargs="?")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--provenance", type=Path)
    parser.add_argument("--smiles")
    args = parser.parse_args()
    agent = ResearchAgent(args.root)
    try:
        if args.command == "list":
            print(json.dumps(dict(tasks=agent.tasks(), runs=agent.runs(), models=Registry(agent.root).list()), ensure_ascii=False, indent=2))
            return 0
        if args.command == "create":
            print(json.dumps(agent.create(TaskConfig.model_validate_json(args.config.read_text(encoding="utf-8"))), ensure_ascii=False))
            return 0
        if args.command == "import":
            result = agent.import_csv(args.identifier, args.csv.read_text(encoding="utf-8-sig"), Provenance.model_validate_json(args.provenance.read_text(encoding="utf-8")))
            print(json.dumps(result, ensure_ascii=False))
            return 0
        if args.command == "predict":
            print(json.dumps(Registry(agent.root).predict(args.identifier, args.smiles), ensure_ascii=False, indent=2))
            return 0
        identifier = args.identifier
        if args.command == "demo":
            identifier = agent.create(TaskConfig(**FREESOLV_TASK))["id"]
            print("Importing pinned FreeSolv text and license...", flush=True)
            print(json.dumps(agent.import_freesolv(identifier)), flush=True)
        run = agent.start(identifier, "prepare" if args.command == "prepare" else "train")
        previous = None
        while True:
            state = agent.run(run["id"])
            if state["stage"] != previous:
                print(state["stage"], flush=True)
                previous = state["stage"]
            if state["status"] not in ("queued", "running"):
                # Wait for supervisor publication.
                agent.jobs[run["id"]].join()
                agent.monitors[run["id"]].join()
                state = agent.run(run["id"])
                print(json.dumps(state, ensure_ascii=False, indent=2), flush=True)
                return 0 if state["status"] == "completed" else 1
            time.sleep(.5)
    except KeyboardInterrupt:
        print("Cancelled by user", flush=True)
        return 130
    except (ValueError, OSError) as error:
        print(f"Research error: {error}", flush=True)
        return 1
    finally:
        agent.shutdown()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
