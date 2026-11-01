# Architecture overview

ChemAnalyzer 3.2.0 is a local-first Windows desktop application with a React frontend, Electron shell, and Python/FastAPI backend.

## High-level components

```text
┌──────────────────────────────────────────────────────────────┐
│                       Electron desktop                       │
│  main process · preload · secure IPC · app lifecycle          │
└─────────────────────────────┬────────────────────────────────┘
                              │ launches / monitors
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                      FastAPI backend                          │
│  API routes · configuration · local data/model access         │
└───────────────┬───────────────────────┬──────────────────────┘
                │                       │
                ▼                       ▼
┌──────────────────────────┐  ┌────────────────────────────────┐
│ React + TypeScript       │  │ Chemistry services             │
│ Vite · Ketcher · 3D view │  │ RDKit · descriptors · ADME     │
│ analysis tabs · exports  │  │ fingerprints · conformers      │
└──────────────────────────┘  └────────────────────────────────┘
                │                       │
                └───────────┬───────────┘
                            ▼
               External data / optional AI
               PubChem · ChEMBL · AlphaFold · Anthropic
```

## Main directories

| Path | Responsibility |
|---|---|
| `electron/` | Desktop window, backend process lifecycle, preload bridge, secure IPC, local state handling, and Electron tests. |
| `frontend/src/` | React and TypeScript interface, tabs, editor integration, visualization, history, and export features. |
| `frontend/scripts/` | Copies Ketcher static assets from the installed package before dev/build. |
| `backend/app/api/` | FastAPI routes for molecule analysis, identification, ChEMBL, assistant, and protein structures. |
| `backend/app/chemistry/` | RDKit-based descriptors, fingerprints, drug-likeness, ADME, conformers, and activity calculations. |
| `backend/training/` | Training utilities and empty endpoint-specific CSV templates for specialized activity models. |
| `scripts/` | Development orchestration, icon generation, and Windows build scripts. |
| `.github/workflows/` | GitHub Actions workflow for manually triggered or tag-triggered Windows builds. |

## Backend API map

The molecule router is mounted at `/api/molecules`:

| Endpoint | Purpose |
|---|---|
| `POST /api/molecules/analyze` | Local RDKit analysis and molecular descriptors. |
| `POST /api/molecules/identify` | PubChem identification with explicit match status. |
| `POST /api/molecules/validate` | Validate SMILES and return canonical structure information. |
| `POST /api/molecules/activity` | Reference similarity, drug-likeness, and available QSAR result. |
| `POST /api/molecules/chembl` | Retrieve available ChEMBL activity data. |
| `POST /api/molecules/conformer` | Generate a small-molecule 3D conformer. |
| `POST /api/molecules/depict` | Render a 2D structure as SVG. |
| `POST /api/molecules/adme` | Calculate selected ADME-related descriptors and heuristic outputs. |
| `POST /api/molecules/specialized-activity` | Query endpoint-specific antidote/growth-regulating model status or results. |

Additional routes include `/api/assistant/*`, `/api/structure/*`, `/api/app/info`, and `/health`.

## Data and network boundaries

- **Local calculations:** the core RDKit descriptor calculation runs in the backend and does not depend on PubChem or ChEMBL being reachable.
- **Online resources:** PubChem, ChEMBL, and AlphaFold Protein Structure Database require network access; availability is controlled by those services.
- **Optional assistant:** Anthropic is only used when a valid local API key is configured. The key belongs in local environment configuration, never in the repository.
- **User data:** the packaged desktop application stores application state and optional models in the user-data directory documented in `DESKTOP_BUILD_GUIDE.md`.
- **Models and datasets:** trained models and private data are not source-controlled by default. Their provenance, license, endpoint, and validation status must be documented before any public distribution.

## Scientific interpretation

The interface presents computed descriptors, database records, similarity comparisons, and model-based estimates. These have different meanings and confidence levels. Similarity is not an activity probability. QSAR output depends on the training set and applicability domain. ADME/drug-likeness outputs are not medical conclusions. The specialized Antidote-Prediction module ships without trained models or experimental datasets and must not be used to guide treatment or real-world substance handling.
