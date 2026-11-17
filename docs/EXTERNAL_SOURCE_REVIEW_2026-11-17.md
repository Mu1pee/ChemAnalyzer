# External data review for COX-2 and Arabidopsis primary-root growth

## Human COX-2

The November 2026 BindingDB exports for journal articles, patents and PubChem
were downloaded and checked against the publisher's MD5 files. A first-chain
match to UniProt P35354 yielded 228, 371 and 0 rows respectively. BindingDB's
article data and patent data were examined separately from records imported
from ChEMBL. The no-match count describes the specified field of this PubChem
export only. BindingDB provides its own curated data under CC BY 3.0.
[Downloads and file descriptions](https://www.bindingdb.org/rwd/bind/chemsearch/marvin/Download.jsp?all_download=yes)
and [source and license information](https://www.bindingdb.org/rwd/bind/info.jsp).

| TSV archive, 202611 | SHA-256 |
| --- | --- |
| BindingDB_BindingDB_Articles | 423609987c3589ca204d59380da7087fe7c67fe0e73b411347e0698ed5fbbdc8 |
| BindingDB_Patents | 1fbe2093cea7a981f0c796010eb350e212d5f532afc2be375def94ea89a015c3 |
| BindingDB_PubChem | cfc270a535f1126f4eb17c66a398d945e22857b1fe53566a5be8902335558885 |

For the literature export, 183 single-chain, wild-type-name, human records
yielded 140 positive-valued exact IC50 measurements in nM. Using the frozen
panel's structure standardization, 126 distinct molecules had consistent
binary labels. Of these, 68 were on 27 scaffolds absent from all 2,740
structures of the previous ChEMBL panel. Their class counts at 1,000 nM were
25 active and 43 inactive. These are structural support counts before protocol
review. The existing COX-2 evaluation requires at least 30 per test class.
[Prior split, thresholds and admission decision](COX2_REVALIDATION_2026-11-11.md).

The November assay and reactant-set mappings resolved 598 of 599 record IDs
to 27 assay descriptions. In particular, the 213 patent rows associated with
assay 1297_1 were linked to a human PTGES experiment despite the P35354 field.
They were excluded from the candidate panel. Another source explicitly reports
human COX-2 experimental values alongside separate ovine COX-1 measurements.
[PTGES patent](https://patents.google.com/patent/US10172814B2/en) and
[human COX-2 assay and table](https://patents.google.com/patent/US9630914B2/en).

An initial subset of six assay descriptions specifying the human COX-2 enzyme
(13165_1, 1436_3, 6146_3, 6829_2, 7086_1, 7870_1) yielded 13 active and 31
inactive unique molecules on previously unseen scaffolds after the structure
and exact-measurement filters. Other descriptions require primary-source
review. Matching DOI or PMID across all 464 document IDs in the old activity
snapshot found one shared publication among the BindingDB articles examined.
Further checks on measurement provenance, unit conversions and related patent
families are required before using any candidate as an external test.
No model was fitted or evaluated on these exports.

## Arabidopsis primary root

The full report by Rodriguez-Furlán and colleagues confirms a seven-day Col-0
root-length assay with matched plate controls in a 10,000-compound screen.
The 689 selected hits reflect several traits, including leaf growth and lateral
root branching. Figures summarize groups and selected follow-ups. The main
article supplies neither a complete compound-to-root-length table nor reuse
terms for such a table. No root classes were inferred from hit counts.
[Full paper in the Universidad de Chile repository](https://repositorio.uchile.cl/bitstream/handle/2250/139291/High-throughput-selection-of-novel-plant-growth-regulators.pdf?isAllowed=y&sequence=1).
