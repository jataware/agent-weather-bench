# The proposed starting set of 25 tasks

Status: proposal agreed in discussion on 6 October 2026. Nothing in this document
is implemented beyond what the "Where it lives" column says. No task contract,
rubric, evaluator or approval field was changed by writing it.

## The question, stated twice

**In plain terms.** Which forecasting jobs should this benchmark ask AI agents to
do first, so that the results tell us which models and agent harnesses are
accurate, cheap and fast, and so that a few jobs remain hard even for the best
agents?

**In technical terms.** Which task templates form the initial collection, drawn
from the ten packaged tasks in this repository and the sixteen cases in the
earlier `weather-skills-bench` repository, such that (a) every template can be
instantiated at many locations and time windows, (b) the collection covers the
main kinds of subseasonal and seasonal forecasting work, and (c) a subset
carries a continuous skill score with no ceiling?

## Terms used in this document

- **Task template.** A task whose brief, data request and answer key take
  parameters such as region, dates or forecast issue. One template yields many
  instances.
- **Instance.** One template with its parameters fixed.
- **Brief.** The text given to the agent. The proposed cap is about 150 words.
  A brief states the product (quantity, region, period, units, answer fields)
  and omits the procedure.
- **Level 1 (the bench).** The agent produces a valid output. The result is pass
  or fail, reported with cost, time and tokens.
- **Level 2 (the leaderboard).** The agent improves its output. The result is
  forecast skill against a baseline on a private period. Level 2 is a separate
  submission with its own format and leakage gate, and the Level 1 result is
  shown beside the Level 2 score and does not gate it (see
  [the assessment format](assessment-format.md)). Level 2 uses the same brief
  and data as Level 1 plus one sentence and a fixed budget of feedback queries.
- **Subseasonal.** Forecasts about two to six weeks ahead.
- **Seasonal.** Forecasts of a three-month total or mean, issued about a month
  ahead.
- **Old repository.** `ACCORD/weather-skills-bench`, built 29–30 September 2026.
  Its cases are in `weather-skills-bench/cases/<id>.json`.
- **This repository.** `ACCORD/agent-weather-bench`. Its packaged tasks are in
  `tasks/<id>/`.
- **Frontier model.** Claude Fable 5.1 or GPT-6 Astra in the runs cited here.
- **Cheap model.** GPT-6 Luna, Gemini 3.1 Flash-Lite, or an open-weight model of
  9 billion parameters or fewer in the runs cited here.
- **CCA.** Canonical correlation analysis, a standard statistical method for
  seasonal forecasting.
- **Indian Ocean Dipole.** A sea-surface-temperature index, the west Indian
  Ocean minus the east, that drives East African rainfall.
- **Madden–Julian Oscillation.** The main tropical driver of subseasonal
  weather, tracked by a two-component index.

## The set exists to compare whole systems, not only models

**A system is a model plus everything around it.** The benchmark compares three
things, one at a time, with the others held fixed:

- *The model.* More and less powerful language models, from small open-weight
  models to frontier models.
- *The harness.* The agent loop that drives the model, such as the built-in
  driver, the Codex adapter, or the experimental `rx` research harness.
- *The substrate.* The tools and knowledge supplied to the agent. The three of
  first interest are the Rhiza Research weather-skills catalog
  (`ACCORD/weather-skills-catalog`), the ACMAD data library `acmadDL`
  (`ACCORD/acmadDL`), and the `AfricaS2S` seasonal forecasting library
  (`ACCORD/africas2s`).

**Four questions are asked of every system.**

1. *Does it meet the bar?* Which tasks does the system pass, and under what
   conditions of model, harness, substrate and budget?
2. *What does it cost?* Dollars, tokens and time to a solution, with failed
   attempts included.
3. *What is a substrate worth?* How much does a given skill set or library
   change the pass rate and the cost, compared with the same model and harness
   without it?
4. *Does work accumulate?* When a system has already done one task, how much
   cheaper and faster is the next related one?

**The fourth question is why tasks are templates.** Episodes stack. A system
that has built the workflow for a seasonal forecast for Ethiopia should find
the same forecast for Kenya or Nigeria close to a change of parameters. The
measurement runs the same template at a new location with the system's earlier
work retained, and again with it reset, and compares cost, tokens, time and
pass rate. The harness already supports this through `--parent RUN_ID` and the
sequence files in `experiments/`; the comparison rules are in the top-level
README under "What we measure".

**Substrate use is monitored, not assumed.** A substrate that is mounted but
never opened measures availability, not use. The substrate-use monitor
contributed in pull request #1 (`weatherbench/substrate_use.py`, credited in
these documents to Neil Hausmann) records for every run whether the agent
listed, read or ran its substrate, and at which step it first did so. That
monitor is a standing part of every run record and of the proposed assessment
format.

**The earlier work already ran these comparisons in a small way.** The
1 October pilot ran three models under three substrate conditions (none, the
Rhiza catalog, and the ACCORD libraries) on one seasonal task, with a follow-up
episode. The old repository ran thirteen models with and without the skills
catalog. Neither set of substrate conditions has been ported to the current
harness: `systems/` holds model and adapter configurations only.

## The set has three tiers, ordered by how long one run takes

- **The diagnostic pack takes seconds per item.** It holds ten one-step data
  operations and counts as one entry, so that ten easy items do not outweigh
  the real tasks.
- **Workflow tasks take minutes.** Each chains several steps: fetch, interpret,
  compute, deliver. These separate cheap models from frontier models.
- **Research tasks take tens of minutes.** Each has both levels. These separate
  frontier models from one another by skill.

## Rows 1–16 already exist in one of the two repositories

Columns:

- **#** — the row number used throughout the design discussion.
- **Task** — a short name.
- **Where it lives** — the existing case or package identifier. "old:" means
  the old repository; "new:" means this repository.
- **Varies by** — the parameters that turn the task into a template.
- **Mode** — how Level 1 is assessed, as defined in
  [the assessment format](assessment-format.md). *Product* checks the requested
  quantity under any defensible convention. *Process* also checks that the
  method conforms to a named standard. *Outcome* checks only that the
  submission is valid: format, units, time alignment, coverage and no leakage. The Level 2 submission is always assessed
  in outcome mode. Interpretation checks apply in every mode.
- **Level 2** — whether an optimize level exists. "Yes" means private held-out
  targets already exist. "Later" means the task needs more data first.
- **Evidence so far** — observed outcomes. Old-repository counts are Python-arm
  passes over scored attempts, pooled across several studies with different
  settings, so they are descriptive only. New-repository outcomes are single
  attempts graded without the model judge.

| # | Task | Where it lives | Varies by | Mode | Level 2 | Evidence so far |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Diagnostic pack (ten one-step data operations) | old: `calendar-alignment`, `duration-weighted-rainfall`, `ensemble-flux-spread`, `forecast-observation-bias`, `grid-alignment`, `iod-anomaly`, `legacy-accumulation`, `multimodel-disagreement`, `rainfall-completeness`, `rolling-nonoverlap` | Random seed | Product | No | Fable and Sonnet 10 of 10; Gemini Flash-Lite 6; Qwen 9B 3; Llama 1B and 3B 0 |
| 2 | Kenya rainfall outlook | old: `e2e-kenya-rainfall` | Forecast issue, rectangle | Product | No | Frontier 4 of 6 |
| 3 | Kenya heat outlook | old: `e2e-kenya-heat`, `e2e-kenya-heat-cached-v3` | Forecast issue, rectangle | Product | No | Frontier passes; models of 9B or fewer mostly fail |
| 4 | Kenya forecast revision | old: `e2e-kenya-revision`; converted: `templates/kenya-forecast-revision` | Issue pair, rectangle | Product | No | Frontier 4 of 5; Gemini Flash-Lite 0 of 3 |
| 5 | Observed Indian Ocean Dipole index | old: `iod-dmi-observed-skill` | Dates, ocean boxes | Product | No | Never run |
| 6 | Indian Ocean Dipole forecast check | old: `iod-s2s-forecast-skill` | Start date, ocean boxes | Product | No | Never run |
| 7 | Scorecard debugging | new: `weatherbench-verification` | Month, variable, injected faults | Product | No | Luna reproduced the reference numbers |
| 8 | Station verification | new: `station-verification` | Stations, month | Product | Later | Luna partly correct |
| 9 | Paper-versus-code audit | new: `wvg-definition-audit` | Nothing | Product | No | Luna reproduced the numbers 3 of 3 |
| 10 | Probability forecast combination | new: `acmad-objective` | Nothing | Process | Later | Luna passed 1 of 3 |
| 11 | Seasonal rainfall calibration | new: `seasonal-calibration`; converted: `templates/seasonal-rainfall-calibration` | Region, season, start month | Process | Yes | Luna failed 3 of 3 |
| 12 | Short-rains workflow | new: `short-rains-workflow` | Region, season | Process | Yes | Astra passed the numerical checks; Fable ran out of budget |
| 13 | Seasonal CCA reproduction | new: `cca-seasonal-reproduction` | Region, season | Process | Yes | Luna failed; Astra passed |
| 14 | Monthly cyclic calibration | new: `monthly-cycle-calibration` | Region | Process | Yes | Luna partly correct |
| 15 | Weeks 3–4 rainfall | new: `subseasonal-optimization`; converted: `templates/weeks34-rainfall` | Region | Outcome | Yes | Astra beat the raw model by 6.7% |
| 16 | Rainfall downscaling | new: `conservative-downscaling` | Region | Product | Yes | Luna valid, but worse than climatology |

Notes on rows 1–16:

- The old repository's sixteen cases reduce to rows 1–6. The two heat variants
  are one task. The real dipole index task (row 5) supersedes its synthetic
  twin, which stays inside the pack.
- Rows 2, 4 and 6 also have follow-up phases written in
  `archive/pilot-2026-10-01/tasks/`, which ask the agent to reuse its saved code
  on a new forecast issue. Those phases measure reuse.
- Three frontier failures on rows 2 and 4 were caused by an unstated
  convention (whether to clip negative daily rainfall increments), not by an
  agent error. See `weather-skills-bench/results/rainfall-semantics-audit.json`.
- Rows 12–14 need the most rewriting, because their current prompts are the
  supplied algorithm. Their one-sentence briefs would be: "repair this
  workflow's units, then test whether predictor search beats a fixed
  predictor" (12); "reproduce this centre's CCA forecast from its source code"
  (13); "test whether sharing regression slopes across months helps" (14).

## Rows 17–25 fill gaps that variation in place and time does not cover

Columns are the same, except **Why it is needed** replaces the location and
evidence columns, there is no "Varies by" column, and **Starting point** names
any existing written material.

| # | Task | Why it is needed | Mode | Level 2 | Starting point |
| --- | --- | --- | --- | --- | --- |
| 17 | Rainy-season onset and dry spells | No existing task forecasts an event date or a spell, only totals and means | Process | Yes | Candidate 5 in `docs/task-candidate-shortlist.md` |
| 18 | Probabilistic forecast verification | Rows 6–8 score single-value forecasts; none tests the reliability of probabilities | Process | No | None |
| 19 | Multi-model combination with hindcasts | Row 10 averages one case by a fixed rule; none learns weights across models | Process | Yes | None |
| 20 | Test a published predictor claim | Row 9 checks a definition; none checks whether a paper's claimed skill holds on held-out years | Process | Yes | Family C in `docs/task-portfolio.md` |
| 21 | Beat the regional consensus forecast | No existing task has a bar set by a real forecasting centre | Process | Yes; frontier-hard | Consensus reconstruction in `ACCORD/from_icpac/`; hindcast coverage unchecked |
| 22 | Probabilistic weeks 3–4 and 5–6 outlook | Row 15 is single-value error; this is tercile probabilities for rainfall and temperature | Process | Yes | Candidate 1 in the shortlist; its data endpoints failed an earlier audit |
| 23 | Weekly forecasting with observation updates | The agent's frozen program runs week by week and may learn from each released observation | Outcome | Yes; frontier-hard | `docs/frontier-challenge-next.md`; needs a controller that releases observations in date order |
| 24 | Madden–Julian Oscillation forecast check | Mirrors rows 5–6 at the subseasonal timescale | Product | No | None; data access unchecked |
| 25 | Extreme-event probability at weeks 2–3 | Row 3 reports a peak with no skill score; this scores exceedance probabilities | Product | Yes | None |

Two spare candidates exist: a rainfall distribution with dry-day mass
(candidate 8 in the shortlist), and calibrating the Kenya weekly outlook against
observed rainfall.

## The set of 25 breaks down as follows

- **By timescale:** 9 subseasonal (rows 2, 3, 4, 6, 15, 22, 23, 24, 25),
  10 seasonal (rows 10–14, 16, 17, 19, 20, 21), 5 short-range or general
  (rows 5, 7, 8, 9, 18), plus the diagnostic pack.
- **By level:** 13 have an optimize level now or by design, 2 can gain one
  later (rows 8 and 10), and 10 are produce-only.
- **By readiness:** 10 are packaged in this repository, 6 have briefs and
  answer keys in the old repository, and 9 must be built. Three rows are
  converted to the new assessment format: row 4 in product mode, row 15 in
  outcome mode with both levels, and row 11 in process mode.
- **By mode:** 12 product (rows 1–9, 16, 24, 25), 11 process (rows 10–14,
  17–22), and 2 outcome (rows 15 and 23). The assignment of rows 12, 14, 16, 20
  and 25 is tentative.
- **By intended difficulty:** rows 1–10 separate cheap models from frontier
  models; rows 11–20, 22, 24 and 25 separate frontier models by skill; rows 21
  and 23 are the ones frontier agents should not simply pass.

## Four design choices apply to every row

- **Briefs are short.** The current prompts run 3,700 to 10,400 characters and
  supply the procedure. The old briefs run 260 to 1,800 characters and state
  the product. The new set follows the old length.
- **Supplied algorithms become an optional condition.** Files such as
  `tasks/cca-seasonal-reproduction/algorithm.md` move out of the brief and into
  a "method supplied" comparison arm.
- **Tasks are templates.** Location and time window are parameters, so repeats
  are independent instances and private instances cannot have been memorised.
  Today every builder hard-codes one location and one window.
- **Reasonable answers are accepted, and required methods are enforced where a
  standard exists.** Product rows accept any defensible convention. Process
  rows also require conformance to a named standard. The mechanism is in
  [the assessment format](assessment-format.md).

## Limits of this proposal

- **The instance counts are untested.** No one has enumerated the valid regions
  and windows for any template.
- **Four seasonal rows share data.** Rows 11–14 forecast East African rainfall
  from the same sources, so four results there are fewer than four independent
  measurements.
- **Most Level 2 holdouts are small.** Only row 15 has a large private period
  (208 forecast issues across nine cells). Rows 12–14 hold out the same four
  years.
- **Historical observations are public.** A model may know them from training.
  Private instances reduce this risk; only forecasts scored after they are
  frozen remove it.
- **The substrate and reuse comparisons are designed but not set up.** No
  system configuration in the current harness carries the Rhiza catalog, the
  ACCORD libraries or the `rx` harness, and no retained-versus-reset sequence
  has been run on these tasks.
- **The substrate-use monitor sees only part of the picture.** It matches
  `/substrate` paths in command text. It does not see an installed library
  being imported, which is how `acmadDL` and `AfricaS2S` are used. It needs
  extending to cover imports; it should be extended, not replaced.
- **The evidence column is thin.** No row has repeat attempts by more than one
  model under one protocol, so no pass rate here supports a model ranking. The
  three converted rows each have two or three attempts by one cheap model in
  the new format; see [the assessment format](assessment-format.md).
- **No human has approved any task.** Scientific, scoring and redistribution
  approvals remain false for every packaged task.
