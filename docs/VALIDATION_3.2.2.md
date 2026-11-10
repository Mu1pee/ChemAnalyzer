# ChemAnalyzer 3.2.2 — research validation

Date: 2026-11-10. This is an experimental application release. The goal of
validated predictive coverage for every catalog system is **not complete**.
Untrained endpoints remain explicitly unavailable.

## Models

**Human COX-2 IC50** retains artifact `CHEMBL230-panel-3.2.1`, trained from
ChEMBL 37, 2,776 unique standardized compounds (1,449 active/1,327 inactive).
Active means pChEMBL >= 6 (IC50 <= 1 micromolar). Internal 5-fold scaffold CV:
balanced accuracy **0.7081**, ROC-AUC 0.7867, PR-AUC 0.8007, MCC 0.4160;
Y-randomization AUC 0.4913. The new runtime policy admits the existing artifact
without re-labelling its evidence as an independent test. Assay protocols vary;
there is no independent external, prospective or assay-held-out validation.

**Hydration free energy** was retrained from actual FreeSolv experimental data
after correcting partition scaffold support. It is a distinct endpoint from
bioactivity, antidote activity and plant growth. Source revision:
`6c7d19b4b565537365ffd22006aa2cd4643200c6`; CC BY 4.0.

- Task: `8d2ed704feae4810b2a0bb674266732f`.
- Run: `78c98dac694647768ef87f0ab2566381`.
- Artifact: `35f7187c7a124876be58a08e1761a2ce`, experimental/unapproved.
- Input checksum: `3702a624c634675ebc5d7b005c3a99009f527b1ea45e800890e109dc023ce00f`.
- 642 unique molecules; 398 train / 90 validation / 154 test.
- 30 / 30 / 3 scaffold groups in those partitions, without overlap.
- Random Forest, Ridge and Gradient Boosting candidates; train-only 3-fold group
  CV and validation selected Gradient Boosting. Seed 42; test evaluated afterwards.
- Test MAE **1.222015 kcal/mol**, RMSE **1.629124 kcal/mol**, R² **0.729009**.
- Baseline MAE **2.915622 kcal/mol**. R² is not percent accuracy.

**Important limitation:** 152 of the 154 test molecules have the benzene scaffold;
the other two scaffolds have one molecule each. Reserving whole groups improves
the minimum support but does not make this a diverse external validation set.
Broad chemical generalization remains unproven. This benchmark has previously
been examined; this correction is not a new independent scientific replication.
Source experimental conditions are not completely uniform. The applicability
rule is heuristic and does not measure uncertainty. Model approval remains a
separate documented step.

## Admission behavior

Classification requires balanced accuracy strictly > 0.60. Existing stricter
target-QSAR and specialized thresholds remain enforced. Missing/non-finite
metrics and incomplete OOF coverage fail. Research Agent additionally requires
documented held-out support, baseline improvement and test exclusion from model
selection. Regression admission requires R² > 0.60 and MAE below baseline.

Quality is recomputed at review, activation and prediction. Older artifact files
are preserved but cannot bypass current admission rules. Numerical predictions
outside the heuristic applicability domain are hidden. The catalog and model
screen distinguish probability, similarity, CV quality and regression metrics.

No experimental tables have yet been integrated for acetaminophen rescue or
Arabidopsis primary-root length/control; both stay `not_trained`. Other missing
catalog models remain described in MODEL_QUALITY_POLICY.md. No artificial labels
or proprietary PASS/Way2Drug predictions are used.

## ChEMBL correction

Packaged verification identified an additional root cause: the build runtime's
SSLContext loads `codex-rejected-cas.pem` alongside the frozen ssl module. That
public CA policy resource was missing, causing FileNotFoundError before HTTPS
initialization. The PyInstaller spec now includes the resource where applicable.
A minimal frozen HTTPS probe reproduced the failure and verified the correction.
The backend supports `--check-network` for TLS/ChEMBL status diagnostics.

Exact and similarity requests run concurrently, transient requests can retry,
DNS/network waiting is bounded by a shared 55-second budget, partial results are
marked and logged, and successful responses are timestamped and cached locally.
Stale cached data may be shown during outages with their original date. TLS is
verified. Live source check: aspirin CHEMBL25, 15 targets and 8 analogs,
30.12 seconds live / 0.30 seconds cache, no missing sections. Results vary with
external service availability. Packaged Windows verification is recorded in
`windows-verification.json` accompanying the release.

## Software checks

166 backend tests passed before final registry applicability refinement; the
38 relevant Research Agent/policy tests passed again afterwards. Frontend
TypeScript/Vite production build and all 18 Electron tests passed. Packaged
runtime and visual checks are recorded separately. These software tests do not
establish predictive performance for untrained endpoints.

The Windows executables are unsigned because no signing certificate is configured.
The build preserves the signing integration points. Clean-machine installation
and every possible Windows environment are not certified by these checks.

Sources: https://www.ebi.ac.uk/chembl/ and https://github.com/MobleyLab/FreeSolv
