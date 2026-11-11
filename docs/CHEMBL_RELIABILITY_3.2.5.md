# ChemAnalyzer 3.2.5: trustworthy ChEMBL failure states

Checkpoint: 2026-11-11. A partial ChEMBL response must never be interpreted as
proof that a molecule is absent. Earlier UI logic could show a no-hit notice
and hide the partial-response message when exact search failed but similarity
search returned an empty successful list. The UI now retains the failure message
and shows a no-hit fallback only for a complete, fresh response without a more
specific server message. A stale empty cache is explicitly dated and does not
claim current absence.

HTTP 200 alone also does not prove success. A JSON error object without the
expected resource collection is now rejected as `invalid_response`. Empty valid
collections remain distinct from failures. For molecule/similarity, mechanisms,
indications, activities and targets, the corresponding collection must be a list.

The 22-second per-attempt limit, shared 55-second deadline, bounded retries,
verified TLS and timestamped cache remain in place. Comparing the two officially
documented exact-lookup routes during this audit produced HTTP 500 from both
in approximately 4.9 seconds; switching routes alone would not solve that outage.
Neither TLS verification nor server access controls were bypassed.

The backend suite passes 208 tests, including the new distinction between an
empty similarity result with failed exact search and a complete no-hit result,
and rejection of HTTP-200 error envelopes. The Windows verification report
records the packaged UI checks and the observed live service result separately
from deterministic software fixtures. Fixtures are never training data.

The final unpacked Windows application passed all four UI-state checks with no
renderer errors. Its fresh live aspirin request returned CHEMBL25 in 54.93
seconds, explicitly partial: similarity, activity and indication requests
received HTTP 500, and mechanism lookup timed out. This is useful partial
retrieval, not a claim that every EBI endpoint was available. The TLS resource
was present, all eight research models loaded, and model/domain checks passed.

This patch does not retrain or change model weights. The eight Research Agent
models and COX-2 QSAR from version 3.2.4 remain experimental with their existing
evidence and limitations. See SCREENING_VALIDATION_3.2.4.md and
MODEL_QUALITY_POLICY.md. The dataset/model archive remains available with the
3.2.4 release: https://github.com/Mu1pee/ChemAnalyzer/releases/tag/v3.2.4 .

Further primary-root source review is recorded in ENDPOINT_DATA_AUDIT_2026-11-10.md.
The Microphenotron article describes a potentially relevant screen, but the full
dataset requires an author request. Aggregate hit counts and qualitative root
traits were not converted into invented quantitative length/control labels.
The all-systems quality goal is still incomplete; APAP-rescue and primary-root
models remain not_trained.

Windows x64 Setup and Portable artifacts are unsigned. A clean-machine Setup
installation has not been verified. Public release assets have SHA256 checksums.

Primary API reference:
https://chembl.github.io/using-new-chembl-web-services/
