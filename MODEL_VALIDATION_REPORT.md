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
