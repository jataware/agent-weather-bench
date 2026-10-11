# Tooling efficiency across forecasting jobs

Six fresh agent attempts are complete. The MAM repeat shows a time benefit:
guided tools and Python both pass, with guided 21.7% faster in the agent phase
but using 8.8% more fresh-input-plus-output tokens. Guided MAM was faster in
both matched pairs, while token savings did not repeat. Rhiza adds overhead
on weekly revision; guided consolidation produces correct submitted numbers
but fails command portability. The evidence supports a task-specific time
signal on the heavier calibration workflow, not general token or dollar savings.

This bounded follow-up asks whether the first guided-tool completion signal
extends to other ordinary forecasting work. It compares fresh Luna attempts
with general scientific Python against a pinned weather environment with a
short public-API guide and a runnable synthetic example. The intervention is
the package/skill and discovery bundle; it does not isolate library effects.

The [predeclared plan](../experiments/tooling-breadth-plan-2026-10-08.json)
allows six agent attempts, one matched pair at a time with its two arms running
concurrently. There are no automatic retries or favorable-result expansion
rules. Runtime or grader defects pause the investigation before further calls.
Native scientific I/O remains serial inside each fresh process, with at most
two scientific workers across all preflight and inference work.

| Pair | Job and selected tool | Why this comparison |
| --- | --- | --- |
| Kenya revision | Compare two weekly rainfall forecasts; Rhiza deaccumulation converts native cumulative amounts to interval rates | Tests preparation of provider data, distinct from statistical calibration. The agent still selects valid dates, integrates periods and computes regional changes. |
| Objective consolidation | Retrieve and combine seasonal probability products; AfricaS2S `combine_terciles` implements complete-vector support and available-component weighting | Tests a different native operation on a straightforward job that Luna already completed with Python. Acquisition, support counts, disagreement and packaging remain agent work. |
| MAM repeat | Repeat the prior native normalization/calibration comparison with unchanged precision-pair instructions, sources and caps | Checks whether the original valid-versus-incomplete result repeats. It is the same instance, not another dataset or independent scientific question. |

CCA and downscaling were excluded because their task recipes differ from
the library defaults. Seasonal calibration remains a useful future candidate;
its three required prose/process reviews add a separate completion and timing
dimension. An unused guide for that task is explicitly marked unvalidated.
The selected production jobs do not require the supplementary prose judge for
completion, so this round runs without judging and reports prose as unresolved.

Within each pair, both arms use the same Luna backbone, high reasoning effort,
pinned adapter, common scientific dependency versions, 2 CPUs, 1536 MB memory,
900 seconds and 20 commands. Requested token caps are 350,000 cumulative,
100,000 fresh-input-plus-output and 20,000 output. Usage checkpoints can overshoot;
all actual usage remains in the accounting. The new-task arms share guidance
to promote values before arithmetic, produce the envelope before optional
exploration, run their own command once and finish. The MAM repetition retains
the exact earlier instructions instead.

Before inference, each task needs a current automatic-control certificate,
the rendered brief, native helper compatibility in the selected pinned image,
and Docker control evidence including changed-data replay. Public guides
contain API signatures, units, coordinate semantics and invented examples;
the controller's task-solving validation code and private answers are never
included in the system substrate. Historical templates, source snapshots,
submissions and assessments remain unchanged.

Report computed completion, overall completion, driver status and substantive
helper use separately. A tool counts only when its returned values feed
delivered arrays; imports and toy runs are insufficient. Resource measures are
fresh input, cached input, output, total tokens, agent time, command time and
full CLI/assessment time. Failures remain assigned to their arm. Resources per
valid completion include failures and are undefined for zero completions.

Percentage efficiency comparisons are most informative when both arms
produce valid results. A valid-versus-incomplete pair shows an exploratory
completion difference under that budget; it does not establish a scientific
capability boundary or general speedup. Report every measured resource
direction, including increases. Three single pairs cannot support a stable
ranking, and related sources or repeated instances are not independent data.
Subscription tokens are not invoices; direct paid API use and unknown
subscription charges remain separate.

Docker Desktop was stopped at the start of preflight. It was started without
resetting data or volumes; the healthy server snapshot is
`var/review/tooling-breadth-docker-health-20261008.json`. No agent inference was
in flight. This is infrastructure evidence, not a model failure.

## Recorded results

| Job / assigned arm | Completion | Fresh input + output | Agent seconds | CLI seconds, including assessment |
| --- | --- | ---: | ---: | ---: |
| Revision / Python | Pass | 29,254 | 65.4 | 71.3 |
| Revision / Rhiza | Pass | 37,002 | 73.7 | 79.0 |
| Consolidation / Python | Pass | 55,320 | 96.7 | 105.7 |
| Consolidation / AfricaS2S | Fail: replay portability | 33,417 | 91.0 | 100.6 |
| MAM repeat / Python | Pass | 53,069 | 149.9 | 191.5 |
| MAM repeat / acmadDL + AfricaS2S | Pass | 57,727 | 117.4 | 168.8 |

Every driver submitted normally, without a token/time stop. All three guided
attempts substantively used the requested native helpers on real inputs;
returned arrays feed delivered outputs. Supplementary prose remains unresolved
because no judge was run. Failed attempts remain in resource totals.

For revision, Rhiza uses **26.5% more** fresh-plus-output tokens and **12.8% more**
agent time; full CLI time is 10.8% higher. Both arms repair a scalar issue-time
coordinate conflict during packaging. Rhiza additionally inspects the skill,
help and helper source, then reruns for inherited-attribute cleanup. These
traces show extra work; they do not causally allocate token or time differences
to particular operations. The helper is scientifically correct, but its
discovery and integration overhead outweighs any observed saving in this pair.

For consolidation, both native probability fields and the support/disagreement
arrays pass reference and validity checks. The guided script unconditionally
copies acquired files into `/work/state/source_snapshot`. That actor workspace
path is not writable in standalone assessment: both replays fail before the
helper runs. The Python arm passes both replays. Guided's lower recorded usage
therefore cannot be claimed as efficiency at valid completion.

An independent review classifies the failure as command portability, not a
grader or library-math defect. A [separate diagnostic](../experiments/breadth-consolidation-portability-diagnostic-2026-10-08.json)
changes exactly one expression in a copied frozen submission, moving optional
retention beneath the declared output directory. All computational checks,
including changed-source/partial-vector regeneration, then pass. The original
submission, assessment and failure remain unchanged. This diagnostic is neither
a new agent attempt nor a valid completion in the comparison.

For MAM, both repeat attempts pass every computational instrument, including
all three own-command/data-isolation probes. Guided is **21.7% faster** in the
agent phase and **11.9% faster** including assessment, but uses **8.8% more**
fresh-plus-output tokens. It uses 28.5% fewer output tokens and more fresh input;
cached input is also lower. Its command time is higher, 30.4 versus 14.6 seconds,
so this is not a claim that the native calculation itself runs faster. Two
recovered coordinate/year-axis schema errors remain in its trace.

The same-condition MAM ledger now contains two fresh matched pairs:

| Across both precision-condition MAM pairs | Python | Guided ACCORD |
| --- | ---: | ---: |
| Computationally valid completions / attempts | 1 / 2 | 2 / 2 |
| Fresh input + output, including failures | 111,519 | 112,298 |
| Agent seconds, including failures | 355.1 | 267.9 |
| Fresh input + output per valid completion | 111,519 | 56,149 |

Guided used 26.7% and 21.7% less agent time in the two pairs. The first pair's
6.6% fresh-plus-output saving reverses to an 8.8% increase in the repeat; total
fresh-plus-output across two attempts is 0.7% higher for guided. The resources
per valid completion reflect one Python budget failure, not an established
population cost ratio. Both pairs use one historical instance; these counts
do not establish general reliability or statistical significance. The earlier
v1 precision-confounded phase is retained separately and excluded from this
same-condition ledger.

## Accounting and implications

This expansion stops at its declared six agent attempts, with no retries or
additional judging. Total usage is **952,893 tokens**: 687,104 cached input,
227,682 fresh input and 38,107 output. Fresh input plus output is 265,789.
Direct paid API spending is **$0**; subscription invoice costs are unknown.
The changed mix of fresh, cached and output tokens prevents a general monetary
saving claim. API-guide/toy overhead and recovered agent errors are included.

The promising next experiment is another complete calibration workflow, with
the same explicit separation of scientific completion, portability and
resources. Routine preparation/combination also deserves a leaner discovery
condition: the current bundle mandates reading a guide and running a toy on
every fresh attempt. A portable replay check could catch fixed actor-workspace
paths before submission without revealing private reference answers. These are
next experiments, not unrecorded changes to this comparison.

The [verified results](../experiments/tooling-breadth-verified-results-2026-10-08.json)
pin the frozen plan, six attempts, source/substrate/artifact manifests and
independent native-use reviews. They retain raw descriptive resource deltas
but expose efficiency comparisons only when both arms pass and native dataflow
is verified. The [raw collection](../experiments/tooling-breadth-results-2026-10-08.json)
is preserved separately. No task fingerprint or scientific source was changed.
