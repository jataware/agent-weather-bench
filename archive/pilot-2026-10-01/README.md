# Agent Weather Bench

Agent Weather Bench studies what tooling, knowledge, and retained work allow AI
agents to carry out verifiable subseasonal and seasonal forecasting research.
The repository was renamed from `accord-weather-pilot`; the completed ACCORD
pilot below is its starting point.

Start the benchmark design discussion in [docs/README.md](docs/README.md): the
original proposal, editorial review and framework design, a candidate task
portfolio, and a proposed rubric tree for the existing seasonal experiment.
These are design drafts; the current runner still uses the pilot task contracts
and shared rubric. Historical experiment names, results and image tags retain
their original identifiers.

Three standalone [task packages](../../tasks/README.md) are now prepared for
[joint review](../../docs/task-package-review.md), with source records, hashed local
inputs, rubric trees and static numerical checks. Benchmark-wide task sequences
are the main accretion design, with optional explicit follow-ups. Preparation makes
no model calls or agent attempts; the pilot launch controls remain closed.

## Completed ACCORD pilot

Start with the [updated check-in deck](2026-10-01-accord-checkin.pptx),
[weather section](slides/weather-slides.pptx), [five-slide results extract](slides/revised-slides.pptx), [table alternative](slides/revised-tables.pptx), or [results page](report.html).
The original presentation is preserved in `slides/checkin-original.pptx`.

## Revised comparison — complete

Same seasonal task and supplied monthly ECMWF/CHIRPS data across all conditions.
Nine initial attempts and three Fable follow-ups; no response truncations.

| Initial setup | Checks | Tokens | Minutes | Agent USD |
|---|---:|---:|---:|---:|
| Haiku / scratch | 3/12 | 776,678 | 4.54 | 0.918 |
| Haiku / Rhiza | 7/12 | 748,020 | 3.76 | 0.858 |
| Haiku / ACCORD | 5/12 | 764,137 | 4.09 | 0.884 |
| Sonnet / scratch | 9/12 | 86,410 | 1.56 | 0.265 |
| Sonnet / Rhiza | 12/12 | 132,946 | 1.64 | 0.360 |
| Sonnet / ACCORD | 9/12 | 213,754 | 2.57 | 0.555 |
| Fable / scratch | 12/12 | 260,515 | 4.92 | 3.361 |
| Fable / Rhiza | 11/12 | 360,047 | 4.88 | 4.422 |
| Fable / ACCORD | 12/12 | 365,355 | 4.10 | 4.387 |

Sonnet + Rhiza matched Fable scratch's check count with 49% fewer tokens, 67% less
time and 89% lower API cost. Their initial RPS values were nearly identical.
Both Sonnet scratch and Sonnet + ACCORD missed three checks because of units metadata;
the aggregated arrays matched the reference and rainfall was positive. Sonnet + ACCORD
used the installed library and passed independent offline replay, but cost more than
Sonnet + Rhiza in this attempt. Original scores and judge ratings are preserved;
`failure-diagnostics.json` explains the failures. The extension cost $0.62 including its judge.
Fable + Rhiza failed offline replay because it wrote into the read-only source
workspace. Skills did not improve every model on every measure.

Haiku + ACCORD stopped at its token limit with 5/12 checks: training aggregation and
development output checks passed, but delivery, frozen prediction and replay remained
incomplete. No retry was made. The run and judge cost $0.93 together.

ACCORD uses the installed `EnsembleRegressionMethod` fit/save/load/predict API.
`train("ereg")` is not supported by the separate downscaling registry; documenting
that distinction and the working class resolved the earlier integration problem.
The independent synthetic fit/save/load test passed with refitting disabled.

| Fable follow-up | Checks | Tokens | Minutes | Agent USD |
|---|---:|---:|---:|---:|
| Scratch | 12/12 | 334,053 | 3.76 | 3.770 |
| Rhiza | 11/12 | 213,139 | 2.52 | 2.389 |
| ACCORD | 12/12 | 165,576 | 2.59 | 1.889 |

ACCORD's follow-up used 50% fewer tokens, cost 50% less and took 31% less time than
scratch. Across initial plus follow-up, ACCORD cost $6.28 versus $7.13 for scratch
(12% less). All three retained unchanged fitted state and cached training arrays.
Direct application of saved predictors took 1–2 seconds with no LLM calls.
ACCORD did not beat scratch's forecast RPS on the second batch; accuracy and cost
remain separate measures.

**Total recorded API spend: $60.15**, including both experiment versions, setup
diagnostics and judging. Prior interrupted requests may add unrecorded cost;
this is not an account-reconciled invoice. The user ceiling was $100. No larger
benchmark or open-web replication has been launched.

The forecast-quality slide (19 in the check-in deck) compares all three Fable arms
against raw ECMWF and the simple model-climatology baseline. All three have lower
RPS than raw in both batches, while the simple baseline wins in 2007–08. ACCORD
has no demonstrated forecast-accuracy advantage. Scores are read directly from
`results/revision-summary.json`; no additional agent runs were needed.

## Interpretation

These are individual illustrative attempts, not a stable model ranking. Rhiza
agents received catalog names/descriptions/paths but did not execute its scripts
or open individual skill files. The comparison measures that skills-enabled
configuration. ACCORD did invoke its installed scientific implementation.

Training is 1993–2004; private-to-agent forecast batches are 2005–06 and 2007–08.
The designer previously inspected these development years. Two years cannot
establish probabilistic calibration. Identical monthly inputs were supplied, so
live data discovery/download savings are not measured. Retained-data/cache use
and network bytes are recorded separately. There are no fresh-workspace follow-up
controls. All arms may save code, data, fitted state and notes.

Numerical checks, independent offline replay and five evidence-citing judge
criteria are reported separately. The strict overall label remains partial when
the judge lists any concern, even if all checks and all five ratings pass. Judge
statements are reviewed against artifacts; diagnostics document incorrect judge
inferences rather than silently altering its ratings.

## Files and reproducibility

- `revision/haiku-accord-extension.json`: final initial condition, budget and recorded cost.
- `revision/messaging-audit.json`: weather-slide corrections; older heat benchmark archived.
- `slides/assets/kenya-boundary.geojson`, `kenya-study-area.json`: locator boundary and study bounds.
- `revision/sonnet-accord-extension.json`: authorized extra condition, budget and recorded cost.
- `slides/assets/tercile-example.{png,svg,json}`: actual forecast map and source provenance.
- `revision/PLAN.txt`, `revision/{haiku,sonnet,fable}.json`: frozen protocol and budgets.
- `results/revision-summary.json`: model IDs, tokens, time, dollars, checks, metrics and audit.
- `runs/revision-v1/*/frozen/`: saved code, inputs, fitted models, reports and figures.
- `runs/revision-v1/*/evaluation/`: predictions from frozen code, without verification observations.
- Per-run `events.jsonl`, `system.txt`, `prompt.txt`, `config.json`, `judge*.json`,
  `audit.json`, `reuse.json`: raw evidence and exact configuration.
- `results/revision-direct-reuse.json`: direct saved-predictor timings.
- `tasks/{seasonal,iod,kenya}.yaml`, `PLAN.md`: the original three candidate tasks.
- `runs/smoke-v3/`, `slides/checkin-smoke-v3.pptx`: earlier experiment, not pooled.
- `runs/smoke-v1/` and `smoke-v2/`: excluded infrastructure diagnostics, with costs.

The fifth slide simplifies the auto-science loop from `../docs/presentations/toward-auto-science.html`.
It describes a research direction, not a measured finding from this pilot.
Old heat-benchmark slides 11–14 are labelled archived and hidden in the main slideshow;
slide 15 now describes only the three actual seasonal arms. Slide numbers are preserved.
Slides 17–18 use fixed colors: scratch gray, Rhiza blue, ACCORD red; on slide 18,
light bars are initial attempts and dark bars are follow-ups. The Kenya locator is on
slide 16 beside the probability grid; slide 18 explains the later forecast years.

One checker correction excluded optional session notes from scientific replay;
all declared answer fields and numerical arrays still must match. It was applied
to every revised submission. The affected original score/judgment is retained
under `evaluation-revisions`, with one new judge call. No agent artifact changed.

The sandbox isolates arm packages/docs, host secrets, other arms and reference
answers. Common images/data are pinned. Frozen prediction runs have no network.
`runs/` and `.private/` remain locally retained and ignored by Git. Image rebuilding
on a clean machine requires the existing base-image dependency locks.

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m revision.collect
.venv/bin/python -m revision.present
.venv/bin/python -m smoke.preview revised-slides
.venv/bin/python -m smoke.render revised-slides
```

Do not rerun the agent launch scripts into existing directories. The launch guard
is closed after this completed suite; new scientific comparisons need review.
