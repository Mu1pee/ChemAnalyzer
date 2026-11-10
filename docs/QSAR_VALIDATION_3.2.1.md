# ChemAnalyzer 3.2.1 - COX-2 IC50 research model

## Dataset and provenance

Training was performed on 2026-11-10 using ChEMBL 37 API snapshots. Target: CHEMBL230, human Prostaglandin G/H synthase 2 (COX-2). Only binding assays with target confidence 9 and exact IC50 values in nM are eligible. Ki, Kd, EC50, other species, validity flags and potential duplicate records are excluded. No synthetic activity labels were introduced.

The initial single-assay candidate CHEMBL763870 was excluded because its target confidence is 8. No confidence-9 single assay in the downloaded panel supplied 30 examples in both classes before curation. The resulting panel uses multiple assays for the same human target and IC50 endpoint; protocol differences remain a scientific limitation.

6027 exact IC50 activity records were retrieved, then filtered against the confidence-9 assay catalog. Standardized molecular duplicates crossing the activity threshold were excluded; compatible repeats were reduced by median pChEMBL. The final dataset has 2776 unique molecules: 1449 active and 1327 inactive. Activity is defined in advance as pChEMBL >= 6.0 (IC50 <= 1 micromolar). Each retained compound preserves activity IDs and assay IDs.

The release includes source URLs, source-document references, raw-response SHA256 checksums, curated rows and source snapshots in a separate data archive. ChEMBL data, the curated dataset and this supplied research model are distributed under CC BY-SA 3.0; original ChemAnalyzer application code retains its existing Showcase conditions. Attribution: ChEMBL contributors, EMBL-EBI. License: https://creativecommons.org/licenses/by-sa/3.0/ .

## Training and evaluation

Morgan fingerprints, Random Forest and sigmoid probability calibration follow the existing QSAR pipeline. Evaluation uses 5-fold StratifiedGroupKFold by chemical scaffold; all 2776 molecules received out-of-fold predictions. Seed: 42. No threshold or seed was tuned after evaluation.

| Metric | Result |
| --- | ---: |
| Scaffold CV ROC-AUC | 0.7867 |
| Scaffold CV PR-AUC | 0.8007 |
| Balanced accuracy | 0.7081 |
| MCC | 0.4160 |
| Label-randomization ROC-AUC | 0.4913 |

The existing ROC-AUC >= 0.75, MCC >= 0.25 and minimum-class-size gates passed. The final model was fitted to all curated data after this evaluation. Its predictions must not be reported as independent test results on training compounds.

## Limits

This is an experimental research classifier. There is no independent external, prospective, clinical or toxicological validation. Assay protocols differ, and no assay-held-out validation was performed. Scaffold CV estimates transfer between chemical groups, not necessarily between assay protocols. The calibration subfolds follow the existing training pipeline. The similarity-based applicability domain is a heuristic, not a probability calibration guarantee.

The model addresses COX-2 IC50, not general pharmacological efficacy, toxicity, antidotal activity or plant growth regulation.

## App integration and reproduction

Bundled model ID: CHEMBL230-panel-3.2.1. The application reads its checksum-verified bundle from packaged qsar-models resources in addition to existing local models. Existing user model files are not replaced.

From backend:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m training.train_assay --target CHEMBL230 --assay panel --output-dir <fresh-output-directory>
```

For bitwise dataset reproduction use the published raw snapshots with --source-dir. API database revisions can change over time; a fresh live download is not guaranteed to reproduce this exact panel.

## Build and verify

All 150 Python tests, 18 Electron tests and the TypeScript/Vite production build passed. The Windows backend is packaged with PyInstaller from Python 3.12. The release uses electron-builder.qsar.cjs; set CHEMANALYZER_QSAR_RELEASE_DIR to the reviewed manifest/model directory and CHEMANALYZER_RESEARCH_SEED_DIR to the existing research seed before building. Neither datasets nor model binaries are committed to Git; reproducibility artifacts accompany the release.

The Windows files are unsigned. Known moderate npm audit findings in third-party dependencies remain documented; no incompatible automatic downgrade was applied. A clean-machine installation acceptance test has not been performed.
