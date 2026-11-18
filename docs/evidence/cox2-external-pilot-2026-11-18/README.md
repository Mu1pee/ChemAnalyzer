# External COX-2 research experiment, 18 November 2026

The new fixed random forest failed its external assessment. Balanced accuracy
was **0.567708**, ROC-AUC **0.591667**, MCC **0.137955**, and average precision
**0.607062** versus the prior baseline **0.483871**. The confusion matrix,
with true rows and predicted columns ordered inactive/active, was
`[[15,17],[10,20]]`. No COX-2 model was activated or added to an application
release, and no accepted model artifact was exported.

Training used all 2,740 previously curated ChEMBL37 compounds. The old internal
validation/test rows were explicitly training data for this new phase; their
previous failed result remains unchanged. The new external set contains
62 distinct structures (30 active, 32 inactive), 35 nonchiral Murcko groups,
and 64 measured observations. It has zero exact-structure or Murcko overlap
with the entire old panel, and no known old source DOI was retained.

PLAN.json and PLAN_AMENDMENT.json were saved before fitting or predicting.
The amendment makes the existing implementation's `balanced_subsample` class
weight explicit. The previous validation-selected algorithm was fixed at
200 trees, seed 42, one CPU thread and training-only sigmoid calibration
using three scaffold folds. There was no algorithm, threshold or seed search
on the new external outcomes. A training-only label-permutation control gave
ROC-AUC **0.491333** across three outer scaffold folds.

The predeclared 95% interval for balanced accuracy, from 5,000 bootstrap
replicates of whole scaffold groups, was **[0.402520, 0.723071]**. The accuracy,
AUC, MCC and uncertainty gates all failed. Only 16 of 62 external compounds
had maximum training-fingerprint Tanimoto >= 0.5; 45 were at the domain edge
and one was below 0.3. These domain results do not excuse the failed overall
test. This small, source-dependent retrospective sample does not establish
prospective or population-wide accuracy.

The current set is now an evaluated benchmark. It must not be silently reused
as independent validation after selecting features, algorithms, thresholds or
data exclusions using its results. A future adaptively developed model needs
new untouched validation data or a clearly disclosed different evaluation.

Data provenance and exclusions:

- BindingDB's November 2026 article and patent exports supply the older
  observations, under CC BY 3.0 with original record IDs, source links, archive
  checksums and underlying authors/publications retained in the candidate
  pool's provenance file. Their measured values and structures were checked
  against the actual versioned exports. The ADHP-fluorescence assay 7562_1 was
  excluded from this pilot; retained assays measure arachidonic-acid conversion
  or its prostanoid products. Preincubation and detection protocols still vary.
- Najla A. Alshaye, Mohamed K. Elgohary, Mahmoud S. Elkotamy and Hatem A.
  Abdel-Aziz, *Molecules* 2024, 29, 1309,
  [DOI 10.3390/molecules29061309](https://doi.org/10.3390/molecules29061309),
  contribute seven additional observations under CC BY 4.0. Table 1 supplies
  measured mean IC50 values; Schemes 1/2, compound names, molecular formulas
  and masses were reviewed. OPSIN resolved names to structures, checked with
  RDKit. The N-arylglycyl names for series 10 were made explicit from Scheme 2;
  no unspecified E/Z stereochemistry was invented.
- Compounds 5a-f were excluded for old scaffold overlap. Compound 10b was
  excluded because the named/drawn structure and published formula/mass
  disagree. Compounds 10e/10f were excluded because Table 1 and the discussion
  exchange their numerical IC50 values. All three exclusions occurred before
  predictions. No absent outcome received an inactive label.
- Cayman identifies kit 560131 as ovine COX-1 / human recombinant COX-2:
  [manufacturer specification](https://www.caymanchem.com/product/560131/cox-ovine-human-inhibitor-screening-assay-kit).

The curated measurements retain a license for each row. Changes to source data
are context filtering, name/structure interpretation, unit conversion to nM,
threshold labels at IC50 <= 1,000 nM, deduplication and overlap exclusion.
Source XML, the supplementary package and structure-resolver responses remain
checksum documented in source-review.json and source-provenance.json.

This experiment changes no application code or installer. It supplies no
evidence for acetaminophen rescue, Arabidopsis primary-root effects, or any
other application endpoint.
