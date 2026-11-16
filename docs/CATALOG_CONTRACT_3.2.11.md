# ChemAnalyzer 3.2.11 — catalog model admission

Date: 2026-11-16.

The catalog previously matched registry records by endpoint alone, whereas
CYP and screening inference required exact context, kind, domain and units as
well. This could label an incompatible or failed model available. The FreeSolv
card also prepared an admet-domain task while the historical reviewed artifact
uses the default qsar domain.

## Current behavior

- A read-only `/api/molecules/capabilities` endpoint reports catalog states from
  backend admission. CYP and screening inference use the same task selector.
- A model must match all five scientific task fields, be non-archived and pass
  recomputed quality. Human approval, then recency, controls selection. Test
  scores never choose a deployment candidate.
- The selected artifact SHA-256 is verified without unpickling weights during
  the catalog check. Loading and molecule-specific applicability are checked
  during inference. A failed selected artifact is an error; an older artifact
  is not silently substituted.
- Cards distinguish experimental, validated, approved, partially available,
  not-trained, quality-failed, incompatible, archived and error states. Failed
  status retrieval is unknown availability, not an untrained-model claim.
- QSAR and antidote/growth cards use their actual inference loaders and quality
  gates. A generic research record with a similar endpoint cannot enable a
  separate specialized predictor.
- FreeSolv task preparation matches the stored source contract, including its
  historical qsar domain and regression/kcal/mol context. No artifact is
  relabeled or refit. The ADMET catalog grouping is a user-interface grouping.
- Local CYP/screening inference remains visible when the optional training lab
  is disabled. FreeSolv prediction uses the gated lab route, so its catalog
  state is disabled until the lab is enabled. The API and catalog share the
  same opt-in check; a present artifact does not bypass it.

## Real-artifact verification

The current nine reviewed artifacts were queried through the capabilities API
with current quality recomputation and checksum verification. All are
experimental, none is human-approved: five Veith CYP inhibition models, one
NCI/MoleculeNet HIV replication model, one ToxCast HepG2 proliferation model,
one NCATS human microsomal-stability model and one FreeSolv regression model.
Detailed context and artifact-check evidence is retained in the release
verification report. The check does not refit or relabel these artifacts.

COX-2 remains quality-failed under its fixed held-out validation requirement.
Acetaminophen-rescue and Arabidopsis primary-root-length models remain
not-trained without eligible complete experimental data. No new model,
artificial biological label or quality score is introduced by this release.

## Software and Windows evidence

356 backend tests passed with no skipped tests, failures or errors; the local
JUnit report is retained. Frontend TypeScript and production builds passed.
The packaged Windows app verified real catalog states, FreeSolv inference and
task preparation, the available-only filter, rejection of a wrong-context
metadata fixture claiming 99%, and unknown availability after a network error.
Network-only UI fixtures were not stored as scientific artifacts.

The actual Portable EXE was tested with the lab explicitly disabled. FreeSolv
was unavailable, while five CYP and three screening models loaded and served
prediction requests. Portable verification, including extraction and checks,
took 109.682 seconds on this computer. No model was trained or activated during
these checks. The Windows installer was built but not installed in this check;
both executables are unsigned.

A separate fresh ChEMBL check on 2026-11-16 returned aspirin CHEMBL25 with
655/655 activity rows over two pages in 7.672 seconds, without cache or
warnings. This is a current successful observation, not a guarantee of upstream
service availability.
