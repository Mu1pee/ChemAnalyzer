# ChemAnalyzer 3.2.0 audit

Date: 2026-11-02. This is an incremental audit, not a claim of exhaustive coverage.

## Verified baseline

Python/FastAPI/RDKit backend: 113 pytest tests passed; selftest passed with UTF-8 output. Electron: 17 tests passed. React/TypeScript/Vite production build passed after the events alias fix. Original Git commit: 41d6f57. Showcase licensing preserved.

## Findings and reproduction

| Priority | Location | Finding / reproduction | Next action |
| --- | --- | --- | --- |
| P1, fixed locally | frontend/vite.config.ts, frontend/package.json | Production build failed on Ketcher EventEmitter import | Browser events dependency and alias added; build passed |
| P2 | frontend/package-lock.json | npm audit reports five moderate findings through Ketcher/dpdm/glob/minimatch | Evaluate compatible patched dependency versions; rerun audit/build |
| P2, compatibility risk | frontend/package.json | miew-react declares React 18 peers while app uses React 19 | Test editor and 3D viewer at runtime before changing versions |
| P2 | backend/scripts/selftest.py | Default Windows cp1251 output raises UnicodeEncodeError | Run with -X utf8; consider explicit output encoding |
| P3, fixed locally | .gitignore | Generated Ketcher assets and TypeScript cache appear as untracked files after build | Ignore generated resources/cache and local env files |
| P3 | frontend build | Large bundle and third-party 3Dmol eval warning | Assess runtime CSP compatibility and loading performance |

No P0 issue confirmed by checks performed so far.

## Architecture and unverified areas

- Backend: FastAPI routes, RDKit calculations, PubChem/ChEMBL integrations and QSAR services; tests cover contracts, security, ADME, PubChem and specialized activity.
- Frontend: React 19, TypeScript, Vite 7, Ketcher 3.18; browser runtime and export workflows still require inspection.
- Desktop: Electron backend supervisor with free-port selection and health checks; PyInstaller onedir spec and electron-builder NSIS/portable configuration exist.
- Windows EXE has not yet been built or tested on a clean system.
- Existing specialized training uses user-supplied endpoint data; supplied CSV files are templates. No real-data training has been executed in this audit.
- Scientific dataset provenance, leakage controls and external API live behavior require further review.
- Credential-pattern scan found no matches in original tracked files; new lockfile and pending files must be scanned before checkpoint.

## Execution order

1. Verify file inclusion and publish authorized backup/pre-windows-build checkpoint.
2. Create feature/windows-desktop-stabilization from that checkpoint.
3. Resolve dependency/runtime findings and build/test Windows artifacts.
4. Audit and extend reproducible ML training only with suitable real experimental data.
5. Add CI and update user documentation with verified results and explicit limitations.

## Update: 2026-11-11, version 3.2.7

The preceding sections are the historical 3.2.0 baseline. Subsequent versions
include actual Windows builds and real experimental models; current coverage is
documented in docs/MODEL_QUALITY_POLICY.md. The overall >60% goal remains open.

This update corrects endpoint/context pointer collisions, malformed quality
evidence/counts, failure propagation from one damaged model/schedule, interrupted
bundled-model copying, Electron origin-prefix checks and reserved Windows export
names. The fixes preserve existing user files and scientific model weights.
Backend: 276 tests passed; Electron: 20 passed; TypeScript/Vite build passed.
Nine fixed research models had their original test metrics, support counts,
scaffold separation and checksums reproduced. Native packaged Windows checks
passed, including corrupt-record isolation. Live ChEMBL still returned upstream
HTTP 500 for two sections, correctly reported as a partial result. See
docs/RESILIENCE_VALIDATION_3.2.7.md for scope and outstanding limitations.

## Update: 2026-11-11, version 3.2.8

Specialized training previously evaluated 200-tree Random Forest CV objects and
then fit a 400-tree final object. It now selects fixed train-only candidates by
validation, tests the selected object and saves it without post-test refitting.
The two requested biological profiles require a checksum-bound experimental
protocol/source/license declaration. Legacy CV-only specialized models cannot
bypass held-out admission; model artifacts are checked before deserialization.
Mixtures, acyclic-group leakage and damaged-manifest preservation are covered.
Backend: 295 tests passed; TypeScript/Vite production build passed; packaged
Windows checks retained existing models and rejected an invalid high-score
legacy fixture. Actual empty-template training created zero models. See
docs/SPECIALIZED_PIPELINE_3.2.8.md. The overall model-quality goal remains open.
