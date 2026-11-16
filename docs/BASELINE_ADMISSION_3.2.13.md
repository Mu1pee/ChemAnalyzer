# Numerical baseline admission — ChemAnalyzer 3.2.13

The Research Agent's classifier admission previously trusted the stored
`beats_baseline: true` flag. A record could pass with adequate balanced accuracy,
ROC-AUC and support even when its baseline PR-AUC was missing or exceeded the
classifier's PR-AUC. This affected the quality check used during registry
review, activation, catalog selection and inference; it was not evidence of a
newly trained model or an error in the nine reviewed classifiers' saved scores.

Policy version **2026-11-16** now compares the actual values. Classifier test
and baseline PR-AUC must be finite numeric values in [0, 1], and the test value
must be strictly greater. In this evaluator PR-AUC means average precision.
A true flag cannot replace the comparison; a false flag still rejects the
record. Balanced accuracy >0.60, ROC-AUC >=0.70, scaffold/class support and
test-selection independence remain required. The stricter target-QSAR and
specialized policies remain separate.

For example, a software fixture with BA 0.72, ROC-AUC 0.80, PR-AUC 0.60,
baseline PR-AUC 0.90 and a true flag was incorrectly admitted before the fix.
It is now rejected. Equal, missing, malformed, Boolean, nonfinite and
out-of-range values also fail. These fixtures are software checks, not
synthetic experimental observations or evidence of biological accuracy.

## Scientific artifacts and scope

All **ten existing Research Agent artifacts** were checked using the new
policy: nine classifiers have real saved test PR-AUC greater than their saved
baseline PR-AUC; FreeSolv retains its distinct R2/MAE gate. Their original
source seed, metadata and weights were preserved. No model was refitted,
selected again, approved by a fictitious reviewer or assigned a new accuracy.

An isolated copy of the real solubility record was given an inconsistent
baseline PR-AUC of 0.95 while retaining its true flag. Source API checks
confirmed rejection in the catalog, withheld numerical prediction and denied
review/activation, while the other models stayed available. This deliberately
damaged copy is a local software fixture and is excluded from the release seed.

The original model validation reports still define the scope and limitations
of their numerical results. These are internal held-out scaffold results;
independent external/prospective validation and calibrated probabilities are
not claimed. In particular, HIV recall remains 32.07%; solubility is a
source-defined low-solubility class, not numerical logS or bioavailability.

COX-2 remains withheld after its failed held-out ROC-AUC gate. APAP rescue and
Arabidopsis primary-root models remain **not_trained**. Their completed source
reviews are documented in
[ENDPOINT_DATA_REVIEW_2026-11-16.md](ENDPOINT_DATA_REVIEW_2026-11-16.md).
Nearest-drug structural similarity does not become a trained activity-spectrum
model. The full requested goal is therefore still incomplete.

## Verification

- The added negative cases reproduced the defect before the fix: 23 failed,
  one positive control passed. After the fix, 91 focused checks passed.
- The complete backend suite passed: **404 tests**, no failures, errors or skips.
- Electron's backend/security/store/seeding suite passed: **20 tests**.
- TypeScript and the Vite frontend production build passed. Existing large-chunk
  warnings remain; no frontend behavior was changed by this patch.
- Source model checks admitted all ten real models and verified their checksums.
  Original source-seed files remained unchanged after the isolated failure test.
- The packaged Windows application served all nine classifier endpoints with
  normal applicability handling and served FreeSolv with the Lab enabled.
  The unchanged solubility object's numerical result matched its previously
  verified result. The isolated contradictory-baseline profile was rejected
  by the frozen backend and catalog; the other nine models remained admitted.
- Portable's real first launch completed in 113.65 seconds, including extraction.
  Local classifier inference worked with the Lab disabled, while FreeSolv's
  Lab-only route remained disabled. The loaded solubility result matched the
  same preserved object, and out-of-domain numerical scores remained hidden.
  Packaged checks reported no renderer errors or research-data mutations.

Packaged Windows and Portable verification is recorded separately in the release
verification archive; a compiled installer is not proof that installation was
tested. No code-signing certificate is configured, and SmartScreen is not
bypassed. The installer must be identified as unsigned.

## Live ChEMBL observation

A fresh source query on **2026-11-16 at 17:58:19 UTC** returned aspirin CHEMBL25
with 500 of 655 activity rows in 55.156 seconds. It was explicitly marked
**partial**: mechanism and activity requests encountered HTTP 500 and the
target request timed out. Verified earlier activity rows were retained rather
than represented as a complete response or absence of activity. This observation
does not claim that the upstream service is continuously available. It does
not undo the prior packaged TLS-resource and pagination fixes.

The new frozen backend's `--check-network` command also reached the official
status endpoint but received HTTP 500 and exited with failure. Its adjacent
CA resource was present. Both the structured failure and original traceback
are retained; this is not reported as a successful ChEMBL status check.

The verification archive preserves the fresh-source response, raw test logs,
JUnit output, model checksum checks and application checks. No source error was
hidden by replacing this observation with a later successful attempt.
