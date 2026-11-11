"""Reproduce reviewed TDC/Veith CYP runs in a fresh local registry.

From backend: python -m training.train_cyp --isoform CYP1A2 --output-dir <fresh-directory>
"""
import argparse
import json
import multiprocessing
from pathlib import Path
import time

from app.ai_research_agent.config import TaskConfig
from app.ai_research_agent.model_registry import Registry
from app.ai_research_agent.orchestrator import ResearchAgent
from app.ai_research_agent.tdc_cyp import FILES, task_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isoform", choices=["all", *FILES], default="all")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("Use a fresh directory; previous datasets, runs and test results must be preserved")
    agent = ResearchAgent(args.output_dir)
    results = []
    try:
        for isoform in (FILES if args.isoform == "all" else [args.isoform]):
            task = agent.create(TaskConfig(**task_config(isoform)))
            imported = agent.import_tdc_cyp(task["id"])
            run = agent.start(task["id"])
            print(json.dumps(dict(isoform=isoform, task_id=task["id"], run_id=run["id"], source_rows=imported["measurements"])), flush=True)
            previous = None
            while True:
                state = agent.run(run["id"])
                if state["stage"] != previous:
                    print(json.dumps(dict(isoform=isoform, stage=state["stage"], status=state["status"])), flush=True)
                    previous = state["stage"]
                if state["status"] not in ("queued", "running"):
                    break
                time.sleep(1)
            if state["status"] != "completed":
                print(json.dumps(state), flush=True)
                return 1
            meta = Registry(args.output_dir).metadata(state["model_id"])
            results.append(meta)
            print(json.dumps(dict(isoform=isoform, model_id=meta["id"], quality=meta["quality"], test=meta["evaluation"]["test"])), flush=True)
        (args.output_dir / "training-results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        return 0 if all(model["quality"]["passed"] for model in results) else 1
    finally:
        agent.shutdown()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
