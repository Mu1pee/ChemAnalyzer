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

## Additional source review, 2026-11-11

Burrell et al., Microphenotron, doi:10.1186/s13007-017-0158-6:
https://link.springer.com/article/10.1186/s13007-017-0158-6 . The article is CC BY
4.0, with a CC0 data waiver unless otherwise stated. It describes 800 compounds,
70 qualitative root-phenotype hits, and possible replicate loss. Its data
availability statement requires requesting the datasets from the corresponding
author. The public supplements concern hardware/software, not a complete
structure-linked table of primary-root length/control measurements. No values
or inactive labels were reconstructed from the article's aggregate counts.

Rodriguez-Furlan et al., doi:10.1016/j.plantsci.2016.01.001, is a further lead:
https://pubmed.ncbi.nlm.nih.gov/26940491/ . The abstract describes a 10,000-compound
plant-growth screen. The publisher returned HTTP 403; the university repository
showed an access challenge. Full row-level outcomes and redistribution terms
remain unverified. Neither access protection was bypassed. This is not yet an
eligible training dataset, and the abstract does not supply missing outcomes.

## Further bounded search, 2026-11-11 (3.2.7)

Yang et al., Nature Communications 7, 11916 (2016),
https://www.nature.com/articles/ncomms11916 , describes an acetaminophen rescue
screen of 302 **miRNA mimics**. This concerns nucleic-acid perturbations, not
302 small molecules suitable for the current molecular-fingerprint QSAR. It
was excluded without importing labels. Full supplemental reuse terms were
not established; publisher retrieval redirected to authentication and PMC
displayed a browser challenge. Neither was bypassed.

Kim and Kim, Biomolecules 14, 1177 (2024),
https://www.mdpi.com/2218-273X/14/9/1177 , describes a 14,400-compound reporter
screen and detailed follow-up of SRR1/SRR2. Reporter expression does not supply
primary-root-length/control values for that full library. Full supplement and
license review remains incomplete (publisher HTTP 429; PMC browser challenge).
No root outcomes or negative labels were inferred from those aggregate counts.

Christian et al., Journal of Experimental Botany 59, 2757 (2008),
https://academic.oup.com/jxb/article/59/10/2757/436620 , is a further root-growth
screening lead. Publisher retrieval failed; a complete structure-linked outcome
table and usable data terms have not been verified. It remains a lead, not an
imported dataset. These bounded checks do not establish that no eligible dataset
exists elsewhere. Both requested target models remain explicitly not_trained.

## Additional primary source audit, 2026-11-11

Emmenecker et al., iScience 28, 112375 (2025), DOI
https://doi.org/10.1016/j.isci.2025.112375 , reports a 1,519-compound Prestwick
screen in Arabidopsis WT and mus81. The primary-screen readout is segmented
root/leaf area in pixels, not primary-root-length/control. Full data/code are
available from the authors on request according to the source's data-availability
section. The primary full-text XML explicitly identifies CC BY-NC 4.0:
https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12032938/fullTextXML
(HTTP 200, 130,917 bytes, checked 2026-11-11).

No compound outcomes were inferred from reported hit percentages, and no
unmeasured compounds were labeled inactive. No data were imported and no author
was contacted. This source would require a separate root-area endpoint,
structure-linked complete measurements, experimental-condition review and
acceptable reuse terms; it does not fill the requested primary-root-length
dataset. Publisher/PMC browser access challenges were not bypassed; the public
Europe PMC API supplied the source XML.
