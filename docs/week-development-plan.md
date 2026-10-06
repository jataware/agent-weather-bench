# Plan for ten validated forecasting examples

The practical target for Friday 9 October is ten runnable examples, with fifteen a stretch target. Ten packages are now registered: the original four plus WeatherBench verification, regional subseasonal optimization, seasonal CCA reproduction, station verification, monthly cyclic calibration and conservative downscaling. These tasks share forecasting families; ten examples do not establish ten independent scientific benchmarks. Each addition has real data, independent calculations and consequential executable controls; all six additions have completed integrated solver trials. An example means a frozen scientific contract and checked executable evidence; a source link or drafted prompt does not count. Not every example needs to defeat a frontier model.

## Two complementary tracks

**Reproduce and investigate:** reconstruct a bounded published result or established workflow, diagnose a real discrepancy, and support the conclusions. Declare whether author code is supplied or withheld: reproducing an available repository and reconstructing a paper are different conditions. Follow PaperBench's separation of agent work, fresh execution and outcome-specific grading, and its separate evaluation of judges. We are borrowing that structure, not reproducing its full-paper scale or claiming author-reviewed rubrics. [PaperBench implementation](https://github.com/openai/frontier-evals/tree/main/project/paperbench).

**Improve forecast performance:** use a source-backed subseasonal benchmark and bounded development-score feedback to optimize a forecasting method. Compare the chosen final model on separate controller-only cases. Scientific admissibility and reproducibility precede skill ranking. Temperature, precipitation and different leads can supply useful transfer instances, but remain correlated instances of their source family. See [the leaderboard track](subseasonal-leaderboard-track.md).

## Autonomous preparation

1. Audit real papers, repositories and data for six additions plus backups. Record the bounded objective, exact source evidence, independently checkable outcomes, compute estimate, inspected data and unresolved gaps. Prioritize locally available ACCORD parity/calibration work and lightweight subseasonal baselines over retraining large weather models.
2. Broaden judge examples beyond ACMAD using existing WVG, seasonal and short-rains submissions. Preserve original artifacts and traces, conceal expectations in reviewer packets, and distinguish numerical/execution constraints from uncertain expert judgments.
3. Obtain two fresh-context provisional agent reviews of a bounded four-task subset and validate their cited evidence. Produce a disagreement queue that Ezekiel can review tomorrow. Agent agreement is not human ground truth; these cases are development examples, not an untouched judge test set.

The [source shortlist](task-candidate-shortlist.md) and [judge coverage audit](judge-calibration-next.md) are complete. Seven expanded local packets are prepared, including six additional WVG, seasonal and short-rains cases and one copied ACMAD case. Two fresh-context reviewers completed eight validated reviews on a four-task subset under `var/calibration/judge-local-review/`: three of 13 paired criterion ratings differ. The [local review queue](../var/calibration/judge-local-review/README.md) records those decisions and shared concerns. These are provisional development reviews, not the locked paid judge or a judge-accuracy estimate. This plan schedules no background process.

## Packaging through the week

Eight additional development attempts are complete: six Luna runs cover every
new task, and Astra probes CCA reconstruction and subseasonal optimization. New
controls passed independent calculations and offline Docker checks; the full
suite passes 261 tests and all ten frozen packages validate. Actual controller
feedback is logged. Scientific errors, manifest failures and controller bugs
remain separate in the [overnight audit](overnight-development.md).

The first ten examples are already packaged. Use the remaining week for a short
human review of consequential judgment questions, fresh alternatives and defects,
and a stronger subseasonal instance rather than adding variants solely to reach
fifteen. The [frontier challenge brief](frontier-challenge-next.md) has a small
validated causal prototype. Full-grid coverage, published-baseline parity and
controller-owned sequential replay remain work, and extraction is paused due to
disk pressure. Measure those prerequisites before launching another frontier
pilot; current Astra success does not establish a scientific ceiling.

Judge packets reserve space for declared scientific code and fitted state.
Unknown feedback remains unknown, trace sampling keeps request/result pairs,
and bounded ungraded array diagnostics surface value and metadata defects
separately. Original executed assessments retain their fingerprints. Read-only
static overlays check final repairs without repeating Docker probes or copying
more inputs. Independent local reviews remain provisional; no expert labels or
judge-accuracy estimate exist.

Count a new example only when it has pinned source/data records, a self-contained information boundary and prompt, criterion-specific evidence, an independently checked calculation or metric, a known-correct executable control, a consequential defect control, and a clean offline replay. Run a fresh inexpensive solver attempt to expose ambiguity and operational friction. Open-method tasks permit different valid predictions and supported negative results.

Keep readiness visible: source-audited candidate, runnable development example, or scientifically reviewed comparison task. Human scientific labels, redistribution approval and independent judge calibration remain explicit outstanding work. Prioritize a short review of consequential disagreements rather than asking Ezekiel to annotate every artifact tonight. Preserve family labels and reserve new parent workflows for judge checks before further prompt tuning.

## Spending and scope

Accounted paid API spend is $19.41024 against the $30 cap. Preparation and helper reviews use existing local/subscription capabilities; subscription dollar allocation is unknown. No new paid calls or cloud compute are part of this preparation. The $3 judge allocation remains within the cap and requires pending explicit permission to export the prepared submissions to Anthropic; the expanded packets are not automatically covered by that export request or allocation.

Reuse the existing runtime, storage, criterion reporting and Neil Hausmann's substrate engagement records. Add only task-specific calculations and the bounded feedback interface needed for optimization. Keep source investigations in docs until they pass packaging requirements; avoid filling the task registry with incomplete examples or turning this cycle into a general research-agent platform.
