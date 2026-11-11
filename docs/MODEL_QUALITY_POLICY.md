# Model admission policy, 2026-11-10

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
- Regression: held-out R² **strictly > 0.60** and MAE below the baseline. R² is an
  explained-variance score, not a percentage of correct predictions. Units and
  baseline errors remain visible. These thresholds are admission criteria, not
  guarantees for new molecules.
- Review, activation and prediction recompute the policy, including older
  artifacts. A previous approval cannot bypass current evidence requirements.
  Existing user artifacts are preserved. Numerical values are withheld outside
  the heuristic applicability domain.
- Internal CV and internal held-out tests remain explicitly distinct from
  independent external or prospective validation; none is claimed here.

## Current coverage

| Application system | Evidence / status |
| --- | --- |
| Target QSAR, human COX-2 IC50 | Real ChEMBL 37 model, 2,776 unique compounds; 5-fold scaffold CV balanced accuracy 0.7081, ROC-AUC 0.7867, MCC 0.4160, randomized AUC 0.4913. Internal CV only; no external/assay-held-out test. |
| Hydration free energy | Real FreeSolv data; updated split and model evaluated separately in the release report. Experimental; not antidote or plant activity. |
| Antidote: acetaminophen rescue | No eligible curated training table has been integrated. Remains not_trained. General liver toxicity is not an antidote label. |
| Arabidopsis primary-root growth/control | No eligible curated training table has been integrated. Remains not_trained. Auxin receptor binding is not root growth. |
| Antibacterial and general antiviral/cytotoxicity | Broader organism/strain/cell-line and exposure-specific datasets still required; the two narrow screening tasks below do not validate these general claims. |
| HIV replication, NCI/MoleculeNet | Experimental classifier, 38,027 accepted molecules; internal held-out balanced accuracy 65.50%, ROC-AUC 0.7614. Recall only 32.07%; no external validation. |
| HepG2 proliferation decrease, 24 h | Experimental single-assay ToxCast classifier, 924 accepted molecules; internal held-out balanced accuracy 71.25%, ROC-AUC 0.7704. No clinical toxicity claim or external validation. |
| CYP inhibition | Version 3.2.3 adds five separate TDC/Veith models; internal held-out balanced accuracy 72.76–78.62%. Full evidence and class-specific limitations: CYP_VALIDATION_3.2.3.md. No external validation. |
| Human liver microsomal stability >30 min | Version 3.2.6 adds one NCATS AID 1963597 classifier: internal held-out balanced accuracy 71.25%, ROC-AUC 0.7441, stable recall 65.69%, positive predictive value 80.72%. 171 test compounds; experimental, no external validation. See HLM_VALIDATION_3.2.6.md. |
| Quantitative in-vitro half-life, other metabolic systems, general toxicity | Separate endpoint datasets and validation required. No validated predictions claimed for these broader endpoints. |
| Gene expression, publication entity extraction | Planned pipelines without trained artifacts. |
| Activity spectrum | Tanimoto nearest-drug comparison; structural similarity, not calibrated biological prediction. No accuracy percentage is assigned. |
| ADME profile, drug-likeness | RDKit descriptors, rules, ESOL/BOILED-Egg estimates. Deterministic rules and empirical estimates are labelled by method; no blanket >60% prediction claim. |
| 3D molecule/protein viewer | Conformer generation and structure visualization; evaluate geometry/provenance, not classification accuracy. |
| Literature assistant | Requires configured API access; generated text needs source checking and is not QSAR validation. |
| PubChem, ChEMBL, registry, history | Data retrieval/storage: availability, exact identity, provenance and failure handling are relevant; model accuracy does not apply. |

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

Primary references:
- https://scikit-learn.org/stable/modules/generated/sklearn.metrics.balanced_accuracy_score.html
- https://chembl.gitbook.io/chembl-interface-documentation/web-services/chembl-data-web-services
- https://github.com/MobleyLab/FreeSolv
