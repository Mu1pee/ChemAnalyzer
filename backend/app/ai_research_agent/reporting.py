from .security import write_json


def write_report(run, meta):
    write_json(run / "result.json", meta)
    evaluation = meta["evaluation"]
    (run / "report.md").write_text(
        f"# Research experiment {meta['id']}\n\nStatus: experimental. Not scientifically validated.\n\n"
        f"Endpoint: {meta['task']['endpoint']} ({meta['task']['units']}).\n\n"
        f"Selected algorithm: {evaluation['selected']}.\n\n"
        f"Held-out metrics: {evaluation['test']}\n\nBaseline: {evaluation['baseline_test']}\n\n"
        "Candidate selection used training CV and validation only. Test was held out. "
        "Scaffold splitting cannot replace prospective external validation. "
        "Acyclic structures share a group; data are small and curated-source conditions may differ.\n",
        encoding="utf-8")
