# COX-2 single-protein research experiment

The exact saved train-only model passed the fixed retrospective internal
scaffold holdout: balanced accuracy 0.762168, ROC-AUC 0.822185, MCC 0.524005.
Its test comprises 422 structures excluded from its fitting/calibration.
The source panel had already been studied and fitted in earlier experiments;
this is not a new untouched external or prospective validation. Previous
mixed-context internal and external failures remain in the project history.
The previously evaluated external 62-compound benchmark was not reused here.

PLAN.json fixes the procedure before fitting. provenance.json retains original
source hashes, context annotations and contributing assay identifiers.
curated.json contains 2111 structures/2146 observations, under CC BY-SA 3.0.
report.json records all candidates, fixed split, label-permutation control,
selected procedure and test. test-predictions.json and model-verification.json
reproduce the saved object without refitting. The bootstrap interval is
descriptive and was not used to select a model. SHA256SUMS.json records exact
file bytes; line endings are preserved deliberately.

Attribution: ChEMBL contributors, EMBL-EBI; ChEMBL 37.
[CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).
Changes: human single-protein context selection, description-conflict review,
unit/cutoff and structure checks, grouping and a fixed train/validation/test
experiment. Protocols may still differ within that context. The data and
provided weights retain this license; application source licensing is separate.

The release's QSAR evidence archive contains the model, manifest and frozen
original source responses. These results supply no APAP-rescue or Arabidopsis
primary-root validation. The full application-wide quality goal remains open.
