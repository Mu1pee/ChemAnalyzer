# Exact-endpoint data audit — 2026-11-10

This is a bounded audit of specific sources, not a claim that no suitable data
exist anywhere. No labels or measurements from the sources below have yet been
integrated into training. One root-growth supplement has now been downloaded
and its actual rows inspected.

## Arabidopsis primary-root growth relative to control

Primary source: Chuprov–Netochin et al., BMC Plant Biology 16, 192 (2016),
https://link.springer.com/article/10.1186/s12870-016-0875-4

The publisher identifies a 1,040-compound pollen screen and 22 quantitative root
hits. Its attachment description mentions 65 compounds, but direct extraction
of MOESM3 found **23 table rows: one header and 22 compound IDs**. Columns contain
ID, chemical family, root length with uncertainty, and growth/control percentage.
The family names do not uniquely identify molecular structures. The 22 rows
are below the 60-compound training floor and are selected hits. Unmeasured
library compounds must not be labelled inactive.

The article is CC BY 4.0; its data are covered by a CC0 waiver unless stated
otherwise. Per-file exceptions and compound-library rights still require review.
Downloaded supplement:

https://static-content.springer.com/esm/art%3A10.1186%2Fs12870-016-0875-4/MediaObjects/12870_2016_875_MOESM3_ESM.docx

The retained original DOCX and extraction JSON are in the research data archive
under `root-source-2016`, including the download checksum. Molecular identity
mapping from the structural supplement and additional compatible measurements
are still needed. No model was trained from these insufficient rows.

## Rescue from acetaminophen injury

Primary source: Chao et al., Acta Pharmaceutica Sinica B, DOI
10.1016/j.apsb.2023.10.017,
https://pmc.ncbi.nlm.nih.gov/articles/PMC10793101/

The paper describes a 383-drug TFEB screen and mouse acetaminophen-injury
protection by salinomycin. TFEB activation across the screen is a different
endpoint from measured acetaminophen rescue. It cannot provide rescue labels
for all 383 molecules. The article states CC BY-NC-ND 4.0; unrestricted reuse of
an extracted training distribution has not been established. It was not imported.

Gene-expression or CRISPR perturbation screens likewise cannot be silently
converted to small-molecule antidote QSAR labels. A suitable next dataset must
document actual co-treatment rescue, matched controls, compound identity, dose,
time and organism/cell system, plus usable redistribution/training terms.

Both target models remain not_trained while these requirements are unresolved.
