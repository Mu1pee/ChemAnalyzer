# ChemAnalyzer 3.2.9

## QSAR evidence and safe model admission

- Revalidated the legacy COX-2 ChEMBL 37 panel using a predeclared, fixed-seed
  scaffold holdout and validation-only candidate selection.
- The selected model reached 67.5% balanced accuracy on the held-out test but
  ROC-AUC 0.733, below the existing 0.75 QSAR gate. No replacement weights were
  admitted. The historic CV-only COX-2 artifact is preserved but rejected by
  the application.
- Updated API and UI labels to show held-out test metrics and explain when a
  model is withheld. Nine previously qualified Research Agent models remain
  available.
- Aligned the legacy QSAR default forest at 200 trees and made final-fit
  probability calibration scaffold-disjoint. Scores now retain full precision.
- Added reproducible curation, provenance, model-procedure and artifact checks.

## Limitations

The COX-2 experiment is a retrospective internal scaffold holdout from a
previously studied multi-assay panel, not independent or prospective
validation. Protocol heterogeneity remains. Acetaminophen rescue and Arabidopsis
root-growth models remain untrained for lack of eligible complete experimental
data. See `COX2_REVALIDATION_2026-11-11.md` and `MODEL_QUALITY_POLICY.md`.

## Windows

Windows x64 portable and per-user installer are unsigned because no code-signing
certificate is configured. The portable executable was launched on Windows and
the packaged UI/API behavior was checked. SmartScreen behavior is unchanged.
