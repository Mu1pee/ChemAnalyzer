# Exact-endpoint data audit — 2026-11-10

This is a bounded audit of specific sources, not a claim that no suitable data
exist anywhere. No labels or measurements from the sources below have yet been
integrated into training. Inspection of supplementary tables remains necessary.

## Arabidopsis primary-root growth relative to control

Primary source: Chuprov–Netochin et al., BMC Plant Biology 16, 192 (2016),
https://link.springer.com/article/10.1186/s12870-016-0875-4

The publisher identifies a 1,040-compound pollen screen, Table S3 listing 65
compounds evaluated in pollen/root assays, and Table S4 reporting root length
relative to control for 22 selected compounds. The 1,040-compound library cannot
be treated as 1,040 quantitative root measurements. The reported 22-compound
quantitative subset alone is below the current 60-compound training floor and
is selected for hits. Unmeasured compounds must not be labelled inactive.

The article is CC BY 4.0; its data are covered by a CC0 waiver unless stated
otherwise. Per-file exceptions and compound-library rights still require review.
Table S3 is the next concrete candidate to inspect, rather than assuming all 65
rows supply numerical primary-root values and resolvable molecular structures:

https://static-content.springer.com/esm/art%3A10.1186%2Fs12870-016-0875-4/MediaObjects/12870_2016_875_MOESM3_ESM.docx

The web reader identified this attachment but could not decode its binary format.
No structural identities or root labels have been inferred from that failure.

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
