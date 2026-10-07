# The template set

The set holds 25 templates in six families. Three are certified, thirteen have a brief and a reference answer that await conversion to a spec, and nine are to be built. This page is the full list. [The roadmap](roadmap.md) gives the plan and [the assessment format](assessment-format.md) gives the mechanism.

## Terms

- **Template.** A task whose brief, data and answer key take parameters such as region, season or forecast issue. One template yields many instances.
- **Instance.** One template with its parameters fixed.
- **Mode.** How Level 1 is checked. *Product*: the controller compares the requested quantity with a private reference under every defensible reading of the brief. *Process*: the product, plus conformance to a named standard, step by step. *Outcome*: the submission is valid in format, units, alignment, coverage and leakage, and the forecast is scored against withheld observations.
- **Level 2.** The same template run for skill on a leaderboard, with private held-out targets. "Later" means the targets must be built first.
- **Status.** *Certified*: the spec passes the five certification tests in the offline runtime. *Reference written*: a brief and an answer key exist and await conversion to a spec. *To build*: nothing exists beyond the row.
- **Evidence.** Attempts under the current assessment format are counted as headline passes. Counts before it are descriptive only: they come from several studies with different settings and no judge.
- **Frontier-hard.** A template a frontier agent should not simply pass.

## The templates

| # | Template | Family | The agent must | Varies by | Mode | Level 2 | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Diagnostic pack | Downscaling and diagnostics | Perform ten one-step data operations: calendar alignment, duration-weighted rainfall, ensemble flux spread, forecast–observation bias, grid alignment, dipole anomaly, legacy accumulation, multi-model disagreement, rainfall completeness and non-overlapping rolling windows. The pack counts as one entry. | random seed | product | no | reference written | frontier models 10 of 10; Gemini Flash-Lite 6; Qwen 9B 3; Llama 1B and 3B 0 |
| 2 | Kenya rainfall outlook | Outlook products | Read a raw provider forecast and produce the weekly rainfall outlook over a rectangle. | forecast issue, rectangle | product | no | reference written | frontier models 4 of 6 |
| 3 | Kenya heat outlook | Outlook products | Read a raw provider forecast and produce the peak-heat outlook over a rectangle. | forecast issue, rectangle | product | no | reference written | frontier models pass; models of 9B parameters or fewer mostly fail |
| 4 | Kenya forecast revision | Outlook products | Report how the rainfall forecast changed between two issues, as an area-weighted mean per period. | issue pair, rectangle | product | no | certified: spec v2, 5 instances | 4 of 4 attempts passed (gpt-6-luna) |
| 5 | Observed Indian Ocean Dipole index | Observed indices and verification | Compute the observed dipole index from sea-surface temperature over two ocean boxes. | dates, ocean boxes | product | no | reference written | not yet run |
| 6 | Indian Ocean Dipole forecast check | Outlook products | Score a provider's dipole forecast against the observed index. | start date, ocean boxes | product | no | reference written | not yet run |
| 7 | Scorecard debugging | Observed indices and verification | Find and correct injected faults in a verification scorecard. | month, variable, injected faults | product | no | reference written | gpt-6-luna reproduced the reference numbers |
| 8 | Station verification | Observed indices and verification | Verify gridded forecasts against station observations. | stations, month | product | later | reference written | gpt-6-luna partly correct |
| 9 | Paper-versus-code audit | Observed indices and verification | Check whether a paper's stated definition matches the code that produced its numbers. | none | product | no | reference written | gpt-6-luna reproduced the numbers 3 of 3 |
| 10 | Probability forecast combination | Seasonal forecast production | Combine tercile probability forecasts by a published objective rule. | none | process | later | reference written | gpt-6-luna passed 1 of 3 |
| 11 | Seasonal rainfall calibration | Seasonal forecast production | Calibrate a seasonal rainfall forecast to the WMO guidance: leave-one-out hindcasts, tercile probabilities, skill against climatology. | region, season, start month | process | yes | certified: spec v3, 3 instances | 2 of 4 attempts passed (gpt-6-luna) |
| 12 | Short-rains workflow | Seasonal forecast production | Repair the units of a short-rains forecasting workflow, then test whether predictor search beats a fixed predictor. | region, season | process | yes | reference written | GPT-6 Astra passed the numerical checks; Claude Fable ran out of budget |
| 13 | Seasonal CCA reproduction | Seasonal forecast production | Reproduce a regional centre's canonical-correlation-analysis forecast from its source code. | region, season | process | yes | reference written | GPT-6 Astra passed; gpt-6-luna failed |
| 14 | Monthly cyclic calibration | Seasonal forecast production | Test whether sharing regression slopes across months improves a monthly calibration. | region | process | yes | reference written | gpt-6-luna partly correct |
| 15 | Weeks 3–4 rainfall | Subseasonal forecast production | Forecast weeks 3–4 rainfall from the ensemble; at Level 2, make it as skilful as possible against withheld observations. | region | outcome | yes | certified: spec v3, 8 instances | 2 of 3 attempts passed (gpt-6-luna); GPT-6 Astra beat the raw model by 6.7% at Level 2 |
| 16 | Rainfall downscaling | Downscaling and diagnostics | Downscale rainfall to a fine grid while conserving the coarse totals. | region | product | yes | reference written | gpt-6-luna valid, but worse than climatology |
| 17 | Rainy-season onset and dry spells | Subseasonal forecast production | Forecast the onset date of the rainy season and the dry spells within it. No other template forecasts an event date. | region, season | process | yes | to build | — |
| 18 | Probabilistic forecast verification | Observed indices and verification | Verify probabilistic forecasts with the standard scores: Brier, ranked probability and reliability. | region, season | process | no | to build | — |
| 19 | Multi-model combination with hindcasts | Seasonal forecast production | Learn combination weights across several models from their hindcasts. | region, season | process | yes | to build | — |
| 20 | Test a published predictor claim | Research claims and consensus | Test whether a paper's claimed predictor skill holds on held-out years. | paper, region | process | yes | to build | — |
| 21 | Beat the regional consensus forecast | Research claims and consensus | Produce a seasonal forecast with better backcast skill than the regional centre's consensus forecast. The consensus reconstruction exists in `ACCORD/from_icpac/`; its hindcast coverage is unchecked. | region, season | process | yes; frontier-hard | to build | — |
| 22 | Probabilistic weeks 3–4 and 5–6 outlook | Subseasonal forecast production | Issue tercile probability outlooks for rainfall and temperature at weeks 3–4 and 5–6. The data endpoints failed an audit and need a new source. | region, forecast issue | process | yes | to build | — |
| 23 | Weekly forecasting with observation updates | Subseasonal forecast production | Submit a frozen program that forecasts week by week and may learn from each observation as the controller releases it in date order. | region, season | outcome | yes; frontier-hard | to build | — |
| 24 | Madden–Julian Oscillation forecast check | Outlook products | Score a provider's Madden–Julian Oscillation forecast against the observed two-component index. Data access is unchecked. | start date | product | no | to build | — |
| 25 | Extreme-event probability at weeks 2–3 | Outlook products | Forecast the probability of exceeding a threshold at weeks 2–3 and score it. | region, forecast issue, threshold | product | yes | to build | — |

For the templates to build, the parameters are proposed. Two spare candidates exist: a rainfall distribution with dry-day mass, and calibrating the Kenya weekly outlook against observed rainfall.

## The breakdown

- **By family:** outlook products 6 (templates 2, 3, 4, 6, 24, 25); observed indices and verification 5 (5, 7, 8, 9, 18); seasonal forecast production 6 (10, 11, 12, 13, 14, 19); subseasonal forecast production 4 (15, 17, 22, 23); research claims and consensus 2 (20, 21); downscaling and diagnostics 2 (1, 16).
- **By timescale:** 9 subseasonal (templates 2, 3, 4, 6, 15, 22, 23, 24, 25), 10 seasonal (10–14, 16, 17, 19, 20, 21), 5 short-range or general (5, 7, 8, 9, 18), plus the diagnostic pack.
- **By mode:** 12 product (templates 1–9, 16, 24, 25), 11 process (10–14, 17–22) and 2 outcome (15, 23). The mode of templates 12, 14, 16, 20 and 25 is tentative.
- **By level:** 13 have Level 2 now or by design, 2 can gain it later (templates 8 and 10), and 10 are Level 1 only.
- **By status:** 3 certified (templates 4, 11, 15), 13 with a reference written, 9 to build.
- **By intended difficulty:** templates 1–10 separate cheap models from frontier models; templates 11–20, 22, 24 and 25 separate frontier models by skill; templates 21 and 23 are frontier-hard.
- **By duration:** the diagnostic pack takes seconds per item; the workflow templates take minutes, because each chains fetch, interpret, compute and submit; the research templates take tens of minutes and carry both levels.

## Four design choices apply to every template

- **Briefs are short.** A brief runs 260 to 1,800 characters and states the product: quantity, region, period, units and answer fields. It does not state the procedure.
- **Methods and conventions are supplements.** A method description and a template's `conventions.md` are handed to the agent only with `--supply`, so a run with and a run without one measure how much of the difficulty lies in knowing the conventions and how much in carrying them out.
- **Repeats are instances.** Region and time window are parameters, so repeats are independent and private instances cannot have been memorised. A second instance of the same template is a second episode: the agent is given its earlier submission and decides what to reuse.
- **Defensible answers pass, and standards are enforced where one exists.** Product templates accept any defensible reading of the brief. Process templates also require conformance to a named standard.

## The limits

- **The instance counts are untested.** No one has enumerated the valid regions and windows for any template beyond the three certified ones.
- **Four seasonal templates share data.** Templates 11–14 forecast East African rainfall from the same sources, so four results there are fewer than four independent measurements.
- **Most Level 2 holdouts are small.** Only template 15 has a large private period (208 forecast issues across nine cells). Templates 12–14 hold out the same four years.
- **Historical observations are public.** A model may know them from training. Private instances reduce the risk; only forecasts scored after they are frozen remove it.
- **The tooling comparisons are designed but not set up.** No system definition carries the Rhiza catalog, the ACCORD libraries or the `rx` harness, and no retained-versus-reset episode sequence has been run on these templates.
- **The tooling-use monitor sees part of the picture.** It matches tooling paths in command text and does not see an installed library being imported, which is how `acmadDL` and `AfricaS2S` are used. It is to be extended, not replaced.
- **The evidence column is thin.** No template has repeat attempts by more than one model under one protocol, so no count here supports a model ranking. The three certified templates have 36 attempts by one cheap model: 25 under the first contract and 11 under the current one. [The results](results.md) give the tables.
- **No human has approved any template.** Scientific, scoring and redistribution approvals remain false for every template.
