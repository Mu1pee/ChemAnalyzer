# COX-2 research model

Training date: 2026-11-02. Target: ChEMBL CHEMBL230, Prostaglandin G/H synthase 2 (COX-2).

The existing ChEMBL downloader retrieved 3000 experimental activity records. Standardization and median aggregation produced 1989 molecules (1225 active, 764 inactive), with 481 scaffold groups. Activity threshold: pChEMBL >= 6.0. Existing Random Forest training uses Morgan fingerprints and scaffold cross-validation.

Observed cross-validation metrics: ROC-AUC 0.7739; PR-AUC 0.8242; balanced accuracy 0.6901; MCC 0.3969. Label-randomization ROC-AUC: 0.5017. The model passed the existing project quality gates.

These are internal cross-validation results, not independent external validation. The downloader mixes IC50, Ki, Kd and EC50 and does not yet preserve complete assay/species provenance. The first 3000 records are a bounded pilot dataset, not a representative full-target benchmark. This model must remain exploratory and is not evidence of clinical, antidotal or agricultural efficacy.

Local artifacts: backend/models/CHEMBL230.joblib, manifest.json, training_report.json. Training data and model files are excluded from Git. ChEMBL attribution/licensing notes remain in LICENSE_NOTICES.md. No antidote or plant-growth model was trained: suitable context-specific experimental datasets are absent.

Reproduce from backend using its Python environment:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m training.fetch_data --targets CHEMBL230 --max-records 3000
.\.venv\Scripts\python.exe -X utf8 -m training.train --targets CHEMBL230
```

Before broader scientific use: preserve assay identifiers and source version, stratify compatible endpoints/species, audit contradictory measurements, and evaluate a locked external test set.

# AI Research Agent: FreeSolv experiment, 2026-11-04

Status: **experimental**, no external scientific validation and no activation.
This section supplements the existing COX-2 report above.

Dataset: 642 experimental FreeSolv hydration free energies; no calculated GAFF
labels. Normalized CSV SHA256:
`a489cf3153d616abb7072e07ad4470b9ac4e96f3ff944d192ae23504a7ec3575`.
Pinned source commit: `6c7d19b4b565537365ffd22006aa2cd4643200c6`.
Seed 42; train 399, validation 91, test 152. Scaffold groups never overlap;
acyclic molecules share a single group. Three-fold training-only CV and a small
parameter grid per algorithm; validation selects Gradient Boosting, max_depth=3,
80 estimators. Final exact parameters are recorded in local metadata.

| Held-out measure | Selected model | Dummy mean baseline |
|---|---:|---:|
| MAE, kcal/mol | 1.3207 | 2.9055 |
| RMSE, kcal/mol | 1.7042 | 3.4012 |
| R² | 0.6929 | -0.2233 |

The initial development split used group counts and produced 122/13/507;
it was replaced with size-balanced scaffold allocation before the reported
experiment. Both development artifacts are retained locally as experimental.
The split algorithm changed for size balance, not based on prediction scores.
These development metrics are not an untouched prospective benchmark claim.
Source-specific conditions/uncertainties are heterogeneous; validation is small.
No confidence interval, prospective experiment or external test has been run.
No new plant, antidote or ADMET model has been trained in this increment.

Dependencies used: Python 3.12.14, RDKit 2026.9.1, sklearn 1.9.1, numpy 2.5.4,
scipy 1.18.1, joblib 1.6.0. Registry status remains experimental unless a user
records a documented review and separately confirms activation.
