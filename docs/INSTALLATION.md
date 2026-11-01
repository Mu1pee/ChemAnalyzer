# Installation and development

This guide describes the developer workflow for the ChemAnalyzer 3.2.0 source tree. The supplied archive contains source code and build scripts; it does **not** contain a ready-made Windows installer.

## Supported build environment

- Windows 10/11 x64
- Node.js 24.20.0 or newer
- Python 3.12 x64
- Internet access to download npm and Python packages
- Several GB of free disk space for Electron, RDKit, PyInstaller, and build output

The Python requirements include RDKit and scientific Python packages. Use Python 3.12 x64 for the documented Windows build.

## 1. Install root and frontend dependencies

Open PowerShell in the project root (the folder containing the root `package.json`):

```powershell
npm install
npm --prefix frontend install
```

The frontend install is needed for the Vite development server and Ketcher assets. The production build script also installs frontend dependencies as part of its build pipeline.

## 2. Create the Python environment

```powershell
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

## 3. Start the desktop development environment

```powershell
$env:CHEMANALYZER_PYTHON = (Resolve-Path ".\backend\.venv\Scripts\python.exe").Path
npm run dev
```

The development script starts Vite and Electron. Electron launches the local FastAPI backend. Keep the terminal open while developing; use `Ctrl+C` to stop the development processes.

## 4. Optional AI assistant configuration

The assistant is optional. It requires an Anthropic API key, internet access, and an available model configured for the account.

For development, copy the safe template and edit the local copy:

```powershell
Copy-Item backend\.env.example backend\.env
notepad backend\.env
```

Set `ANTHROPIC_API_KEY` in `backend\.env`. Do not paste a real key into source files, README text, screenshots, GitHub Issues, or commits. The `.env` file is excluded by `.gitignore`; verify it is not staged before pushing.

In the packaged desktop application, user-specific configuration and state are stored under `%APPDATA%\ChemAnalyzer\` according to the desktop build guide.

## 5. Build Windows installer and portable package

From the project root:

```powershell
.\scripts\build-windows.ps1
```

The script validates Node.js and Python versions, installs root dependencies, builds the frontend, packages the Python backend with PyInstaller, and runs the Windows packaging step.

Expected output in `dist/`:

- `ChemAnalyzer-Setup-<version>.exe` — NSIS installer
- `ChemAnalyzer-Portable-<version>.exe` — portable package

A successful build is not a substitute for a clean-machine acceptance test. Follow the checklist in `DESKTOP_BUILD_GUIDE.md`, especially the checks for Ketcher, offline local analysis, external services, exports, and process shutdown.

## 6. Tests

From the project root:

```powershell
npm run test:electron
```

For backend tests, use the created Python environment:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests -q
backend\.venv\Scripts\python.exe backend\scripts\selftest.py
```

The complete Windows installer and first-run workflow should still be checked on a clean Windows 10/11 x64 machine before publishing a release.

## Troubleshooting

- **Ketcher assets missing:** run `npm --prefix frontend install`, then retry. The frontend prebuild/predev step copies static Ketcher resources from the installed package.
- **Node version rejected:** install Node.js 24.20.0 or newer and reopen PowerShell.
- **RDKit installation or packaging fails:** use Python 3.12 x64 and recreate `backend\.venv` or `backend\.venv-build`.
- **Assistant unavailable:** check the local `ANTHROPIC_API_KEY`, model availability, network access, and account limits. Core local RDKit analysis does not require the assistant.
- **External data unavailable:** PubChem, ChEMBL, and AlphaFold requests require internet access. The local RDKit descriptor calculation is designed to work without those services.
- **Packaged editor is blank:** follow the Ketcher/CSP troubleshooting section in `DESKTOP_BUILD_GUIDE.md`; the packaged path must be verified on Windows.
