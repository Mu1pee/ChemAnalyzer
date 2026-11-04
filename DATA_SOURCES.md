# Data sources and provenance

Verified for the first increment on 2026-11-04:
[MobleyLab FreeSolv](https://github.com/MobleyLab/FreeSolv),
[database format](https://github.com/MobleyLab/FreeSolv/blob/master/database.txt),
[data license](https://github.com/MobleyLab/FreeSolv/blob/master/LICENSE).
Data CC BY 4.0; code has a separate license. Attribution: David L. Mobley,
J. Peter Guthrie and FreeSolv contributors. Reference:
[FreeSolv (2014)](https://doi.org/10.1007/s10822-014-9747-x).

Import pins both LICENSE and database.txt to Git commit
`6c7d19b4b565537365ffd22006aa2cd4643200c6` in the demonstrated run.
The adapter resolves the current upstream commit on each explicit import and
records it; historical runs always retain their original bytes and checksums.

Endpoint: experimental hydration free energy of small neutral molecules,
kcal/mol. Semicolon field 4 (1-based) is the target. Calculated GAFF energies
are never labels or features. Experimental uncertainty, original references and
notes are retained. Some uncertainties are defaults assigned by the source;
they are not treated as new experimental error measurements. Source measurements
and reference conditions are heterogeneous; the demonstration is a benchmark,
not proof that every record shares one laboratory protocol.

Normalized CSV SHA256 for the first demonstration:
`a489cf3153d616abb7072e07ad4470b9ac4e96f3ff944d192ae23504a7ec3575`.
642 rows, 642 accepted molecules. Raw source and LICENSE hashes are in local
task evidence.json; raw source.txt/LICENSE.txt are retained, not committed.

## Discovery leads, not accepted training sets

- [PubChem BioAssay](https://pubchem.ncbi.nlm.nih.gov/): needs assay-specific
  experimental outcomes, units, controls and submitter reuse terms.
- [ChEMBL](https://www.ebi.ac.uk/chembl/): separate endpoint/assay/context;
  do not pool IC50, Ki, Kd and EC50 just because pChEMBL is available.
- [Zenodo](https://zenodo.org/): inspect dataset license, version, supplement
  structure/measurement mapping and the primary publication.
- Local CSV: explicit curator declaration and provenance; source URL alone is
  not verification. Parquet is not yet directly supported.

No authenticated-source bypass, unknown script execution or remote private-data
upload. This increment has no generic publisher supplement scraper. Existing
plant/APAP source-screening notes remain in ML_TRAINING_GUIDE.md; no labels were
inferred from unmeasured compounds, docking or transcriptomic experiments.
