# ChemAnalyzer 3.2.12: NCATS kinetic-solubility classifier

A new **experimental** model predicts the source-defined low-solubility class
for the NCATS kinetic aqueous-solubility protocol at pH 7.4. Internal held-out
balanced accuracy is **78.2001%**, ROC-AUC **0.849157**, PR-AUC **0.857756**.
This result does not establish accuracy for antidote activity, Arabidopsis root
growth, thermodynamic solubility, bioavailability or other ADMET endpoints.

## Source, assay and rights

- Federal NCATS/NIH experimental data, depositor NCGC, external ID
  `ADME-solubility1`, [PubChem AID 1645848](https://pubchem.ncbi.nlm.nih.gov/bioassay/1645848),
  version 2, revision 1.
- Frozen [CSV](https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/aid/1645848/CSV):
  295,477 bytes; SHA-256
  `081904a6292637bb16a59de66b8d648729dd1b583a566c532ff32e60fceba1a2`.
- Frozen [assay description](https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/aid/1645848/description/JSON):
  5,915 bytes; SHA-256
  `da0eb7b21678d3169f692b1681b1f00e1ca8faf649217d0f4ab6ebfcb6c00588`.
  Both snapshots were retrieved on 2026-11-16 and are pinned by the source adapter.
- Primary publication: Sun et al. (2019),
  [doi:10.1016/j.bmc.2019.05.037](https://pubmed.ncbi.nlm.nih.gov/31176566/).
  All listed authors are affiliated with NCATS; the assay description identifies
  its federal submitter and intramural data generation.
- Rights basis for these federal database records is Public-Domain-US-Gov,
  with the checked [NCBI government-works policy](https://www.ncbi.nlm.nih.gov/home/about/policies/).
  This is not a blanket license for all PubChem contributions, the assay method
  or the Elsevier article and supplements. No article text is redistributed as
  training data. The new curated table and ChemAnalyzer weights are CC BY 4.0
  with attribution; see LICENSE_NOTICES.md. No government endorsement is implied.

The public source contains **2,532 substance records / 2,530 distinct CIDs**.
It is a subset, not the publication's 11,780-compound collection or the portal's
36,171-compound model. No published NCATS estimator or its reported performance
was imported as ChemAnalyzer's model or validation result.

The protocol uses Pion microSOL: compound initially prepared in DMSO, final
concentration 150 uM in 100 mM phosphate buffer at pH 7.4, six hours at room
temperature, vacuum filtration and UV absorbance at 250–498 nm, in duplicate.
The reference plate uses solubilized compound in n-propanol. This is kinetic
solubility under those conditions, not an equilibrium or intrinsic-solubility
measurement.

## Source classes and exclusions before fitting

Model **Y=1 means Low, <=10 ug/mL**, source Inactive and `class = 1`.
Model **Y=0 means Moderate/High, >10 ug/mL**, source Active and `class = 0`.
Here PubChem Active is the *higher-solubility* phenotype, not model Y=1. The
adapter explicitly checks phenotype, source outcome, class comment and measured
value/interval together. The source description includes 10 in the low class;
there are no exact 10 ug/mL values in this snapshot.

Of the original records, 1,400 are Low, 1,056 Moderate/High and 76 N/A.
The 76 inconclusive/unmeasured N/A results are excluded. One Moderate/High row
has only `>6 ug/mL`; that interval crosses the 10 ug/mL threshold and cannot
independently establish its binary class, so it is excluded with an explicit
reason. Values such as `<1` or `>100` supply only their unambiguous class, not an
invented exact concentration or a continuous regression target. No numerical
target is derived from the rounded activity score.

This leaves 2,455 records before structure preparation. Preparation excludes
17 invalid, oversized or multicomponent structures, collapses one same-class
duplicate, and excludes both members of one conflicting structure pair.
**2,435 unique accepted structures** enter the experiment. Different SIDs or
doses are not additional independent molecules. No outcomes were fabricated,
missing records were not labeled inactive, and no other solubility protocol or
source was pooled into this dataset.

## Fixed experiment and internal validation

The plan was written and hashed before the experiment started. Task
`35b5032c82ec4fe3941afde2d45ad777`, run `2250d99df331487d82af0bd9d90c40d6`,
model `f95957567a394c04bf9c6c0675e606d5`; seed 42.

| Partition | Molecules | Low / Y=1 | Moderate-high / Y=0 | Scaffold groups |
| --- | ---: | ---: | ---: | ---: |
| Fitting | 1,558 | 920 | 638 | 743 |
| Validation | 390 | 225 | 165 | 390 |
| Test | 487 | 247 | 240 | 486 |

Features use the existing Research Agent contract: chiral Morgan radius 2,
1,024 bits plus six RDKit descriptors. Exact identity preserves stereochemistry;
nonchiral Murcko scaffolds group stereo variants, and all acyclic structures
share one group. Complete partition indices, nonoverlap and support counts were
independently verified against saved features. Size-based grouping places large
series predominantly in fitting and many single-scaffold compounds in the
holdout; the result is not a prospective or randomly sampled performance claim.
An additional nonchiral, uncharged-parent identity audit found no duplicate
parent groups among the 2,435 accepted structures and no cross-partition parent
identity overlaps. This extra check does not establish all tautomer or close-
analogue equivalences and did not change the split or labels.

The existing fixed RF/logistic-regression/gradient-boosting grids use train-only
three-fold GroupKFold. Candidates passing validation BA >0.60 and ROC-AUC >=0.70
are ranked by validation PR-AUC. Random Forest was selected: 100 trees,
`min_samples_leaf=1`, balanced class weights. Its validation PR-AUC was
0.857604. Gradient boosting's higher validation balanced accuracy was not used
to change that predeclared selection rule. The test was evaluated only for the
selected train-fitted object, with no post-test refit, seed change, threshold
tuning or replacement selection.

| Held-out test metric | New model | Prior baseline |
| --- | ---: | ---: |
| Balanced accuracy | 0.7820006748 | 0.5 |
| ROC-AUC | 0.8491565452 | 0.5 |
| PR-AUC | 0.8577558639 | 0.5071868583 |
| Recall of Low | 0.8056680162 | 1.0 |
| Precision of Low predictions | 0.7743190661 | 0.5071868583 |
| F1 | 0.7896825397 | 0.6730245232 |

Confusion matrix, rows true 0/1 and columns predicted 0/1:
`[[182, 58], [48, 199]]`. A diagnostic 1,000-sample whole-scaffold bootstrap
(seed 20261116) gives a 95% BA interval of **0.744817–0.818681**. It was computed
after the fixed model was selected and was not a tuning or selection criterion.
No external or prospective validation and no separate probability calibration
are claimed. The published point quality does not guarantee accuracy for a new
query structure.

The unchanged, train-only applicability rule admits 301 of the 487 held-out
molecules (61.81%; 173 Low and 128 Moderate/High). The other 186 would have their
numerical scores withheld in the application. As a diagnostic only, admitted
test molecules have BA 0.792901, ROC-AUC 0.869558 and PR-AUC 0.897987. These
conditional metrics were not used to tune the domain threshold, select a model
or replace the full-test admission metrics shown above.

The saved RF's predictions reproduce every reported test metric. Its actual
tree count, leaf setting, class weights and seed were inspected; the saved
applicability reference equals fitting fingerprints and descriptor ranges only.
Artifact SHA-256:
`f486464227e2f0218ee82a7162003caa76ff3ed74d51ed190a8a324ce4ec746e`.
The nine existing Research Agent artifacts retain their original bytes. All ten
remain experimental, with no human approval or activation records fabricated.

## Application integration and reproduction

The ADMET catalog has a separate **Кинетическая растворимость** card and sidebar
view. The predictor's positive score explicitly means *low* kinetic solubility.
The screen shows the cutoff, conditions, held-out metrics and both class counts.
Outside its heuristic applicability domain, numerical scores are withheld.
Existing ESOL/logS estimates remain separately labeled estimates for a different
quantity. The catalog and prediction use the same complete task match and
artifact-integrity/quality admission. Local prediction is available with the
training laboratory disabled; imports/training remain opt-in.

AI Research Lab provides the exact task preset and reviewed NCATS source import.
From `backend`, a fresh independent reproduction can be requested with:

```powershell
python -m training.train_screening --assay solubility --output-dir <fresh-directory>
```

The adapter rejects changed source bytes, metadata, protocol or class semantics
pending renewed source review. Do not rerun seeds or choose a replacement based
on test performance. The local original plan, raw snapshots, prepared records,
indices, features and model are retained under `solubility-2026-11-16`; the
release evidence contains a compact independent reproduction report.

This addition does not resolve the missing acetaminophen-rescue or Arabidopsis
primary-root datasets. Those models remain not_trained. COX-2 remains withheld
under its stricter failed held-out ROC-AUC gate; general toxicity and other
unsupported biological claims remain untrained.
