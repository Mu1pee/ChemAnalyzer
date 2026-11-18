# Model admission policy (ChemAnalyzer 3.2.16, updated 2026-11-18)

The requested goal is quality above 60% for every predictive system. A feature
catalog is not evidence of an implemented or trained model. This release does
not claim that all catalog entries meet that goal.

## Admission and evidence

- Binary classification: balanced accuracy **strictly > 0.60**, ROC-AUC >= 0.70,
  on structures excluded from fitting. Conventional accuracy is insufficient on
  imbalanced data. QSAR target models retain their stricter ROC-AUC >= 0.75,
  MCC >= 0.25, >= 30 compounds/class and Y-randomization checks. Specialized
  classifiers retain MCC >= 0.10 and >= 5 scaffolds/class before training.
- Complete out-of-fold predictions are required for scaffold cross-validation.
  A missing metric, NaN, infinity, failed fold or absent randomization result
  cannot count as a pass. Similarity and prediction probability are not accuracy.
- Research Agent: candidate selection uses train CV and validation; the test is
  evaluated afterwards. At least 20 test molecules and 3 distinct scaffold groups
  are required; classifiers also require >= 10 test compounds/class. Every
  partition reserves at least 3 entire groups using group sizes only.
  Support counts must be finite nonnegative integers; scaffolds cannot exceed
  molecules and the two class counts must sum to the test molecule count.
- Regression: held-out R² **strictly > 0.60** and MAE below the baseline. R² is an
  explained-variance score, not a percentage of correct predictions. Units and
  baseline errors remain visible. These thresholds are admission criteria, not
  guarantees for new molecules.
- Review, activation and prediction recompute the policy, including older
  artifacts. A previous approval cannot bypass current evidence requirements.
  Existing user artifacts are preserved. Numerical values are withheld outside
  the heuristic applicability domain.
  Malformed evidence fails closed. Unreadable model records are shown as invalid
  in the research registry and excluded from inference; other records remain
  available. Existing records are not deleted or silently repaired.
- Internal CV and internal held-out tests remain explicitly distinct from
  independent external or prospective validation; none is claimed here.

Policy version 2026-11-16 also requires classifier test PR-AUC and baseline
PR-AUC to be finite numeric values in [0, 1], with strict improvement. PR-AUC
in the Research Agent is average precision, as computed by its evaluator.
The stored `beats_baseline` flag alone cannot establish this comparison.
Missing, malformed, equal or worse baseline evidence prevents review,
activation and prediction. Existing valid numerical evidence needs no refit;
the nine reviewed classifiers and FreeSolv regressor retain their artifacts.

Target QSAR source schema 3 additionally records the original assay organism,
BAO format, cell/tissue/fraction and variant annotations. A human single-protein
target or a Binding (B) assay type alone cannot establish a single-protein
experimental format. The current profile excludes incompatible or unknown
formats, cellular/tissue/fraction contexts and reported variants. Descriptions
mentioning blood require separate protocol review even when structured fields
say single protein. Both acquisition/revalidation paths use the same context
check, which is recomputed during artifact admission. Source descriptions and
the exact contributing assay IDs remain in provenance; catalog-compatible and
actually contributing assay counts are recorded separately. This does not
establish identical substrates, detection methods or exposure conditions.

## Specialized binary training, version 3.2.8

The acetaminophen-rescue and Arabidopsis primary-root binary trainer now requires
a schema-2 protocol sidecar with CSV SHA-256, exact endpoint/context, organism,
profile-specific conditions, class definition and experimental-source/license
declaration. Missing source outcomes cannot be treated as inactive. The protocol
is a curator declaration and does not establish independent review by itself.

Fixed candidates fit train only; validation selects the candidate using PR-AUC
after validation quality gates. The selected object is tested once and retained
without refitting. Its test must pass balanced accuracy >0.60, ROC-AUC >=0.70,
MCC >=0.10 and beat the prior baseline in PR-AUC. Fitted support requires 30
compounds and five scaffolds/class; validation needs five compounds/class and
test ten/class. Disjoint partition indices and complete support are checked again
at loading, along with protocol, feature schema and artifact SHA-256.

CV-only legacy specialized artifacts stay on disk but cannot generate predictions
without retraining under this contract. All acyclic structures share one split
group; mixtures require explicit curation. This binary path does not produce
continuous rescue or root-length ratios. Both requested specialized endpoints
remain not_trained until eligible real data and a passing model are available.

The 2026-11-16 official-source audit retrieved complete results for its bounded
PubChem/ChEMBL queries and retained a review-only measurement packet. It found
no eligible table for these two endpoints; different assays or mirrored database
records were not pooled to inflate support. Fitting 30 compounds/class plus
validation five/class and test ten/class implies a necessary lower bound of 90
distinct curated compounds, with fixed-split scaffold/class support still
required. See SPECIALIZED_SOURCE_AUDIT_2026-11-16.md and its hashed inventory.

A subsequent review expanded the PubChem union to 2,983 IDs, with 2,981
available summaries and two explicit 404s. It also downloaded and verified all
17 workbooks in Mendeley Data 10.17632/jzd9mnsx8t.1. Their four named APAP
interventions are selected follow-ups, not a full training set; CIL56/ConA
results were not relabeled as APAP rescue. Both specialized templates remain
empty and both models remain not_trained. See
[ENDPOINT_DATA_REVIEW_2026-11-16.md](ENDPOINT_DATA_REVIEW_2026-11-16.md).

## Current coverage

Catalog availability in 3.2.11 is provided by the backend, using the same exact
endpoint/context/kind/domain/units match and approval/recency selection as
CYP/screening inference. Quality is recomputed from current metadata and the
selected artifact checksum is checked. A matching endpoint alone, an archived
record or a failing model cannot enable a catalog card. Availability describes
this admission and integrity check; model loading and the molecule-specific
applicability domain are checked again during prediction. It is not external
validation or human approval. See CATALOG_CONTRACT_3.2.11.md.

| Application system | Evidence / status |
| --- | --- |
| Target QSAR, human COX-2 single-protein IC50 | Version 3.2.15: source-context curation retains 2,111 compounds; the exact train-only calibrated RF fits 1,351 and passes a retrospective internal 422-compound scaffold holdout: BA 0.762168, ROC-AUC 0.822185, MCC 0.524005. Bootstrap 95% BA interval 0.711791–0.808532. Previously studied/trained source panel; no new independent external validation. Earlier mixed-context internal AUC 0.733 and external BA 0.567708 remain failed results; the previously evaluated external set was not reused for this experiment. See COX2_CONTEXT_VALIDATION_3.2.15.md and COX2_EXTERNAL_PILOT_2026-11-18_RU.md. |
| Hydration free energy | Real FreeSolv data; updated split and model evaluated separately in the release report. Experimental; not antidote or plant activity. |
| Antidote: acetaminophen rescue | No eligible curated training table has been integrated. Remains not_trained. General liver toxicity is not an antidote label. |
| Arabidopsis primary-root growth/control | No eligible curated training table has been integrated. Remains not_trained. Auxin receptor binding is not root growth. |
| Antibacterial and general antiviral/cytotoxicity | Broader organism/strain/cell-line and exposure-specific datasets still required; the two narrow screening tasks below do not validate these general claims. |
| HIV replication, NCI/MoleculeNet | Experimental classifier, 38,027 accepted molecules; internal held-out balanced accuracy 65.50%, ROC-AUC 0.7614. Recall only 32.07%; no external validation. |
| HepG2 proliferation decrease, 24 h | Experimental single-assay ToxCast classifier, 924 accepted molecules; internal held-out balanced accuracy 71.25%, ROC-AUC 0.7704. No clinical toxicity claim or external validation. |
| CYP inhibition | Version 3.2.3 adds five separate TDC/Veith models; internal held-out balanced accuracy 72.76–78.62%. Full evidence and class-specific limitations: CYP_VALIDATION_3.2.3.md. No external validation. |
| Human liver microsomal stability >30 min | Version 3.2.6 adds one NCATS AID 1963597 classifier: internal held-out balanced accuracy 71.25%, ROC-AUC 0.7441, stable recall 65.69%, positive predictive value 80.72%. 171 test compounds; experimental, no external validation. See HLM_VALIDATION_3.2.6.md. |
| Low kinetic aqueous solubility, pH 7.4, <=10 ug/mL | Version 3.2.12 adds one NCATS AID 1645848 classifier: 2,435 accepted molecules; internal held-out balanced accuracy 78.20%, ROC-AUC 0.8492, low-solubility recall 80.57%, precision 77.43%. 487 test molecules/486 scaffold groups; group-bootstrap 95% BA interval 74.48–81.87%. Experimental; not numerical logS, permeability or thermodynamic solubility. See SOLUBILITY_VALIDATION_3.2.12.md. |
| Quantitative in-vitro half-life, other metabolic systems, general toxicity | Separate endpoint datasets and validation required. No validated predictions claimed for these broader endpoints. |
| Gene expression, publication entity extraction | Planned pipelines without trained artifacts. |
| Activity spectrum | Tanimoto nearest-drug comparison; structural similarity, not calibrated biological prediction. No accuracy percentage is assigned. |
| ADME profile, drug-likeness | RDKit descriptors, rules, ESOL/BOILED-Egg estimates. Deterministic rules and empirical estimates are labelled by method; no blanket >60% prediction claim. |
| 3D molecule/protein viewer | Conformer generation and structure visualization; evaluate geometry/provenance, not classification accuracy. |
| Literature assistant | Requires configured API access; generated text needs source checking and is not QSAR validation. |
| PubChem, ChEMBL, registry, history | Data retrieval/storage: availability, exact identity, provenance and failure handling are relevant; model accuracy does not apply. |

The general Research Lab primary-root regression path now also requires a
structured `root_protocol` before importing/preparing/fitting data. It fixes
the species, ecotype, age, dose, exposure, medium, light, control, replicates,
measurement method, ratio normalization and exact CSV checksum. The registry
rechecks this declaration and source/dataset binding even for previously
approved root records. This closes admission based only on free-text context
and numerical scores; no root data or trained artifact are added. See
[ROOT_REGRESSION_PROTOCOL.md](ROOT_REGRESSION_PROTOCOL.md). Binary specialized
sidecars remain a separate contract with their existing gates.

## Additional screening endpoints in 3.2.4

As of 3.2.4, two further separate experimental screening endpoints pass this
policy: NCI/MoleculeNet HIV replication inhibition (balanced accuracy 65.50%,
ROC-AUC 0.7614) and ToxCast HepG2 proliferation decrease at 24 h (71.25%, 0.7704).
Their held-out test sets contain 7,606 and 185 compounds respectively. HIV recall
is only 32.07%, and the interface explicitly discloses this limitation. These
results do not validate general antiviral/cytotoxicity, APAP rescue or plant
growth. Missing ToxCast outcomes are excluded, never inactive. See
SCREENING_VALIDATION_3.2.4.md for source rights, counts, intervals and reproduction.

## ChEMBL reliability

The packaged EXE also had a separate reproducible failure before any request:
the Python runtime's patched `ssl.SSLContext` loads an adjacent public CA
rejection-list file, `codex-rejected-cas.pem`, which was absent from the frozen
bundle. A minimal frozen HTTPS probe reproduced FileNotFoundError in SSLContext
construction. The PyInstaller spec now includes that resource when present in
the build runtime. Verification is retained; no TLS checks are bypassed. The
backend `--check-network` command diagnoses TLS setup and public ChEMBL status.

Before correction, a live aspirin profile took 82.2 seconds. Exact identity and
similarity are now requested concurrently. Transient errors receive one retry;
the profile has a shared 55-second request budget including DNS waits. TLS
verification stays enabled. Logs contain endpoint/error categories, not structures
or response bodies. Partial results are distinguished from absence of a compound.

Successful responses are timestamped and cached locally (24 hours fresh, partial
responses 5 minutes). Up to 128 entries are retained; a saved copy up to 30 days
old can be shown during an outage, explicitly marked stale with its original date.
An unavailable service is never interpreted as lack of bioactivity.

Version 3.2.10 also corrects silent activity pagination truncation. A fresh
3.2.9 transport check returned useful data without warnings in 6.3 seconds,
but an independent source count showed 655 aspirin activity rows versus the
old 500-row cap. This was a successful availability check, not proof of full
activity coverage. Ordered activity pages are now loaded within the shared
55-second budget, at most four pages/2,000 rows. The API and UI retain explicit
retrieved/total counts and completeness. Source-count changes, duplicate IDs,
invalid pagination and later-page failures retain only verified earlier pages
and mark the response partial. Legacy cache entries have unknown coverage and
cannot claim completeness. See CHEMBL_PAGINATION_3.2.10.md.

Live source check after correction: aspirin CHEMBL25, 15 targets, 8 analogs, no
failed sections; 30.12 seconds live, 0.30 seconds from cache on this computer.
External service latency can vary.

On 2026-11-11, the frozen build imported both new TDC sources successfully, but
ChEMBL returned a similarity HTTP 500 and exact-query timeout. An independent
official molecule endpoint returned HTTP 200 in 15.3 seconds, exceeding the old
12-second per-attempt ceiling. Version 3.2.4 raises that ceiling/read timeout to
22 seconds while retaining the shared 55-second deadline, retries, certificate
verification and explicit partial/unavailable states. This does not guarantee
availability of upstream EBI services. The first failed live request is retained
in the release verification evidence.

With the revised limits, a fresh source run retrieved aspirin CHEMBL25, 15
targets and 8 similar compounds in 55.2 seconds; cache retrieval took 0.328
seconds. The response was explicitly partial: EBI returned drug-indication and
mechanism HTTP 500 errors, and target-name lookup exceeded the shared deadline.
This demonstrates recovery of useful data, not universal upstream availability.

Version 3.2.14 retains one complete, dated ChEMBL profile across partial
refreshes. During an outage the app can display this profile with its original
date, activity coverage and a stale-copy notice. Details and source observations
are recorded in [the cache recovery report](CHEMBL_SNAPSHOT_RECOVERY_3.2.14.md).

Primary references:
- https://scikit-learn.org/stable/modules/generated/sklearn.metrics.balanced_accuracy_score.html
- https://chembl.gitbook.io/chembl-interface-documentation/web-services/chembl-data-web-services
- https://github.com/MobleyLab/FreeSolv
