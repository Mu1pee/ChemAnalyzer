"""Reproduce the fixed HIV, HepG2 and human HLM experiments in a fresh registry.

From backend: python -m training.train_screening --assay all --output-dir <fresh-directory>
The held-out test is never used to select an algorithm, hyperparameter or threshold.
"""
import argparse
import json
import multiprocessing
from pathlib import Path
import time

from app.ai_research_agent.config import TaskConfig
from app.ai_research_agent.model_registry import Registry
from app.ai_research_agent.orchestrator import ResearchAgent
from app.chemistry.screening_activity import TASKS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assay", choices=["all", *TASKS], default="all")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("Use a fresh directory; previous datasets, runs and test results must be preserved")
    agent = ResearchAgent(args.output_dir)
    results = []
    try:
        for key in (TASKS if args.assay == "all" else [args.assay]):
            task = agent.create(TaskConfig(**TASKS[key]()))
            imported = getattr(agent, "import_ncats_hlm" if key == "hlm" else "import_tdc_" + key)(task["id"])
            run = agent.start(task["id"])
            print(json.dumps(dict(assay=key, task_id=task["id"], run_id=run["id"], source_rows=imported["measurements"])), flush=True)
            previous = None
            while True:
                state = agent.run(run["id"])
                if state["stage"] != previous:
                    print(json.dumps(dict(assay=key, stage=state["stage"], status=state["status"])), flush=True)
                    previous = state["stage"]
                if state["status"] not in ("queued", "running"):
                    break
                time.sleep(1)
            if state["status"] != "completed":
                print(json.dumps(state), flush=True)
                return 1
            meta = Registry(args.output_dir).metadata(state["model_id"])
            results.append(meta)
            print(json.dumps(dict(assay=key, model_id=meta["id"], quality=meta["quality"], test=meta["evaluation"]["test"])), flush=True)
        (args.output_dir / "training-results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        return 0 if all(model["quality"]["passed"] for model in results) else 1
    finally:
        agent.shutdown()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
