# Recovering a complete ChEMBL profile in 3.2.14

Earlier versions kept a single cache record per query. When a refresh retrieved
only part of the source data, it replaced the previous complete profile. A
subsequent service outage exposed the loss, including after restarting the app.

A partial refresh is still displayed immediately and remains fresh for five
minutes. The cache also retains the last eligible complete profile. If both
live lookup routes fail, the backend checks the cache again and prefers that
profile. The UI identifies the cached response, displays its original time of
retrieval and reports the source pagination counts. The failure warnings belong
to the current request. All scientific fields come from one snapshot.

Historical fallback requires a found compound, verified complete activity
coverage, a successful profile without warnings, and a source timestamp with a
time zone no later than the cache write. The previous snapshot keeps its
original write time across partial refreshes. The 30-day maximum age applies
to each snapshot separately. A missing date in a legacy copy is shown as
unknown. The on-disk and in-memory caches use the same format and limit each
record to 4,000,000 encoded bytes. Each data directory retains up to 128 files.

## Source observations

Two independent requests for aspirin (CHEMBL25) on 16 November 2026 returned
655 of 655 rows at 13:42:14 UTC and 500 of 655 at 17:58:19 UTC. The second
request encountered upstream failures. Replaying these profiles in that order
reproduces the history of a partial refresh without changing either source
timestamp. A separate fresh check at 19:05:04 UTC retrieved all 655 rows in
two pages in 2.734 seconds. The counts refer to activity rows read from the
source. The app presents up to 15 aggregated targets.

The verification fixture and profile fields derived from ChEMBL are attributed
to ChEMBL contributors and EMBL-EBI under CC BY-SA 3.0. ChemAnalyzer paginates,
aggregates and serializes the responses for display and replay.
[ChEMBL compound record](https://www.ebi.ac.uk/chembl/compound_report_card/CHEMBL25)
and [data license](https://creativecommons.org/licenses/by-sa/3.0/).

## Windows checks on 17 November 2026

The packaged x64 app loaded the two reference profiles from an isolated data
directory. A loopback proxy rejected nine connection attempts from the test
app. Its API recovered all 655 rows, retaining the original compound identity,
date, targets, mechanisms, indications, analogs and pagination evidence. The
renderer displayed the outage notice and the original date. The frozen
backend queried the live service separately and reported ChEMBL 37.

The backend passed 421 tests, Electron passed 20 and the frontend production
build completed. Native and Portable both started on Windows. Predictions,
catalog availability and out-of-domain responses were exercised. The Portable
run had Research Lab disabled. A display example from fitting data checked
model serving only. Neither run produced a renderer error.

The first installer packaging attempt timed out in NSIS. Rebuilding Setup
from the verified application directory succeeded. All 5,951 files embedded
in the installer matched that directory by SHA-256. The unsigned Setup and
Portable archives passed integrity checks. Installation and uninstallation
were not exercised.

## Scope of scientific evidence

Ten existing research artifacts retain their experimental status. The nine
classifiers have internal held-out balanced accuracy above 0.60. FreeSolv has
held-out R² of 0.729. Each measure applies only to its stated endpoint. COX-2
remains withheld after a held-out ROC-AUC of 0.733 against a threshold of 0.75.
The APAP rescue and Arabidopsis primary-root models await eligible
compound-level experimental outcomes. Three author requests were sent on
16 November. This release adds zero fitted models.
