# ChemAnalyzer 3.2.8 — specialized experimental evidence contract

Date: 2026-11-11. This update improves the training and admission path for the
requested acetaminophen-rescue and Arabidopsis primary-root **binary** models.
Neither endpoint is claimed as trained: no eligible complete experimental table
has been integrated, and no new scientific model or outcome was invented.

## Corrected scientific problems

The previous Random Forest path evaluated 200-tree CV models but fit a 400-tree
final object on all data. Those scores did not directly evaluate the final
configuration. It also admitted free-text source/context declarations without a
checked source-license protocol sidecar and used individual SMILES as acyclic
scaffold groups. CSV mixtures could be silently assigned to a largest fragment.

The replacement fits fixed candidates to the train partition only, selects by
validation PR-AUC among validation-qualified candidates, tests only the selected
object and saves that exact object without refitting on validation or test. The
estimator's `predict` decision is used in both evaluation and serving, including
ties. Default seed 42 is fixed; seed retries after test inspection are not valid
independent evidence. Splitting uses group sizes, never labels or test metrics.

All acyclic molecules share a split group and stereo variants of cyclic
scaffolds share a nonchiral Murcko group. Salts, mixtures and structures above
200 atoms require explicit curation. Features in this path remain the same
nonchiral Morgan-2048 representation for fitting and inference; chirality-specific
effects are not separately resolved by these fingerprints.

## Experimental inputs and rights

A nonempty CSV requires a matching `.protocol.json` sidecar with schema 2,
profile, exact endpoint/context, species, toxicant where applicable, all
profile-specific conditions, class definition, experimental-source provenance,
reviewed license identifier/URL and SHA-256 of the exact CSV snapshot. The parser
rejects duplicate headers and malformed extra columns, with 8 MB/50,000-row
limits. Missing outcomes are never generated as negatives.

The protocol is a curator declaration, not an automatic independent scientific
review. The selected binary endpoint and labels must be supported by the real
assay. This does not turn continuous primary-root ratios or rescue percentages
into numerical predictions. Continuous outcomes require a separate regression
task; cutoffs must not be selected to maximize test scores. Other toxicants,
organisms and conditions require separate explicit profiles/data and validation.
The two `.protocol.example.json` files are deliberately incomplete, invalid
templates with `experimental=false`, not approved data.

## Admission and persistence

- Train needs at least 30 compounds and five scaffold groups per class;
  validation needs five compounds/class; test needs ten/class, 20 molecules and
  three groups. Every split is reserved by whole groups.
- Validation and test require balanced accuracy strictly above 0.60, ROC-AUC
  at least 0.70 and MCC at least 0.10. The test PR-AUC must beat a train-fitted
  prior baseline. Scores are retained at full precision at the boundary.
- Test failure rejects the selected candidate without selecting a replacement
  by test results. No candidate uses validation/test rows for fitting.
- Models receive unique artifact filenames, checked SHA-256 values and an
  atomically written manifest. Reports contain curated records, complete split
  indices, support, candidate/validation/test metrics and baseline. Applicability
  references contain train molecules only. Failed training preserves existing
  model files, and a damaged old manifest is preserved for recovery.
- Loading recomputes admission, requires protocol/feature compatibility and
  complete nonoverlapping partition indices, and checks SHA-256 **before** local
  deserialization. Old CV-only specialized artifacts stay on disk but cannot
  bypass the new contract. An invalid domain does not disable another valid one.

These checks protect reproducibility and accidental artifact damage. They are
not a digital signature or a guarantee against deliberately forged local metadata.
The existing nine Research Agent models and separate COX-2 bundle are unchanged;
their original source rights, internal metrics and limitations remain in their
previous validation reports. External/prospective validation is not claimed.

## Verification

Backend: **295 tests passed**, including nonoverlapping selection/test behavior,
preservation of the exact fitted object, rejection after a failed fixed test,
protocol/toxicant/species/license constraints, CSV checksum mismatch, acyclic
grouping, mixture rejection, domain-specific failures, API support fields,
out-of-domain withholding and preservation of damaged manifests. Artificial
fixtures are restricted to software tests and are not biological training data.

TypeScript/Vite production build passed. The native packaged Windows application
started as 3.2.8, retained nine qualified Research Agent models and COX-2, hid
outside-domain values and rejected an invalid legacy specialized artifact with a
claimed 99% score before deserialization. That artifact was a software-only test
fixture in an isolated profile and was never included in the release seed. The
unaffected growth endpoint remained not_trained, mixtures returned HTTP 400 and
the new protocol guidance rendered without observed renderer errors. Actual CLI
execution on both empty CSV templates declined training (expected exit 1), wrote
an empty manifest and created no model artifact; both incomplete protocol examples
were rejected.

Actual Portable EXE verification passed in a fresh isolated profile: version
3.2.8, nine qualified research models, three screening endpoints and both
specialized endpoints explicitly not_trained in API and UI. The verified launch
took 85.44 seconds, including extraction and checks, and was closed afterwards.
An initial observation expired before a test port was found; the initial process
was then confirmed absent. The subsequent diagnostic launch was made only after
that terminal-state check. Its earlier termination cause is not established;
the first observation is not counted as a successful launch. A 7-Zip payload test
reported no corruption (with its normal appended-container warning). This does
not establish reliable startup on every Windows installation.

No signing certificate is configured. A clean-machine
installer test, calibrated probabilities, clinical/field effectiveness and
completion of the overall >60% goal are not claimed.
