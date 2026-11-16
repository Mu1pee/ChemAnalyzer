# Follow-up review: APAP rescue and Arabidopsis primary-root growth

This follow-up was performed after the 3.2.12 model release. Both specialized
endpoints remain **not_trained**. It adds real source evidence and narrows the
remaining data requests; it does not add a model, modify existing weights or
establish that eligible data do not exist elsewhere.

The reproducible counts, query translations, source identifiers and workbook
hashes are in
[evidence/endpoint-data-review-2026-11-16.json](evidence/endpoint-data-review-2026-11-16.json).
The earlier activity-level review remains in
[SPECIALIZED_SOURCE_AUDIT_2026-11-16.md](SPECIALIZED_SOURCE_AUDIT_2026-11-16.md).

## Expanded official database searches

The Entrez `pcassay` field list was checked before using the Assay Name and
Organism fields. Four valid queries returned 2,983 distinct assay IDs:

| Search | IDs | Available summaries |
| --- | ---: | ---: |
| Acetaminophen/paracetamol/APAP in assay name | 388 | 388 |
| Those names plus cytoprotective/hepatoprotective/protective/prevention vocabulary | 2,754 | 2,752 |
| Arabidopsis/thaliana in assay name plus root/elongation/growth | 99 | 99 |
| Arabidopsis organism plus root/elongation/growth | 112 | 112 |

The union has **2,981 available summaries**, including 1,835 absent from the
previous packet. The counts in the table overlap. A failed 100-ID batch returned
HTTP 504 and was recovered in smaller batches. AIDs 2282654 and 2282655 still
returned HTTP 404 individually; those descriptions remain unresolved.
An attempted Taxonomy Name query produced a phrase-not-found warning. Its zero
count was excluded rather than interpreted as biological absence.

All 99 root-name matches identify ChEMBL as the source. They do not create
independent experimental validation. Large organism-search hits AIDs 977608,
977610, 977611 and 1811 describe PDB protein-ligand binding affinity, not
primary-root length. AID 462262 has 66 compounds but measures LL-DAP-AT enzyme
inhibition expressed in E. coli. These counts cannot support the requested
plant-growth model.

The known direct APAP cell-survival series remain small: AID 1761891 has 19
compounds; AIDs 2252420 and 2252421 reuse the same 16 compounds at two doses.
Their distinct cell lines, concentrations and times were not pooled.
Summary retrieval is discovery evidence; it is not a new complete activity-level
curation of every expanded-search result.

Primary interfaces: [Entrez field information](https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi?db=pcassay&retmode=json)
and [PubChem PUG REST](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest).
Exact translations and returned IDs are retained in the inventory.

## Newly inspected experimental spreadsheets

Ru and colleagues deposited
[Mendeley Data 10.17632/jzd9mnsx8t.1](https://data.mendeley.com/datasets/jzd9mnsx8t/1),
version 1, on 20 October 2026. The associated article is
[doi:10.1016/j.cell.2026.10.011](https://pubmed.ncbi.nlm.nih.gov/42971203/).
The deposit explicitly uses CC BY 4.0, subject to any identified third-party
exceptions. That data license does not license the separately copyrighted Cell
article. Dataset attribution is preserved in the machine-readable inventory.

The public folder inventory returned 28 files in 18 folders: **17 XLSX and 11
PDF files**, with no failed folder requests. All 17 original workbooks were
downloaded and checked against the depositor's exact byte counts and SHA-256
hashes: 238,611 bytes, 1,103 nonempty rows and 7,273 nonempty cells. OOXML was
read without executing macros, recalculating or saving the workbooks. There
were no formula cells. PDF western-blot files were not downloaded or reviewed.
An independent read-only openpyxl 3.1.5 check compared all 7,273 coordinates
and values against the OOXML extraction and confirmed that all source hashes
remained unchanged. Its results are retained in the local output packet.

The workbook APAP headers identify only four named chemical interventions:
**2-BP, Salubrinal, GNF-5837 and NAC**. Relevant source workbooks are Figure 6,
Figure 7, Figure S10 and Figure S11. They contain selected follow-up experiments,
including liver-enzyme/cytokine measurements and time-to-event-style tables.
Repeated animals, doses, times and readouts do not constitute additional unique
chemical structures. Source names have not yet been mapped to verified
structures. Missing cells remain missing; 0/1 event-style entries have not been
reinterpreted as QSAR rescue classes.

Other sheets concern CIL56-associated cell outcomes, ConA injury and genetic
perturbations. None was relabeled as acetaminophen rescue. In particular, a
protective result against CIL56 is not an APAP outcome. Workbook headers do not
resolve all APAP doses, strain/sex, timing, controls or event/censor conventions;
the full protocol remains necessary. The publisher returned HTTP 403 for the
article; access controls were not bypassed.

Decision: **retain for review, do not import for training**. Even before
protocol/identity review, four named interventions are below the necessary
90-distinct-compound support floor of the current specialized trainer. This
deposit is useful evidence, but is not a full APAP chemical-screen dataset.

## Plant literature follow-up

The licensed Europe PMC XML for
[Khan et al. (2017), doi:10.1038/srep41121](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5253734/fullTextXML)
was inspected. The 10,000-compound library was screened for seedling development
in the presence of NAE 12:0; ten hits were selected. Reviewed primary-root
follow-up concerns MDPD and three structural analogues. It does not establish
10,000 numerical primary-root outcomes. Root hairs, cotyledon area and FAAH
enzyme activity were kept distinct from primary-root length. No complete
compound-outcome table was established or imported. Text/caption timing
inconsistencies are recorded without silently harmonizing them.

The indexed primary text for
[Okamoto et al. (2018), doi:10.1093/pcp/pcy131](https://doi.org/10.1093/pcp/pcy131)
describes a 456-compound screen under mechanical stress. The full numerical
outcome table and supplement-specific reuse terms remain unverified; the
publisher redirect failed. Library size is not a measurement count.
He et al. (2011), doi:10.1105/tpc.111.089029, and North et al. (2010),
doi:10.1073/pnas.1008209107, also remain unresolved through the checked open
full-text route. Access failures and metadata `OA=N` are not judgments that
their data are scientifically unsuitable or universally unavailable.

## Admission and next data requirements

Each specialized training CSV still has zero records and its existing checksum
is unchanged. No source outcomes were invented; no model was fitted or activated.
The current contract requires 30 train, five validation and ten test compounds
**per class**, making 90 distinct curated compounds a necessary lower bound.
The fixed scaffold/class support, matched protocol, identity, provenance and
held-out quality requirements still apply; 90 compounds alone are insufficient.

The local `endpoint-data-review-2026-11-16` output packet contains unchanged
workbooks, read-only extraction, source snapshots, collection scripts and an
archive whose 103 entries were verified against their hashes. It also holds
unsent data-request drafts. No author has been contacted. Public Git history
contains this provenance/count summary, not the local source archive or drafts.
The next useful data are complete per-compound outcomes, including measured
non-hits and exclusions, structures/library version, matched controls,
conditions/replicate IDs and explicit reuse terms. APAP, other toxicants,
root length, root hairs and other plant phenotypes remain separate contexts.
