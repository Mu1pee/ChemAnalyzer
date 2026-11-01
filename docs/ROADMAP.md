# Roadmap

This roadmap describes proposed project work, not guaranteed release dates.

## Priority 1 — release readiness

- [ ] Build the installer and portable package on Windows 10/11 x64 using Node.js 24.20+ and Python 3.12 x64.
- [ ] Install and launch both artifacts on a clean Windows machine without Python or Node.js installed.
- [ ] Complete the acceptance checklist in `DESKTOP_BUILD_GUIDE.md`.
- [ ] Capture real application screenshots after validating the packaged UI and Ketcher editor.
- [ ] Review all staged files for API keys, personal information, local datasets, and trained model files before each public push.
- [ ] Generate and commit dependency lockfiles after confirming the npm dependency set used for a release.

## Priority 2 — documentation and maintenance

- [ ] Add user-facing documentation for the main interface and supported export formats.
- [ ] Document the meaning and limitations of each analysis result in the relevant UI sections.
- [ ] Add frontend-focused automated tests for important interactions and API error states.
- [ ] Keep the change log and version references synchronized across the root package, frontend package, and backend version.

## Priority 3 — research modules

- [ ] Improve the specialized activity data workflow with curated, source-traceable experimental datasets.
- [ ] Train endpoint- and context-specific models only when the dataset is sufficiently documented and validated.
- [ ] Report model metrics and applicability-domain limits with every specialized model release.
- [ ] Do not ship unvalidated models or present an unavailable model as a working prediction.

## Release principle

A feature is not considered release-ready merely because its interface exists. It should have reproducible data sources, documented limitations, automated tests where practical, and a successful check in the packaged Windows application.
