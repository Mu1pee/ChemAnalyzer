# Data templates for ПК «Антидот-Прогноз»

Files in this folder are **empty templates**, not training data:

- `antidote.csv` — antidote-related assay data.
- `growth_regulating.csv` — plant growth-regulator assay data.

Add rows only from a documented experimental source. Do not combine different endpoints, toxicants, species, assay conditions or activity definitions into the same `endpoint` + `context` group.

Required columns:

| Column | Meaning |
|---|---|
| `smiles` | Compound structure in SMILES format |
| `label` | `1` = active, `0` = inactive according to the cited assay definition |
| `endpoint` | Short stable endpoint identifier, e.g. an assay/property name |
| `context` | Exact context: target/toxicant, plant species, assay protocol, concentration regime, etc. |
| `source` | Publication, curated database or dataset name |
| `source_id` | DOI, URL, accession or other source locator |

Every label must be traceable to a source. `0` must mean experimentally inactive under the same endpoint/context, not merely “no result found”. Do not treat missing measurements as inactive.

Train from the `backend` folder. For models that the installed desktop app can load, write them to its user-data directory:

```powershell
$modelsDir = Join-Path $env:APPDATA "ChemAnalyzer\models\specialized_activity"
python -m training.train_specialized --models-dir $modelsDir
```

Or train only one direction (run these commands after defining `$modelsDir` as above):

```powershell
python -m training.train_specialized --domain antidote --models-dir $modelsDir
python -m training.train_specialized --domain growth_regulating --models-dir $modelsDir
```

After training, close and reopen ChemAnalyzer so the backend reloads `manifest.json`. The default quality gates require at least 30 unique active and 30 unique inactive compounds, at least five Murcko scaffold groups in each class, scaffold-based cross-validation, ROC-AUC >= 0.70, balanced accuracy >= 0.60 and MCC >= 0.10. A model that does not pass is rejected and recorded in `training_report.json`.

These thresholds are safeguards, not proof that a model is suitable for real-world decisions. Review leakage, endpoint homogeneity, applicability domain and external validation before interpreting predictions. The app does not provide medical, toxicological or agricultural advice.
