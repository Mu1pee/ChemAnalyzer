# ChemAnalyzer 3.2.7: model admission and application resilience

Date: 2026-11-11. This release preserves the scientific datasets, trained weights,
test partitions and endpoint definitions shipped in 3.2.6. It does not claim new
training, external validation or completion of the overall model-quality goal.

## Corrected failures

- Active research models previously used the hash of concatenated endpoint and
  context strings. Different pairs could share that concatenation. New pointers
  hash an unambiguous JSON pair. Legacy pointers are accepted only after matching
  both fields against the referenced approved model. No model is auto-approved.
- Nonfinite, fractional, Boolean or inconsistent support counts could bypass or
  crash admission checks. Policy 2026-11-11 rejects those counts, malformed
  evidence and unsupported tasks. Classification remains balanced accuracy
  strictly above 0.60 and ROC-AUC at least 0.70; regression requires R² above
  0.60 and MAE better than its baseline. R² is not percent accuracy.
- One damaged metadata record previously prevented listing all models and could
  disable otherwise valid screening/CYP endpoints. Damaged records now appear
  as invalid, with prediction disabled; the original file is preserved. Direct
  model access still rejects the record. Non-standard JSON NaN/Infinity values
  are rejected before serialization. No arbitrary model file is downloaded.
- A corrupt schedule policy/state or failed state write could stop the scheduler
  daemon and subsequent schedules. Each schedule now has a separate failure
  boundary. Corrupt state is preserved, never treated as permission to retrain.
- Interrupted initial copying of a bundled model could leave a partial UUID
  directory that later launches skipped. A record is now copied into a temporary
  sibling and renamed after successful completion. Existing records are preserved.
- Electron uses parsed exact origins for navigation, IPC, CSP and origin-specific
  permissions. Packaged production ignores the development URL environment
  override. Windows reserved device names with multiple extensions are sanitized.

## Software and scientific checks

- Backend: **276 pytest tests passed**. They include strict >60% boundaries,
  malformed support/evidence, endpoint/context collision and legacy lookup,
  independent schedule failures, corrupt-registry API responses and continued
  inference from unaffected endpoints. Artificial test fixtures are software
  checks only; they are never biological training data.
- Electron: **20 tests passed**, including exact-origin rejection, interrupted
  seed-copy retry and existing-user-record preservation.
- Frontend: TypeScript and Vite production build passed. Existing large-bundle
  and third-party 3Dmol eval warnings remain; dependencies were not upgraded.
- All **nine research artifacts** passed the current policy. The original test
  predictions and all reported metrics were recomputed from the fixed bundled
  model and stored features. Reported partition support was independently counted;
  complete coverage and scaffold disjointness were checked. Artifact SHA-256
  values were verified and the weights remained unchanged. This is a software
  reproduction of existing internal evidence, not a new external test.

| Fixed endpoint | Internal held-out result |
| --- | --- |
| CYP1A2 inhibition | Balanced accuracy 78.62% |
| CYP2C9 inhibition | Balanced accuracy 75.53% |
| CYP2C19 inhibition | Balanced accuracy 75.32% |
| CYP2D6 inhibition | Balanced accuracy 72.76%; recall 53.80% |
| CYP3A4 inhibition | Balanced accuracy 74.67% |
| HIV replication inhibition | Balanced accuracy 65.50%; recall 32.07% |
| HepG2 proliferation decrease, 24 h | Balanced accuracy 71.25% |
| Human microsomal stability >30 min | Balanced accuracy 71.25%; stable recall 65.69% |
| FreeSolv hydration free energy | R² 0.7290; MAE 1.2220 kcal/mol |

The separately bundled human COX-2 model retains internal scaffold-CV balanced
accuracy 70.81%; it is not one of the nine held-out Research Agent models.
Source rights and experimental contexts remain those documented in
CYP_VALIDATION_3.2.3.md, SCREENING_VALIDATION_3.2.4.md, HLM_VALIDATION_3.2.6.md,
VALIDATION_3.2.2.md and QSAR_VALIDATION_3.2.1.md. No new weights or training rows
were generated in 3.2.7. All research models remain experimental.

Acetaminophen rescue and Arabidopsis primary-root growth/control remain
**not_trained**. The bounded source review is recorded separately in
ENDPOINT_DATA_AUDIT_2026-11-10.md. Reporter, miRNA, general liver-toxicity and
target-binding outcomes are not substituted for those requested labels.

## Windows verification scope

The native packaged application started on this Windows computer as 3.2.7 with
nine qualified research models and the separate COX-2 bundle. All eight research
classification endpoints retained their model identities and metrics; helium
queries withheld outside-domain values. A deliberately malformed record was
added only to an isolated test profile. It appeared as invalid with prediction
disabled; the other screening/CYP models remained available and the malformed
file remained unchanged. No renderer errors were observed. A development URL
override did not redirect the packaged application away from its local origin.

A fresh live aspirin ChEMBL query completed in **10.75 seconds** and identified
CHEMBL25 with eight similar compounds. The result was explicitly **partial**:
upstream mechanism and activity endpoints returned HTTP 500, leaving no target
activity rows in that response. This verifies useful partial retrieval and
correct failure disclosure, not full upstream availability or lack of activity.

Final EXE checks and release artifact digests are recorded in the accompanying
verification JSON files and SHA256SUMS.txt. No signing certificate is configured;
the EXEs are unsigned. The actual Portable EXE also started successfully with
nine qualified research models; first-launch extraction and checks took 88.29
seconds on this computer. The test application was closed afterwards.
No clean-machine Windows installation, SmartScreen bypass
or prospective biological validation is claimed. Actual upstream ChEMBL failures
remain possible; a bounded partial/unavailable response is not a negative assay.
