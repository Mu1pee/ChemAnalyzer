# Specialized experimental source audit — 2026-11-16

The acetaminophen-rescue and Arabidopsis primary-root models remain
**not_trained**. This audit retrieved real database records and checked the
coverage of specific searches. It did not create labels, pool protocols, fit
models or change the nine experimental artifacts shipped in 3.2.11. It does not
establish that suitable data do not exist elsewhere.

The machine-readable inventory is
[evidence/specialized-source-audit-2026-11-16.json](evidence/specialized-source-audit-2026-11-16.json).
It contains assay IDs, per-assay counts, source version, coverage checks and
SHA-256 hashes of the locally retained responses. The inventory is discovery
evidence, not an approval manifest or a training dataset.

## Scope and source coverage

The official ChEMBL status endpoint identified **ChEMBL 37**, release date
2026-05-01, with status UP during this collection. Every page used below had
offset zero, no next page, and a returned count equal to the source total.
Activity IDs were unique within each inventory and every requested assay was
accounted for. PubChem search IDs were compared with the returned summaries;
the broad APAP search was expanded past its initial 500-ID window to retrieve
all 1,244 hits. Successful transport is not evidence of endpoint suitability.

| Bounded search | Retrieved evidence | Interpretation |
| --- | --- | --- |
| ChEMBL assay organism exactly Arabidopsis thaliana, description contains root | 15 assays; 35 activity rows; 22 distinct ChEMBL molecule IDs | Includes root morphology, differentiation, endocytosis and other endpoints; not a 22-compound primary-root-length/control dataset. |
| PubChem Arabidopsis AND root, both All Fields | All 43 IDs and 43 summaries | All 43 identify ChEMBL as their source. They are not independent experimental validation, and text matches include other species or readouts. |
| PubChem acetaminophen/paracetamol AND rescue/protection, All Fields | All 1,244 IDs and 1,244 summaries, 13 summary batches | Broad retrieval includes unrelated ToxCast and other records. Only 95 titles explicitly name acetaminophen, paracetamol or the word APAP; that title filter is a discovery heuristic, not scientific admission. |
| ChEMBL descriptions containing acetaminophen, paracetamol, or APAP | 133, 37 and 258 assays respectively; union 428; 426 after excluding APAP substring-only matches | All 426 assays' activity records were retrieved in six disjoint batches: 1,311 rows. No individual matching assay contains even 60 different molecules. |

Reproducible primary interfaces:

- [ChEMBL status](https://www.ebi.ac.uk/chembl/api/data/status.json).
- [Arabidopsis/root assay query](https://www.ebi.ac.uk/chembl/api/data/assay.json?assay_organism=Arabidopsis%20thaliana&description__icontains=root&limit=1000&offset=0).
- [ChEMBL API documentation](https://www.ebi.ac.uk/chembl/api/data/docs).
- [PubChem root search](https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pcassay&term=Arabidopsis%5BAll%20Fields%5D%20AND%20root%5BAll%20Fields%5D&retmode=json&retmax=500).
- [PubChem APAP search](https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pcassay&term=%28acetaminophen%5BAll%20Fields%5D%20OR%20paracetamol%5BAll%20Fields%5D%29%20AND%20%28rescue%5BAll%20Fields%5D%20OR%20protection%5BAll%20Fields%5D%29&retmode=json&retmax=2000).
- PubChem summaries: `/rest/pug/assay/aid/{comma-separated AIDs}/summary/JSON` on `https://pubchem.ncbi.nlm.nih.gov`.

## Arabidopsis: measurements do not yet supply the requested endpoint

Five of the returned assays explicitly mention primary-root inhibition or a
decrease in root length. Together they contain eight rows for five distinct
molecules:

- CHEMBL1243685 and CHEMBL1243696 each contain an IC50 for the same molecule in
  different ecotypes. Their values are concentrations, not primary-root-length
  ratios against matched controls.
- CHEMBL4392768, CHEMBL4392769 and CHEMBL4392771 contain six rows for four
  molecules at different concentration regimes. Both `value` and
  `standard_value` are null in these records. Missing measurements were not
  converted into inactive labels.

Other retrieved assays concern generic root growth, root-tip puffing,
differentiation, Golgi morphology or endocytosis. Their rows cannot be combined
as measured primary-root-length/control outcomes. Ecotypes, concentrations,
exposure times and control definitions still need original-protocol review.
PubChem mirrors do not add new independent compounds or measurements merely by
having different database identifiers.

## Acetaminophen: real small series, no eligible training set

The largest matching ChEMBL assay contains 34 molecules, but measures CYP1A2
inhibition with acetaminophen as a reaction product. It is not rescue from
acetaminophen injury. The largest reviewed explicit cell-survival series is:

| Source assay | Context recorded by ChEMBL | Source rows / unique molecules | Finite standard values |
| --- | --- | --- | --- |
| CHEMBL4820889 | HepG2, 10 uM, 48 h, MTT cell survival after APAP injury | 19 / 19 | 18 |
| CHEMBL6126442 | AML12, 5 uM, 12 h, MTT protection after acetaminophen injury | 16 / 16 | 16 |
| CHEMBL6126443 | AML12, 10 uM, 12 h, MTT protection after acetaminophen injury | 16 / 16 | 16 |

The two AML12 assays reuse the same 16 molecule IDs. Different doses are not
additional independent compounds. HepG2 and AML12, 12 h and 48 h, pretreatment
and post-treatment, MTT survival and ALT release must not be silently pooled.
A null standard value does not by itself establish either an inactive outcome
or an invalid experiment; the original source needs review.

Primary database records and publications:

- [CHEMBL4820889 activity records](https://www.ebi.ac.uk/chembl/api/data/activity.json?assay_chembl_id=CHEMBL4820889&limit=1000&offset=0), document CHEMBL4819036, [doi:10.1021/acs.jnatprod.0c01117](https://doi.org/10.1021/acs.jnatprod.0c01117).
- [CHEMBL6126442 activity records](https://www.ebi.ac.uk/chembl/api/data/activity.json?assay_chembl_id=CHEMBL6126442&limit=1000&offset=0) and [CHEMBL6126443 activity records](https://www.ebi.ac.uk/chembl/api/data/activity.json?assay_chembl_id=CHEMBL6126443&limit=1000&offset=0), document CHEMBL6121056, [doi:10.1021/acs.jnatprod.4c01049](https://doi.org/10.1021/acs.jnatprod.4c01049).

The publisher returned HTTP 403 for both publications. Full experimental
conditions and supplement-specific rights have not been verified. No access
protection was bypassed. These records were retained for review without
assigning binary classes or admitting a protocol.

## Additional literature leads checked

Schepers et al., [doi:10.1021/acschembio.1c00503](https://pmc.ncbi.nlm.nih.gov/articles/PMC12969845/),
is now available as an author manuscript explicitly marked CC BY 4.0 in the
[Europe PMC source XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12969845/fullTextXML).
Its analogue screen measures albumin secretion; the APAP-injury follow-up
concerns FH1. The analogue results do not become APAP-rescue labels. No rows
were imported from this paper.

The [MICROBIOSIS project report](https://cordis.europa.eu/project/id/101089198/reporting)
mentions a collection of more than 400 microbial molecules for screening. The
[published results index](https://cordis.europa.eu/project/id/101089198/results)
does not establish a complete, structure-linked primary-root-length/control
table. It remains a lead; molecule collection size is not a count of available
endpoint measurements.

North et al., [doi:10.1073/pnas.1008209107](https://pmc.ncbi.nlm.nih.gov/articles/PMC2951415/),
remains unresolved here: its public Europe PMC XML request returned HTTP 500,
and full supplement outcomes and rights were not verified. A browser access
challenge was not bypassed. This transport failure does not show that the
paper or its data are unsuitable.

## Admission decision and retained materials

The trainer requires **30 fitted compounds per class**, five validation
compounds per class and ten test compounds per class. The resulting necessary
total lower bound is **90 distinct curated compounds**, not 60. Ninety is not a
sufficient sample size: the fixed scaffold split must actually retain the
required class/scaffold support in each partition, with complete source
conditions, reuse provenance and a justified endpoint/class definition.
Held-out quality must then pass the existing policy. The historical 60-row
check is only a preliminary rejection floor; it must not be presented as enough
data to train and validate a model.

The local research output folder `specialized-sources-2026-11-16` contains:

- `REVIEW_CANDIDATES_NOT_TRAINING_DATA.json`: the original 51 APAP rows from
  three separately retained assays and 35 Arabidopsis rows, without inferred
  labels; `training_eligible` is false.
- `LOCAL_SOURCE_SNAPSHOTS.zip`: the frozen responses and collection/verification
  scripts. It is retained locally, not published as a training distribution.
- `SNAPSHOT_MANIFEST.json` and `source-audit.json`: file hashes, provenance and
  verified discovery counts. Archive entries were checked against every hash.

ChEMBL-derived database inventory is attributed to ChEMBL/EMBL-EBI, ChEMBL 37,
under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/), as verified
in the [official data-licensing statement](https://chembl.gitbook.io/chembl-interface-documentation/about).
This does not grant a blanket license for PubChem-hosted sources or publisher
supplements. The public summary omits full abstracts and original measurement
tables. It is evidence of this bounded audit, not independent scientific review
or a claim of >60% quality for either missing model.

Further training depends on a complete eligible per-compound outcome table,
additional compatible experimental measurements, or an explicit expansion to a
separately named endpoint with its own data and validation. No author was
contacted and no user model, training CSV or protocol was modified.
