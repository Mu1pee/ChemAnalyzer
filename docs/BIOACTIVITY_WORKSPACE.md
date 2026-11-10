# Bioactivity workspace checkpoint

Implemented 2026-11-09; Windows packaging verified separately on 2026-11-10.

## Implemented

- 21 catalog entries in pharmacology, ADMET, scientific analysis and data sources.
- Search, category and availability filters, empty states, missing-model details, keyboard dismissal and JSON registry export.
- Existing molecule analysis, ADME, drug-likeness, QSAR, specialized activity, 3D, history and assistant remain accessible.
- Separate ResearchAgent task presets for antibacterial/antiviral activity, cytotoxicity, CYP, metabolic stability, toxicity and Arabidopsis primary-root regression. Presets do not constitute datasets or trained models.
- Registry count distinguishes experimental artifacts from approved models. Artifact availability is read from the backend.
- Production browser API uses the serving origin by default; Electron bridge and explicit environment overrides retain priority.
- Optional research Portable build seeds UUID-addressed experimental task/run/model records without overwriting existing user records. It enables the local lab for that build only; explicit CHEMANALYZER_RESEARCH_ENABLED=0 overrides it. No schedule or automatic model approval is added.

## Real training performed

ResearchAgent trained one fresh FreeSolv experiment: 642 experimental rows, 399/91/152 train/validation/test. Gradient Boosting selected from Random Forest, Ridge and Gradient Boosting using train CV and validation. Held-out MAE 1.320710 kcal/mol, RMSE 1.704218, R2 0.692881; dummy baseline MAE 2.905546. Model d8c60aaa21d54519a5a2692df399e823 remains experimental and unapproved.

License: FreeSolv CC BY 4.0, revision 6c7d19b4b565537365ffd22006aa2cd4643200c6. The test set has only one scaffold group; these results do not establish generalization across diverse chemistry. This is hydration-energy regression, not biological activity or a validated ADMET suite. Re-running this benchmark adds no independent scientific confirmation.

## Unsupported / data needed

PASS/Way2Drug models and their Pa/Pi scores are not included, recreated or scraped. No artificial Pa/Pi values are generated. The screenshots informed category organization only; brand logos and proprietary services were not copied.

Antibacterial, antiviral, cytotoxicity, CYP, metabolism and toxicity require reviewed endpoint-specific data. Antidote ResearchAgent tasks remain catalog/report-only under the existing agent policy; the dedicated specialized trainer is separate. The preset does not bypass that restriction. Arabidopsis tasks require actual primary-root measurements; a source library size does not supply experimental labels.

Existing Claude assistant still requires a configured key. Gene-expression prediction and chemical-entity extraction from papers are planned entries, not implemented pipelines.

## Verification

- Full Python suite: 146 passed.
- Full Electron suite including the new seeding preservation test: 18 passed.
- TypeScript/Vite production build passed.
- Playwright/Edge: 21 entries, filter/search/empty states, Escape dismissal, real growth-task creation, JSON export, Ketcher ethanol analysis and 1440/768/390 viewport checks passed. No page JavaScript errors or document horizontal overflow.
- Fresh frozen backend: health, research registry, ethanol calculation and experimental-model prediction succeeded on Windows.
- Packaged Electron (fresh isolated user profile): strict CSP startup, all 21 entries, seeded experimental model, real frozen-model prediction and Ketcher ethanol analysis passed; zero renderer page errors. This was the unpacked application used to generate the Portable, not a clean-machine installation test.
- Dev-server mode encountered an existing process global dependency in Ketcher's Node compatibility dependencies; production rendering is the verified route.
- Windows clean-machine installation, all external services and all exports have not been exhaustively tested in this change.

## Reproduce the optional Portable

Build frontend and PyInstaller backend into build/bioactivity-backend first. Set CHEMANALYZER_RESEARCH_SEED_DIR to a reviewed ResearchAgent root containing tasks/runs/models and source-license evidence, then run:

```powershell
node node_modules/electron-builder/cli.js --win --x64 --config electron-builder.research.cjs
```

No certificate is configured. Ordinary build configuration remains unchanged; research artifacts and source datasets are excluded from Git.

Produced Portable: ChemAnalyzer-Bioactivity-3.2.0-Portable.exe, 744874569 bytes. SHA256: 48E6AA01DB91B085F099E83F88F76F126036596A684AB7943FD1B7451D003EB3. The output copy was hash-verified; a copy is also on the desktop. No public GitHub release was created.
