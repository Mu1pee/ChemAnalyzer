# Windows build checkpoint - 2026-11-02

Working branch: feature/windows-desktop-stabilization. Backup remains c0b4b5e on backup/pre-windows-build.

## Verified

- PyInstaller produced build/backend/chemanalyzer-backend/chemanalyzer-backend.exe with Python and RDKit dependencies.
- Backend tests: 113 passed; Electron tests: 17 passed.
- TypeScript/Vite production build passed.
- Playwright with installed Edge opened the production frontend, initialized Ketcher and analyzed ethanol: C2H6O, molecular weight 46.069. No page JavaScript errors remained.
- Ketcher fixes: browser events alias, mixed CommonJS transformation, globalThis mapping.
- Desktop appearance: graphite palette and left analysis navigation inspired by the supplied screenshot.
- COX-2 pilot model trained; see MODEL_VALIDATION_REPORT.md. Model installed locally under the Windows user's AppData/Roaming/chemanalyzer/models directory; it is not embedded in the installer or committed to Git.

## Limitations

- Automatic execution of the frozen backend smoke-test command was rejected by the tool policy (blocked by policy). Frozen backend/installer runtime is not verified.
- No clean Windows machine test or installation acceptance test has been completed.
- No signing certificate is configured.
- Dependency audit findings and miew-react peer compatibility concerns remain documented in AUDIT_REPORT.md.
- Mobile viewport still has horizontal overflow; desktop is the target platform.
- Browser integration testing redirected API requests to the local source backend on port 8876; it is not an Electron runtime test.
- No antidote or plant-growth model was trained without suitable experimental data.

Build commands used Python 3.12 from backend/.venv and Node 24.22.1. npm was provided through a workspace-local wrapper because it is not installed globally. The original PowerShell convenience script still expects a system Python launcher and npm.
