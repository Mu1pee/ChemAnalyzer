# ChemAnalyzer 3.2.4: HIV and HepG2 screening models

Checkpoint: 2026-11-11. Two separate classifiers pass the current admission
policy. Both remain **experimental and unapproved**. All outcomes below concern
the named benchmark assay, not treatment efficacy, general toxicity or antidote activity.

## Data, rights and exclusions

HIV: TDC file 4259593, NCI DTP AIDS Antiviral Screen / MoleculeNet.
Original confirmed active (CA) and moderately active (CM) are positive;
confirmed inactive (CI) is negative. There is no invented EC50 threshold.
All 41,127 rows were cross-checked against DeepChem's original HIV.csv:
101 different SMILES strings represented equivalent canonical structures;
five conflicting/invalid structure pairs were excluded before preparation.
All binary labels agreed with the original category mapping. The excluded
source IDs are Drug 21124, 21127, 21128, 21129 and 35728. Structure preparation
excluded a further 3,095 multi-fragment, invalid or oversized entries, leaving
38,027 molecules. No synthetic or inferred outcomes were added.

HepG2: TDC ToxCast file 4259613, only **APR_HepG2_CellLoss_24h_dn**.
This is a 24-hour proliferation-decrease assay in human liver HepG2 cells.
It is not evidence of confirmed cell death or clinical liver injury, anticancer
efficacy or protection from paracetamol. Of 8,576 source records, 7,542 have no
measurement for this endpoint and were excluded, never labelled inactive.
The measured subset has 734 negatives and 300 positives. A further 110
structure errors were excluded, leaving 924 molecules. Other assays and 72-hour
exposures were not pooled. This is the fixed older TDC benchmark, not a claim
to use the latest EPA invitrodb release.

TDC explicitly documents CC BY 4.0 for both datasets; Dataverse metadata states
CC0 1.0. We retain both statements and distribute the derived data and model
weights under CC BY 4.0 with attribution. Original ChemAnalyzer code licensing
is unchanged. Source tables, metadata, primary-reference bytes, hashes and
per-record preparation issues accompany the experiments.

| Source | Raw SHA256 |
| --- | --- |
| HIV TDC table | c03bf6c0c6bff27df5443c7a34bffc9f2befca3cf300b483b0ff6de3c07b876c |
| HepG2 ToxCast table | 14c392ede82352907e42db35291d8ba998db3b10f074d9497124e44d0329ea5f |

Prepared dataset CSV SHA256: HIV
`8ed642244aed96dab4d678a531c510aa5f6545c010fc41f2133cfb9cb52acebb`;
HepG2 `4a15307922b5c2011e2152917c254112339f561b0efe225501c8257480b4e35a`.

## Training and held-out evaluation

Fixed seed 42. Whole Murcko scaffold groups are disjoint between train,
validation and test; acyclic molecules share one group. Features are Morgan
radius 2, 1,024 bits with chirality and six RDKit descriptors. Three-fold
training-only grouped CV tunes predeclared candidates. Validation quality
and PR-AUC select the algorithm. The decision threshold stays 0.5. The held-out
test is used after selection only. Random Forest was selected for both tasks.

| Endpoint | Train / validation / test | Positive / negative test | Test scaffolds |
| --- | --- | --- | ---: |
| HIV | 24,337 / 6,084 / 7,606 | 237 / 7,369 | 5,706 |
| HepG2, 24 h | 591 / 148 / 185 | 62 / 123 | 123 |

| Endpoint | Balanced accuracy | ROC-AUC | PR-AUC | Recall | Positive predictive value |
| --- | ---: | ---: | ---: | ---: | ---: |
| HIV | 65.50% | 0.7614 | 0.3264 | **32.07%** | 49.03% |
| HepG2, 24 h | 71.25% | 0.7704 | 0.6341 | 72.58% | 54.88% |

The rare HIV positive class makes raw accuracy misleading. The **low HIV recall**
is displayed prominently: a negative prediction cannot rule out activity.
Balanced accuracy exceeding 60% does not imply that both class recalls or the
positive predictive value exceed 60%. Neither probability output was separately
calibrated. Heuristic applicability checks hide probabilities outside the domain.

Whole-test-scaffold percentile bootstrap, 1,000 resamples, fixed seed 20261111:
95% balanced-accuracy intervals are HIV **61.75–69.15%**, HepG2 **61.71–78.85%**.
These intervals are conditional on the fixed model and benchmark; they do not
include systematic assay error, training variability or prospective data shift.
No external or prospective validation has been completed.

Model IDs: HIV `5655f098722e4602986f6185dfc46720`, run
`ae7e1941c12d43cb9f60fe7dddf37ac4`; HepG2
`3cb35799ee3e4e81971c9524ba5089b7`, run `ee0262def2ee417f91865fd044cdcc37`.

## Reproduction and remaining scope

From backend, with repository dependencies installed:
`python -m training.train_screening --assay all --output-dir <fresh-directory>`.
Existing experiment folders are rejected rather than overwritten. The Research
Lab also supplies exact task presets and reviewed source-import buttons.
Published runs, raw inputs, trained artifacts and split indices are retained in
the release data archive. Do not search seeds/thresholds using these test results.

This release retains the five CYP classifiers, COX-2 QSAR and FreeSolv model.
General antiviral/cytotoxicity, antibacterial, metabolic stability, APAP rescue,
Arabidopsis primary-root, gene-expression and text-extraction systems are not
validated by these two endpoints. The goal of qualifying every system remains
unfinished; the endpoint audit explains the missing APAP/root data.

Software checks: 205 backend tests passed; following the additional ChEMBL
timeout change, all eight affected transport tests passed. Eighteen Electron
tests and the TypeScript/production build passed. The final unpacked Windows
application started, loaded eight research models plus COX-2, produced separate
screening predictions, hid outside-domain probabilities and displayed the low
HIV-recall warning without renderer errors. The frozen backend reimported both
real datasets with CSV SHA256 exactly matching training inputs. During that
final probe, ChEMBL itself returned HTTP 500 for exact and similarity requests;
the failure was preserved rather than labelled as successful data retrieval.
Clean-machine Setup installation has not been tested.

Primary sources:

- https://tdcommons.ai/single_pred_tasks/hts/
- https://wiki.nci.nih.gov/spaces/NCIDTPdata/pages/158204006/AIDS+Antiviral+Screen+Data
- https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/HIV.csv
- https://doi.org/10.1039/C7SC02664A
- https://tdcommons.ai/single_pred_tasks/tox/
- https://doi.org/10.1021/acs.chemrestox.6b00135
- https://pmc.ncbi.nlm.nih.gov/articles/PMC6280881/
- https://edg.epa.gov/EPA_Data_License.html
- https://doi.org/10.7910/DVN/21LKWG
