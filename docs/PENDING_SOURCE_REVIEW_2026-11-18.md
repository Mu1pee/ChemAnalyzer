# Pending experimental data for APAP rescue and primary-root prediction

## APAP experiment with 180 licorice compounds

Kuang and colleagues report 180 compounds assayed in HepG2 cells with 14 mM
acetaminophen for 24 hours, with 64 improving viability beyond the reported
threshold. ChEMBL 37 document queries by DOI and PMID returned zero records.
The Elsevier API returned metadata only. The complete compound-level outcomes,
structures and data reuse terms remain to be obtained.
[Publication](https://pubmed.ncbi.nlm.nih.gov/28899510/).

## HP-MoleQ files

The authors' repository at commit
`d50c777361f177510adf220b0ba74f85479e60aa` contains 1,241 train, 156 validation
and 155 test rows. Their supplementary Table S1 describes 749 hepatoprotective
and 803 hepatotoxic compounds. The CSVs provide SMILES, labels and masks.
They lack row-level toxicant, assay, dose, time and control information.
The inspected tree contains no license file, and the API license field is
null. Endpoint-specific provenance and reuse terms require clarification.
[Repository](https://github.com/Wqy523/HP-MoleQ/tree/d50c777361f177510adf220b0ba74f85479e60aa)
and [publication](https://doi.org/10.1007/s12539-026-00838-3).

Applying ChemAnalyzer's structure standardization to the three files found
five structures shared by train and test, four by train and validation, and
one by validation and test. Nonchiral Murcko scaffold intersections contained
53, 51 and 17 groups respectively. Multifragment rows were excluded from these
structural comparisons. These files require curation and a fresh grouped
split before any compatible endpoint can be assessed. Their labels have not
been assigned to the requested APAP endpoint.

## Published iminosugar root screen

Rugen and colleagues screened 390 iminosugars on Arabidopsis. The accessible
supplement has a sorted graph of root lengths and an XLS catalog. Read-only
extraction verified 390 distinct library IDs. Structure cells contain drawing
objects. The graph supplies no usable mapping from a bar to a library ID.
The article reports five hits using 50% root inhibition at 10 µM after seven
days. A numerical outcome table linked to verified structures is required for
regression. The reported hit count is below the current classifier support
requirement. The material is attributed to the authors under CC BY 4.0.
[Article and supplements](https://pmc.ncbi.nlm.nih.gov/articles/PMC6219604/)
and [license](https://creativecommons.org/licenses/by/4.0/).

## Other root-screen deposits inspected

The CONICET ORIGINAL bundle for Rodriguez-Furlán et al.,
DOI 10.1016/j.plantsci.2016.01.001, contains one main-paper PDF. The checked
bundle lacks a compound-level root-outcome table. The subsequent study by
Emmenecker and colleagues quantifies root tissue pixel area in its bulk
chemical screen. Its numerical data are available from the lead contact on
request. Root-length follow-ups involve selected hits.
[Rodriguez-Furlán repository](https://ri.conicet.gov.ar/handle/11336/52377)
and [Emmenecker article](https://pmc.ncbi.nlm.nih.gov/articles/PMC12032938/).

## COX-2 species conflict

ChEMBL 37 document CHEMBL1138184, DOI 10.1021/jm0510474, provides 29 COX-2
measurements assigned to Ovis aries. BindingDB assay 2585_1 for the same
publication was included in the initial P35354 metadata inventory.
That assay is excluded from the candidate human panel pending resolution of
the species conflict. Source-name counts require this protocol-level review.
After excluding known mismatches, 32 active and 43 inactive structures remain
on scaffolds absent from the old panel, with one conflicting structure.
Those counts are an upper bound before completing protocol and publication
independence checks. The previously inspected explicit-protocol subset still
has 13 active and 31 inactive structures.
[ChEMBL document](https://www.ebi.ac.uk/chembl/document_report_card/CHEMBL1138184/)
and [BindingDB source](https://www.bindingdb.org/rwd/jsp/dbsearch/PrimarySearch_ki.jsp?entryid=2585&tag=entry).

ChEMBL-derived inventory fields are attributed to ChEMBL contributors and
EMBL-EBI under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).

The machine-readable inventory records source hashes, file sizes, readout
scope and extraction counts. These checks add zero trained models.
[Inventory](evidence/pending-source-review-2026-11-18.json).
