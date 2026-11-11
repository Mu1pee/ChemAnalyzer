# COX-2 QSAR revalidation — 2026-11-11

## Decision

The previous COX-2 panel artifact is **not admitted for prediction** by the
schema-2 quality gate. A frozen-data retrospective scaffold holdout was
evaluated with the procedure recorded before evaluation. The selected candidate
did not meet the predeclared ROC-AUC requirement on the untouched test set, so
no replacement model was serialized or activated. This is an internal
retrospective assessment, not independent or prospective validation.

## Reproducible input and endpoint

- Source snapshot: ChEMBL 37, target CHEMBL230, human single protein.
- Frozen curated table SHA-256: `B8282F6D0824FBDC685F256C8646903E1C6DE8356762EF21E0472A0BA8057413`.
- Predeclared plan SHA-256: `48AB66A2E148B647F0303DBE1E157E3E68DEF6E6D3E072A5D6BD832557722294`.
- Exact measured endpoint: IC50 in nM, relation `=`, active label at `<=1000`
  nM; missing, invalid, mixed-fragment, oversized and conflicting-parent
  observations are excluded.
- 2,740 curated unique structures; 2,846 source rows failed assay/quality
  filtering, 43 measurement/structure checks, and 56 compounds had conflicting
  threshold labels. The categories are row/compound-level exclusions and are
  not additive to the final unique-compound count.
- Source licenses and attribution are inherited from the archived ChEMBL
  provenance; the source snapshot checksums are verified before parsing.
- Morgan radius-2, 2,048-bit fingerprints; single-fragment structures are
  standardized and uncharged. Whole nonchiral Murcko groups are kept together;
  all acyclic structures share one group. No structure group crosses the
  train/validation/test partitions.

## Fixed procedure and results

Seed 42 assigned whole scaffold groups by group sizes to approximately
64/16/20% train/validation/test. Three fixed candidates were fit on train only.
Candidates were screened on validation with balanced accuracy >0.60, ROC-AUC
>=0.75 and MCC >=0.25; the eligible candidate with the highest validation
PR-AUC was selected. Test scores did not select a candidate or threshold. The
random-forest candidate was selected. Its 200-tree fit/calibration procedure
used only scaffold-disjoint train folds; label randomization was also confined
to train (ROC-AUC 0.477).

| Partition | Molecules | Positive / negative | Scaffolds | Balanced accuracy | ROC-AUC | PR-AUC | MCC |
|---|---:|---:|---:|---:|---:|---:|---:|
| Train | 1,754 | 964 / 790 | 336 | — | — | — | — |
| Validation | 438 | 197 / 241 | 257 | 0.745 | 0.840 | 0.809 | 0.493 |
| Held-out test | 548 | 280 / 268 | 275 | **0.675** | **0.733** | 0.722 | 0.355 |
| Test prior baseline | 548 | 280 / 268 | 275 | 0.500 | 0.500 | 0.511 | 0.000 |

The held-out balanced accuracy exceeds 0.60, and the model beats the prior
baseline, but ROC-AUC 0.733 is below the predeclared 0.75 gate. Therefore the
model is **withheld**. The test was evaluated once under this fixed plan; no
alternative seed, subset, label threshold or algorithm was selected from its
scores. The older 70.81% cross-validation balanced-accuracy figure describes a
different historical procedure and must not be presented as validation of the
shipped 300-tree object.

## Implementation changes

- Align default cross-validation, label-randomization and final-fit tree counts
  at 200; preserve scaffold-disjoint calibration folds when fitting the final
  legacy assay model.
- Record full-precision metrics and define tie predictions consistently.
- Add a frozen-snapshot revalidation path, strict artifact/procedure checks,
  and inference admission that rejects legacy internal-CV-only artifacts.
- Preserve the prior released bundle and historical report unchanged. The new
  revalidation output has an empty model manifest because the candidate failed
  admission.

Software fixture tests do not contain biological training examples and do not
substitute for model-performance evidence.
