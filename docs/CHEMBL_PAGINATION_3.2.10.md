# ChemAnalyzer 3.2.10 — measured ChEMBL coverage

Date: 2026-11-11.

## Problem and correction

The previous activity query retrieved at most 500 rows. A successful HTTP
response could consequently appear complete even when more measurements
existed. The API now reads ordered activity pages with locally constructed
offsets, verifies source totals and unique activity IDs, and preserves
retrieved/total/page counts. Up to four pages of 500 rows are allowed within
the existing shared 55-second deadline. Arbitrary source `next` URLs are never
followed. Retrieval limits and timeouts never become biological negatives.

A malformed later page, changing total or request failure preserves earlier
valid pages with a partial status. Invalid row collections are rejected before
parsing. Legacy cached profiles remain on disk but cannot claim verified
activity completeness. Counts are validated again when reading a cache.

## Live evidence

Official ChEMBL activity endpoint, filtered to IC50/Ki/Kd/EC50/Potency:
https://www.ebi.ac.uk/chembl/api/data/activity.json

| Query | Retrieved / reported rows | Pages | Time | Result |
|---|---:|---:|---:|---|
| Aspirin, CHEMBL25, complete application profile | 655 / 655 | 2 | 13.625 s | Complete activity pages; 15 displayed targets, 8 analogs, no request warning |
| Imatinib, CHEMBL941, activity retrieval | 2,000 / 2,731 | 4 | 53.516 s | Explicitly incomplete at configured page/row limit |

The aspirin cache preserved these coverage counts. Server contents, latency
and availability can change; the recorded counts describe these requests.
The previous 6.266-second check proved transport availability but missed the
500-row cap. Its output is retained as historical evidence.

Fresh recheck on 2026-11-13: aspirin CHEMBL25, 655/655 rows in two pages,
4.266 seconds, no cached response or warning. This is a further successful
availability observation; upstream availability is not guaranteed continuously.

The activity table uses rows with available pChEMBL and displays up to 15
targets, with the maximum pChEMBL among retrieved rows for each target. This
does not imply comparable binding strength across IC50, Ki, Kd, EC50 and Potency
assays. The interface now describes these distinct measurements correctly.

## Scope

No new model, label, data source or quality score is introduced by this fix.
The schema-2 COX-2 rejection and the nine qualified experimental Research Agent
models from 3.2.9 remain in force. Acetaminophen-rescue and Arabidopsis
primary-root-length models still lack eligible complete experimental tables.
