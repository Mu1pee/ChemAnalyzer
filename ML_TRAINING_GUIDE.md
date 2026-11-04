# Endpoint-specific research models

## AI Research Agent first cycle (2026-11-04)

The independent `app.ai_research_agent` pipeline is now available; see
AI_AGENT_USER_GUIDE.md for commands. It does not overwrite this legacy trainer's
artifacts. FreeSolv regression compares Random Forest, standardized Ridge and
Gradient Boosting; binary tasks compare RF, standardized Logistic Regression and
Gradient Boosting. Seeds are fixed, estimators/native pools use one thread.
GridSearchCV has three scaffold folds on training only. Validation selects the
algorithm; held-out test evaluates only the selected candidate and dummy baseline.

Largest scaffold groups are allocated first against 64/16/20 molecule-count
targets using seeded ties, without labels. All acyclic molecules share one group;
exact proportions are therefore not guaranteed. Each partition needs >=10
molecules; dataset needs >=60 molecules and >=10 groups. Classification additionally
requires binary 0/1 labels, >=30 compounds per class, >=3 per class in holdouts
and both classes in each CV fold. These are technical minimums, not scientific
sufficiency. Regression requires varying labels. Fold scores and all parameters
are recorded. R², MAE/RMSE or classification ROC/PR-AUC, F1, precision/recall and
balanced accuracy are saved with dependency versions and split indices.

Source/prepared CSV, features, exclusions, transformations, model checksum and
training-support applicability domain are preserved. Test scores must not be
used to tune repeated releases. Passing baseline does not auto-validate or approve.
Independent external/prospective assessment remains required. The current domain
rule (Tanimoto >=0.35 plus descriptor ranges) is heuristic and uncalibrated.
No universal antidote training is allowed in the new agent.

## Candidate algorithms (2026-11-04)

The existing trainer now accepts --algorithm random_forest, logistic_regression or gradient_boosting. Each uses the same scaffold splits and quality gates. Use a separate --models-dir for each candidate: model filenames identify endpoint/context, so running different algorithms into one directory replaces that endpoint's model. Model metadata records the algorithm. Candidate evaluation is not a validated model release; selecting the best CV score requires subsequent independent validation.

Additional source leads: https://pmc.ncbi.nlm.nih.gov/articles/PMC10793101/ screens TFEB agonists, not direct APAP rescue for every screened compound. https://academic.oup.com/jxb/article/59/10/2757/436620 reports 13 root-inhibiting hits, below the existing 30-positive gate. Rodriguez-Furlan et al. (2016), High throughput selection of novel plant growth regulators, is another lead requiring primary-root endpoint and data-license verification. None has been converted into training labels.

Scope agreed 2026-11-03: acetaminophen injury rescue and Arabidopsis thaliana primary-root growth relative to a matched control. Both models remain not trained. Profiles in backend/training/specialized_data/research_profiles.json describe curation requirements; they are metadata, not an automatic data-quality validator.

## Data acceptance

Record the source URL/DOI, explicit reuse license, assay identifier, structure identifier, experimental measurements, units, dose, exposure duration, organism and protocol. Keep source records unchanged in ignored local training/data folders. Record download dates and SHA256 checksums. Public availability alone is not a reusable-data license.

Do not turn docking scores, gene perturbations or APAP-only toxicity data into antidote labels. Keep each toxicant and experimental context separate. Do not label compounds without measurements as inactive.

For Arabidopsis retain the continuous root-length ratio and direction (inhibition versus promotion). Existing train_specialized is a binary classifier, not a validated regression pipeline. Use it only when a source provides a defensible prespecified binary assay rule, in separate promotion/inhibition tasks; do not invent a threshold to make a trainable dataset. A continuous model requires an independently tested regression extension after suitable data are curated.

The CSV contract is documented in backend/training/specialized_data/README.md. Each endpoint/context is isolated, molecular structures standardized, conflicting duplicate labels removed, and evaluation split by scaffolds. Existing gates require at least 30 compounds per class and five scaffolds per class. Passing them does not establish external validity.

## Source screening (initial, not exhaustive)

- https://pmc.ncbi.nlm.nih.gov/articles/PMC10821416/ : APAP study with two experimentally selected candidates from a docking pool of 40. The pool cannot be treated as 40 experimentally measured rescue labels. Reuse license and complete assay-level supplementary data not verified in this session; not imported.
- https://pmc.ncbi.nlm.nih.gov/articles/PMC5063792/ : GSE74000 transcriptomics of APAP injury, not a compound-rescue classification dataset. Not imported for antidote training.
- https://www.nature.com/articles/s41598-018-34749-1 : screen of 390 iminosugar analogues against Arabidopsis and Tef. Promising root-growth source; full structure-to-measurement mapping, negative results, assay partitioning and reuse rights still require supplementary-material verification. Article retrieval encountered access challenges; no bypass attempted and no training labels inferred.
- https://pmc.ncbi.nlm.nih.gov/articles/PMC6534974/ : beta-cyclocitral root-growth study, published under the PNAS license. Open viewing is not confirmation of unrestricted dataset reuse; source not imported.

Follow-up verification of the Scientific Reports publisher page confirms CC BY 4.0 for the article (third-party exceptions must still be checked). The article reports only five hits above its prespecified 50% inhibition threshold at 10 micromolar; one hit appears as a duplicate. This is below the pipeline minimum of 30 unique positive compounds, irrespective of the nominal 390-library size. Therefore it cannot support an accepted standalone classifier under current gates. No supplementary measurements have been imported or fabricated.

No source above has yet passed the complete license/data/context audit. Empty template training was tested: zero accepted models and two rejected tasks. Do not lower quality gates to produce a model.

## Commands (from backend)

```powershell
.\.venv\Scripts\python.exe -X utf8 -m training.train_specialized --domain antidote --models-dir "$env:APPDATA\chemanalyzer\models\specialized_activity"
.\.venv\Scripts\python.exe -X utf8 -m training.train_specialized --domain growth_regulating --models-dir "$env:APPDATA\chemanalyzer\models\specialized_activity"
```

Run only after curating eligible rows. Preserve different endpoint/context groups; inspect training_report.json and held-out validation before enabling predictions.
