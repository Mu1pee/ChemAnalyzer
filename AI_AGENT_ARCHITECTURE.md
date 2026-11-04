# AI Research Agent — first testable increment

2026-11-04. Separate package `backend/app/ai_research_agent`; no agent framework,
LLM labels, paid APIs, remote uploads or changes to legacy QSAR manifests.

## Boundaries

`config` defines endpoint/context-specific tasks and provenance. `data_discovery`
has one reviewed download adapter (FreeSolv) and explicit source leads.
`data_validation` checks the contract; `molecular_features` records structure
transformations and every exclusion. `training/evaluation` isolate scaffolds,
fit train-only preprocessing/CV, select on validation and evaluate test last.
`applicability_domain` combines Morgan similarity with training descriptor ranges.
`model_registry` stores immutable model IDs, hashes and review/approval records.
`orchestrator` snapshots inputs, spawns one bounded worker and supervises it.
`experiment_tracking/reporting` persist stages, errors and research reports.
`scheduler` implements an explicit allow-list with dataset-hash authorization.
`api/cli` expose the same pipeline. React ResearchLabTab is independent of the
currently drawn molecule and uses asynchronous requests/polling.

## Persistence and recovery

Storage: `<CHEMANALYZER_DATA_DIR>/research_agent`, or `backend/research_agent` in
development. `tasks/<id>/<version>/` contains CSV/provenance/evidence;
`runs/<id>/` holds immutable inputs, preparation.json, features.npz, state.json,
result.json and report.md. FreeSolv source bytes and license remain in task data.
`models/<id>/` holds agent-generated joblib and metadata. JSON replacement is atomic.
Interrupted runs are marked on restart; start a new run explicitly to recover.
Cancellation terminates the worker, preserves evidence, and prevents publication.
The supervisor publishes a model only after successful process exit and quota checks.

One worker, estimator n_jobs=1, native thread limit 1, no paid requests. Default
limits: 600 seconds, 2048 MiB RSS, 512 MiB per run, 10,000 rows; imports 8 MB,
downloads 4 MB per resource. RAM/disk sampled every 250 ms: these are supervised
limits, not Windows Job Object hard quotas. Historical storage is retained and
not subject to a global retention quota. Users manage their own retained evidence.

## Modes and model lifecycle

Manual: separate import/prepare/train actions. Assisted: each visible next-stage
button is an explicit action; no LLM planning engine is implied. Scheduled:
persist a disabled-by-default policy, explicitly enable allowed checks/training,
and keep the backend running. Checks report new FreeSolv data but never import or
approve it automatically. Training requires the exact explicitly approved dataset
SHA256; changed data are skipped. Failed jobs may retry at the next interval.
No model review, approval or production release is scheduled.

experimental -> validated requires a named reviewer and documented evidence,
plus a baseline pass; this records the reviewer's declaration, not verification
by an external authority. validated -> approved requires explicit activation.
archived models cannot predict. Active pointers are endpoint/context-specific;
`/api/research/active/predict` accepts approved models only. Research preview by
model ID exposes its actual status. No existing predictor is silently replaced.

## Current limits / next stages

- CSV ingestion is supported. Parquet ingestion is a follow-up; no pyarrow is
  bundled. Curators can export a plain CSV while preserving source provenance.
- PubChem/ChEMBL/Zenodo are leads, not general automatic dataset extractors.
- Source licensing and metadata syntax are checked; local declarations require
  independent human verification. No generic scientific comparability oracle.
- ADMET and growth use separate task configurations and require curated
  experimental CSVs. Arabidopsis primary-root endpoint is enforced. No trained
  plant/ADMET model is claimed in this increment.
- Antidote tasks support import/preparation/catalog reports only; training is
  blocked. No universal antidote predictor or treatment recommendations.
- No external/prospective validation, prediction intervals, probability
  calibration study, nested outer CV or literature-mining LLM integration yet.
- Scheduler policies are API-controlled; a dedicated scheduling UI is future work.
- No full NSIS/portable release or signing is performed as part of this increment.

Continue by adding reviewed assay-specific adapters, schema-driven experimental
context fields, Parquet import, independent dataset validation and UI end-to-end
automation. Preserve the existing tests and require approval for activation.
