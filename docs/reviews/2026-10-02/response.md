# Response to the three task critiques

The exported reviews are preserved verbatim here. Their six source hashes each
matched the task files before revision; [the receipt](receipt.json) records that
check. All packages advance to `review-0.2`; scientific approval remains pending.

## Consolidated scientific scoring

| Task | Previous scored leaves | Revised outcomes |
| --- | --- | --- |
| Seasonal calibration | 15 | 6: acquisition, preparation, calibration, development verification, report, reuse |
| ACMAD objective | 13 | 4: objective, combination audit, interpretation, reuse |
| WVG definition audit | 12 | 4: reconstruction, comparison, interpretation, reuse |

Reference diagnostics retain their detail but contribute evidence to outcomes,
rather than collecting separate score. Deliverable/schema validity, source
coverage and structured provenance are checked once as unweighted prerequisites.
Trusted information integrity is also a completion condition. A scientific score
cannot compensate for a validity failure. Missing expert/execution evidence
remains unresolved; numeric agreement cannot establish replay or scientific
interpretation. Independently recomputable seasonal development metrics remain
their own outcome, as requested.

## Comparison with the completed seasonal smoke

The revised seasonal task preserves the same core science as
[`archive/pilot-2026-10-01/smoke/task.yaml`](../../../archive/pilot-2026-10-01/smoke/task.yaml). Its results are not a new measurement.

| Aspect | Completed pilot | Revised task / benchmark design |
| --- | --- | --- |
| Scientific work | ECMWF/CHIRPS aggregation, open training-only calibration, leave-one-year-out validation, saved fit | Same work, with explicitly grouped evidence requirements |
| Training and region | 1993–2004, OND, Kenyan study box | Same |
| Acquisition | Verified normalized monthly inputs supplied; retrieval excluded | Agent starts from a source plan, acquires and normalizes products |
| Replay/inference | Required `solve.py` and `predict.py` | Declared commands in any supported CLI/language, with retained dependencies |
| Prediction diagnostics | Initial 2005–06 and related follow-up 2007–08, all previously inspected development years | 2005–06 diagnostic retained; related follow-ups optional at experiment level |
| Accretion comparison | Related saved-workflow follow-up, without fresh-workspace controls or repeated seeds | Other standalone tasks in counterbalanced retained/reset sequences |
| Scoring | Historical pilot checks and judgments | Revised proposed scientific outcomes plus concrete validity/evidence contracts |
| Evidence | Completed agent attempts under the historical harness | No agent attempt or acquisition validation on this revision |

Acquisition adds real work and makes retrieval substrates relevant. Relaxing
script filenames removes one tool/interface constraint. Smaller rubrics clarify
assessment without making the science inherently easier. Yesterday's results
remain evidence about the supplied-data pilot; they cannot be relabelled as
performance on the acquisition task or broad transfer across benchmark tasks.

Keep the historical supplied-data task as a processing-only control when evaluating
the expanded acquisition variant. That can distinguish retrieval improvements
from improvements in calibration, verification or saved-workflow reuse. The
historical task files and results remain unchanged.

## Acquisition without manually packaging every normalized dataset

[The source plan](../../../tasks/seasonal-calibration/source-plan.json)
registers products, dates, spatial bounds and candidate requests. The agent now
retrieves and normalizes the training data; normalized pilot arrays remain
controller development fixtures.

An eventual acquisition service can automatically capture allowed provider
responses into a content cache and replay raw responses through controlled data
access. That avoids repeated provider traffic and hand-preparing every training
array, while still exercising request construction, subsetting and normalization.
A frozen response must contain raw source data, not the already prepared outputs
of the processing task. Range/subset access is acceptable; the retained bytes,
window and request must be recorded.

A live provider run also measures service integration, queues and availability.
A frozen raw-response run controls those factors. Select a primary comparison
mode, label both honestly if both are used, and match starting cache conditions.
Later agent-owned cache reuse can be part of accretion. Log provider wait and
transfer/cache costs alongside model and tool costs. Reproducibility still needs
a pinned source snapshot or a reviewed content-equivalence rule.

Provider documentation was checked on 2026-10-02. The CDS lists precipitation as
metres per second, consistent with the inherited raw-response audit; CHIRPS v3
documents final monthly products and COG access.
[CDS seasonal documentation](https://cds.climate.copernicus.eu/datasets/seasonal-monthly-single-levels),
[CHIRPS v3 documentation](https://www.chc.ucsb.edu/data/chirps3).
The inherited API request/format has not been resubmitted against the current
endpoint. Provider preflight, raw-response freezing, log reconciliation and
clean acquisition replay remain required work. No new provider job was submitted.

Only training observations through 2004 may be accessed. Public availability of
2005–06 observations makes unrestricted internet access incompatible with the
private-target boundary. The existing exact-request gateway is a starting point;
it does not yet supply a frozen response cache. Source/literature access and
later task inputs must respect the embargo across the entire sequence.

## Tool independence and concrete provenance

[The command contract](../../../tasks/replay-contract.md) replaces required
Python filenames with actual replay/prediction commands and retained dependencies.
A CLI skill, shell workflow, Python program or other supported runtime qualifies.
Saved-fit behavior still requires trusted execution evidence.

[The provenance standard](../../../tasks/provenance-contract.md) specifies
source IDs, product versions, actual access/requests, timestamps, retained-file
hashes and transformation lineage/parameters. The static validator checks records
and hashes. Experts assess scientific meaning; trusted logs establish access.
This makes the previous vague provenance requirement inspectable.

## ACMAD difficulty remains to be measured

Keep the current operational step as a candidate basic task. Easier tasks can
identify the smallest reliably successful model/substrate and useful cost
differences. Measure completion and failure modes before assigning a difficulty
tier. If saturated, retain a basic tier or source a distinct component-fitting
or forecast-verification task from centre practice. Extra rubric requirements
alone would create paperwork rather than richer scientific work.

WVG's topic and controlled geometry scope are retained with a smaller rubric.
Published forecast-skill reproduction still requires the author data and a
different reference. No model runs or scientific scope expansion occurred here.

Review [the refreshed HTML pages](../../../tasks/index.html) for the revised
contracts. Acquisition mode, scientific weights, domain review, institutional
permissions and execution adapters remain open; all launch controls remain closed.
