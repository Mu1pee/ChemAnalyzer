# AI Research Agent — test report, 2026-11-04

## Verified behavior

- Original backend suite before integration: 117 passed.
- Final combined backend suite: 145 passed in 49.87 seconds.
- New research suite: 28 passed. Technical synthetic fixtures are explicitly
  labelled and never presented as scientific models.
- Electron Node tests: 17 passed, including process supervision and URL security.
- Frontend TypeScript project build passed; Vite production build passed.
  Existing warnings remain: 3Dmol eval and large Ketcher/application chunks.
- Manual browser check: Research Lab opens without molecule analysis, displays
  experiment history and both model/baseline metrics, executes a real model
  prediction, and displays experimental status and applicability warnings.
- Real-data CLI cycle on 642 FreeSolv molecules completed, then repeated from
  retained CSV with identical metrics: MAE 1.3207097634, RMSE 1.7042176528,
  R² 0.6928807889. Data/weights remain local, excluded from Git.
- Actual PyInstaller Windows onedir backend built. Frozen integration smoke
  verified health, aspirin formula C9H8O4, import, spawned ML training,
  persisted experimental registry, reloaded prediction and task cancellation.
  Frozen metrics matched Python exactly. No model was approved/activated.

Coverage includes discovery lead honesty, FreeSolv experimental-column mapping,
offline/timeouts, source compatibility and license rejection, SMILES errors,
salts, missing/non-finite labels, duplicates/conflicts, input limits, scaffold
leakage and label-independent deterministic partitioning, small/imbalanced data,
regression and classification training, checksum-checked save/load, explicit
review/approval gates, applicability, forbidden antidote training, cancellation,
worker failure, RAM termination, restart recovery, path traversal, default-off
API and foreign-origin rejection, changed-data schedule authorization, offline
schedule reports, and not reusing old runs for newly approved datasets.

## Reproduction

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -q
node --test electron/tests/backend.test.js electron/tests/security.test.js electron/tests/store.test.js
```

Frontend: from frontend, run `node node_modules/typescript/bin/tsc -b`,
`node scripts/copy-ketcher-assets.mjs`, then `node node_modules/vite/bin/vite.js build`.
These commands were used because npm was not on the shell PATH.

Build: from backend, run the environment's Python with
`-m PyInstaller --noconfirm --distpath ../build/research-backend --workpath ../build/research-pyinstaller chemanalyzer-backend.spec`.
Scientific dependencies were already installed; psutil 7.2.2 was added locally.
Packaging excludes test submodules when collecting scientific packages.
Optional unavailable RDKit drawing/torch and tzdata warnings did not prevent the
tested chemistry/training paths; they are not evidence those optional paths work.

`backend/scripts/validate_research_exe.py` accepts `--exe`, `--csv`,
`--provenance`, `--storage`. Use an empty test storage and a reviewed dataset;
it launches a hidden backend, trains once, predicts, cancels another run, saves
smoke_result.json and terminates the process. Results/logs from this session
are in ignored backend/research_agent and build/research-smoke folders.

## Limits

No full NSIS/portable installer, signing, fresh-machine installation or
distribution release was tested. No automated browser interaction suite was
added; browser verification was manual through UI automation. Time/disk quotas
are implemented and RAM termination is tested; no OS-enforced hard quota claim.
No external scientific validation, literature-retrieval benchmark, general
PubChem/ChEMBL ingestion, direct Parquet import, real ADMET/plant/antidote training
or independently verified user provenance is claimed. Current readiness is the
first testable research cycle, not the entire future autonomous research system.
