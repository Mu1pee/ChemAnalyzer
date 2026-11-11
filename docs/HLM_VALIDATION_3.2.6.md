# ChemAnalyzer 3.2.6: human microsomal stability

Checkpoint: 2026-11-11. One separate NCATS HLM stability classifier passes the
current admission policy and remains **experimental and unapproved**. The
positive class means a stable phenotype, T½ >30 minutes, under the source assay.
It is not a quantitative half-life, clearance, clinical or antidote prediction.

## Primary data and curation

Source: NCATS/NIH, PubChem AID 1963597, NCGC external ID ADME-HLM1,
version 1 revision 1. We use the public 900-compound subset, not the authors'
full 6,648-compound dataset or their published trained model. Original
depositor SMILES, SID and CID are retained. No downloaded model or rat-stability
prediction is used as a feature.

The source lists 542 stable and 358 unstable compounds. PubChem Active,
phenotype Stable and NCATS Class=0 map to this model's positive class Y=1;
Inactive, Unstable and Class=1 map to Y=0. All three annotations were
cross-checked against the reported half-life. No record lies exactly at the
30-minute boundary. Such a boundary, disagreement, new row count, protocol
change or changed raw-file hash requires renewed review rather than relabelling.
Values reported at 120 minutes may be capped; they are not treated as exact
continuous regression targets.

The assay is human liver microsomal substrate depletion with a 1 µM test
article, 0.5 mg/mL HLM, NADPH, pH 7.4, 37°C, and source sampling through 60
minutes. Other species, clinical half-lives, intrinsic-clearance units and CYP
inhibition are not pooled. Preparation rejects multi-fragment, invalid or
oversized structures: 48 structure errors, leaving 852 accepted molecules.
No duplicate or conflicting-label exclusions were necessary in this snapshot.

Raw source CSV SHA256:
`9e941510888f92efc4eeb7cc455acc4329717636dcc0b2e2b4ab52b23a08a010`.
Prepared CSV SHA256:
`ddfe4b6f4b98062f071cd23b18b15b35b2d5a87812ff200823b00fce926af145`.
Description SHA256:
`7bfa9fe32ee335ae324411df22a928cfa0b4e6cdee861c310a038a01166ed159`.

## Rights and attribution

These are federal NCATS-authored assay records deposited by NCGC. The NCBI
policy places US-government-created information in the public domain and
distinguishes third-party contributions. No source-specific exception is
indicated in this assay. Provenance records **Public-Domain-US-Gov**, not an
invented CC0 dedication or a blanket public-domain assertion for PubChem.
The source policy, metadata and original bytes are retained. The related
article separately states CC BY 4.0.

Attribution: NCATS/NIH; PubChem AID 1963597 (ADME-HLM1); Shah, Siramshetty,
Mathé and Xu (2024), doi:10.3390/pharmaceutics16101257. The provided curated
table and newly trained model weights are distributed under CC BY 4.0 with
source attribution. This does not imply government endorsement or change the
license of original ChemAnalyzer code.

## Fixed experiment and quality

Fixed seed 42; Morgan radius 2, 1,024 chiral fingerprint bits and six RDKit
descriptors. Whole Murcko scaffolds are disjoint across all three partitions;
acyclic molecules share one group. Train-only three-fold grouped CV tunes the
predeclared candidates; validation quality and PR-AUC select Random Forest.
The decision threshold is 0.5. The held-out test is evaluated afterwards,
without seed, threshold or model selection on test scores.

| Partition | Molecules | Scaffolds | Stable | Unstable |
| --- | ---: | ---: | ---: | ---: |
| Train | 545 | 374 | 322 | 223 |
| Validation | 136 | 136 | 87 | 49 |
| Test | 171 | 171 | 102 | 69 |

| Held-out metric | HLM model | Always-stable baseline |
| --- | ---: | ---: |
| Balanced accuracy | **71.25%** | 50.00% |
| ROC-AUC | 0.7441 | 0.5000 |
| PR-AUC | 0.8196 | 0.5965 |
| Stable recall | 65.69% | 100.00% |
| Stable positive predictive value | 80.72% | 59.65% |
| F1 | 0.7243 | 0.7473 |

The model improves balanced accuracy, ROC-AUC, PR-AUC and positive predictive
value, but does not improve every metric: its F1 is lower than an always-stable
baseline in this test. Class-specific tradeoffs remain visible in the UI.
Whole-scaffold percentile bootstrap, 1,000 replicates, seed 20261111: 95%
balanced-accuracy interval **64.36–77.82%**, conditional on this trained model
and public subset. No external/prospective validation or probability calibration
has been completed. The heuristic applicability check hides numerical outputs
outside the domain. Passing this gate is not a guarantee for a new molecule.

Model: `1862e76cebf14f81b353a45c2fab9326`;
run: `d312fc976dff4edcaa4795eed9df0351`;
task: `d68327d3ab704303a86d7d5d8a880018`.

Reproduce from backend:
`python -m training.train_screening --assay hlm --output-dir <fresh-directory>`.
The source adapter pins the reviewed snapshot and rejects overwriting previous
experiment folders. Full source, features, split indices, artifacts, preparation
issues and provenance accompany the release data archive. A model review and
approval are not automatically fabricated.

## Application scope

The new metabolic-stability screen displays the stable-phenotype probability,
balanced accuracy, ROC/PR-AUC, recall, positive predictive value and test class
counts. A separate quantitative in-vitro half-life entry still requires suitable
measurements. Eight prior research models plus COX-2 remain available with their
previous evidence and limitations. The goal of qualifying every system remains
unfinished: APAP rescue, Arabidopsis primary-root and other untrained endpoints
are not validated by this HLM classifier.

The backend suite passes 221 tests and the production frontend build passes.
The packaged Windows app passed model-loading, in-domain inference, withheld
out-of-domain values, stable/unstable labels and metric display with no renderer
errors. The frozen backend reimported all 900 records with the exact prepared
CSV hash. The actual Portable EXE was verified through the same running process
after its initial combined 90-second test observation expired during cold
extraction/startup. First Portable launch may be slow. The standard archive
payload avoids NSIS's four-minute direct-file compilation limit. Detailed
Windows verification results are retained separately. Builds are
unsigned; clean-machine Setup installation has not been verified.

Primary references:

- https://pubchem.ncbi.nlm.nih.gov/bioassay/1963597
- https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/aid/1963597/CSV
- https://www.ncbi.nlm.nih.gov/home/about/policies/
- https://doi.org/10.3390/pharmaceutics16101257
- https://opendata.ncats.nih.gov/adme/models/hlm
