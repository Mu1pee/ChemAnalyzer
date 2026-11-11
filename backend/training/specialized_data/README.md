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

## Required experimental protocol (schema 2)

Each nonempty CSV also requires a sibling protocol file:

- `antidote.csv` -> `antidote.protocol.json`
- `growth_regulating.csv` -> `growth_regulating.protocol.json`

The `.protocol.example.json` files are **unfilled, invalid templates**, not
approved evidence. Copy the appropriate example to the protocol filename and
fill it only after reviewing the actual experimental source and reuse terms.
The initial supported profiles are acetaminophen/paracetamol injury rescue and
Arabidopsis thaliana primary-root response relative to control. A future toxicant
or species needs a separate explicit profile, data and validation.

Document every required condition, exact endpoint/context, species, toxicant
where applicable, source-defined meaning of both classes and source provenance.
Provenance includes a checked source/license URL, version, curator, retrieval
date and an experimental-label declaration. The accepted license identifiers are
listed in `app/ai_research_agent/config.py`; a source-specific license must be
verified rather than inferred from its hosting database. A curator declaration
is recorded as such and does not constitute independent scientific review.

Set `dataset_sha256` to the SHA-256 of the exact CSV bytes, for example:

```powershell
(Get-FileHash -LiteralPath .\training\specialized_data\antidote.csv -Algorithm SHA256).Hash.ToLowerInvariant()
```

The trainer reads one bounded CSV snapshot and compares that snapshot's digest
to the protocol. A stale sidecar is rejected before fitting. Sources, conditions
and label definitions are stored with model metadata. Salts, mixtures and
structures over 200 atoms are excluded for explicit curation. Stereochemical
variants share a nonchiral Murcko split group; all acyclic structures share one
group. Fingerprints in this specialized binary path are nonchiral Morgan-2048.

This path predicts **binary source-defined classes**. It does not predict a
numerical rescue percentage or root-length ratio. Continuous measurements need
a separate regression task; do not choose a binary cutoff using test results or
convert absent measurements into class 0 to obtain a passing score.

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

After training, close and reopen ChemAnalyzer so the backend reloads `manifest.json`.

## Evaluation and activation

The split is fixed by seed (42 by default), using entire scaffold groups and
group sizes only. The train partition needs at least 30 compounds and five
scaffolds of each class. Validation needs at least five compounds/class, and
test needs at least ten compounds/class, 20 molecules and three scaffold groups.
Thus the old 60-row floor alone is insufficient for a real train/validation/test
experiment. Never try different seeds after inspecting a failed test.

With `--algorithm auto` (default), fixed Random Forest, logistic regression and
gradient boosting candidates are fitted to **train only**, in one CPU thread.
Candidates passing validation balanced accuracy >0.60, ROC-AUC >=0.70 and
MCC >=0.10 are ranked by validation PR-AUC. An explicit `--algorithm` fixes a
single candidate before evaluation. Test is evaluated only for the selected
candidate; a failed test does not select a replacement. No candidate passes if
the exact evaluated object fails test balanced accuracy >0.60, ROC-AUC >=0.70,
MCC >=0.10, sample support or improvement over the prior baseline in PR-AUC.
No refitting on validation/test occurs after scoring. Both training and serving
use the estimator's fixed `predict` decision, including tie handling.

Each accepted artifact gets a unique filename and SHA-256 in an atomically
written manifest. Its applicability reference contains train molecules only.
The report includes candidate/validation/test metrics, baseline, complete split
indices, support counts and curated records. Existing files are not deleted
after failed retraining; old artifacts are never overwritten by a new filename.
Loading checks the artifact checksum, protocol, feature contract and disjoint
partition indices. Old CV-only specialized artifacts cannot bypass this gate:
they remain on disk but require retraining and a protocol before prediction.
Damage in one specialized domain does not disable another domain's valid model.

These thresholds are safeguards, not proof that a model is suitable for real-world decisions. Review leakage, endpoint homogeneity, applicability domain and external validation before interpreting predictions. The app does not provide medical, toxicological or agricultural advice.
