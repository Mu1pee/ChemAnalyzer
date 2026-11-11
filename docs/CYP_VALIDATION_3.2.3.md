# ChemAnalyzer 3.2.3 CYP inhibition validation

Checkpoint: 2026-11-11. Five distinct human CYP inhibition classifiers were
trained from experimental TDC/Veith labels and passed the current admission
policy. They remain **experimental and unapproved** in the registry. This is not
clinical drug-interaction, metabolic-substrate or antidote prediction.

## Source and curation

Dataset: Therapeutics Data Commons, Veith CYP inhibition subsets, hosted in
Harvard Dataverse (`doi:10.7910/DVN/21LKWG`). Scientific reference:
Veith et al., Nature Biotechnology 27, 1050–1055 (2009), doi:10.1038/nbt.1581.

The TDC source documents CC BY 4.0; the Dataverse metadata states CC0 1.0.
Attribution and both source records are retained. The adapter downloads text
tables only, follows redirects only to the reviewed Dataverse storage bucket,
checks schema, exact source row counts and binary labels, and saves source
bytes, metadata and SHA256 hashes. Remote source code/pickle is never executed.

Original TDC labels are preserved: Y=1 inhibitor, Y=0 non-inhibitor under the
benchmark's preprocessing. No new concentration cutoff or synthetic outcome is
invented. These are not relabelled IC50 values. Models and experimental context
remain separate for all five isoforms. Multi-fragment, invalid or oversized
structures are excluded; canonical duplicates and contradictory measurements
are checked by preparation. Per-row issues remain in each run's preparation.json.

| Isoform | Dataverse file ID | Source rows | Accepted molecules | Train / validation / test |
| --- | ---: | ---: | ---: | --- |
| CYP1A2 | 4259573 | 12,579 | 12,037 | 7,704 / 1,926 / 2,407 |
| CYP2C9 | 4259577 | 12,092 | 11,554 | 7,394 / 1,849 / 2,311 |
| CYP2C19 | 4259576 | 12,665 | 12,144 | 7,772 / 1,943 / 2,429 |
| CYP2D6 | 4259580 | 13,130 | 12,581 | 8,052 / 2,013 / 2,516 |
| CYP3A4 | 4259582 | 12,328 | 11,779 | 7,538 / 1,885 / 2,356 |

The TDC code metadata contains an outdated CYP2C19 count in one location; the
actual downloaded table and TDC dataset page support 12,665. This adapter checks
the reviewed real row count rather than silently truncating the data.

## Fixed training procedure and test evidence

Seed 42, Morgan 1024 bits with chirality plus six RDKit descriptors. Whole Murcko
scaffold groups are kept together; acyclic structures share a group. Group sizes
alone determine the split. Each partition contains distinct scaffolds.

Random Forest, Logistic Regression and Gradient Boosting each undergo 3-fold
group CV within train. Validation filters classification candidates to balanced
accuracy > 0.60 and ROC-AUC >= 0.70; validation PR-AUC selects among eligible
candidates. The held-out test is evaluated afterwards, with decision threshold
0.5. There was one run per isoform, with no seed search or test-based retuning.
Random Forest was selected for all five. Dummy prior baselines have balanced
accuracy 0.50; all models also exceed their own test PR-AUC baseline.

| Isoform | Test balanced accuracy | ROC-AUC | PR-AUC | Test scaffold groups | 95% group bootstrap interval for balanced accuracy |
| --- | ---: | ---: | ---: | ---: | --- |
| CYP1A2 | **78.62%** | 0.8728 | 0.8422 | 2,153 | 76.82–80.38% |
| CYP2C9 | **75.53%** | 0.8334 | 0.7485 | 2,053 | 73.80–77.27% |
| CYP2C19 | **75.32%** | 0.8321 | 0.8444 | 2,161 | 73.57–77.13% |
| CYP2D6 | **72.76%** | 0.8392 | 0.6234 | 2,228 | 70.23–75.17% |
| CYP3A4 | **74.67%** | 0.8343 | 0.8091 | 2,120 | 72.73–76.50% |

Intervals use 1,000 percentile-bootstrap resamples of entire held-out scaffold
groups, seed 20261111, after evaluation. They were not used to select or retune
models. They condition on the fixed trained model and this benchmark; they do
not cover experimental systematic errors, training-set variation or future data
shift. They are not a substitute for independent external validation.

Important class-specific limitation: CYP2D6 inhibitor recall is **53.80%** and
positive precision **60.14%**, despite its higher balanced accuracy. A good mean
score does not imply equal reliability for both classes. Recall and precision
are shown in the CYP screen alongside balanced accuracy and ranking metrics.
Probabilities have not undergone separate calibration.

## Artifacts and application behavior

| Isoform | Registry model ID |
| --- | --- |
| CYP1A2 | d5f0453c32b444a496e7f069416736c6 |
| CYP2C9 | e44bcf5d855b4eefbe594f073f9507bd |
| CYP2C19 | 2d72179e73594e26a6ee8f4f4bcfcaff |
| CYP2D6 | d88b9d30b6914d4b9409a73faf99c55d |
| CYP3A4 | 6fd7449b0dc44577ac97645de8093d13 |

The CYP endpoint checks exact isoform task/context, current quality policy and
artifact checksum. It never fills a missing isoform from another model. Values
are withheld outside the heuristic Morgan/descriptor applicability domain. The
selected artifact is the latest qualified model, preferring an approved model;
prediction-time selection never chooses the highest test score. Existing user
registry records are not overwritten by the bundled UUID-addressed seed.

Research Lab provides reviewed task presets and source import for each isoform.
Reproduction from a fresh checkout/environment, from the backend directory:

    .\.venv\Scripts\python.exe -m training.train_cyp --isoform all --output-dir <fresh-directory>

Reproduction is an experiment, not a new independent scientific confirmation.
Checksums, source versions, splits, hyperparameters, all metrics and dependency
versions are included in the data/model archive. Source availability may change.

Software checks: 182 backend tests passed after CYP integration, TypeScript and
the production frontend build passed. Windows runtime and installer checks are
reported separately in windows-verification.json for the release.

## Remaining goal scope

COX-2 and FreeSolv remain separate models with their previously documented
limitations. Antidote rescue, Arabidopsis primary-root regulation, antibacterial,
antiviral, cytotoxicity, other toxicity/metabolism and planned gene/text models
are not established by this CYP work. The overall goal for every predictive
system is still incomplete. No unsupported endpoint is presented as trained.

Sources:
- https://tdcommons.ai/single_pred_tasks/adme/
- https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/21LKWG
- https://pubmed.ncbi.nlm.nih.gov/19855396/
