# The template set

The original candidate portfolio has 25 entries in six families. Seven have implemented assessment templates, nine have archived briefs and reference code awaiting conversion, and nine are proposals. Four subsequent executable investigation templates are listed separately below. Automatic validation, trial-attempt review and scientific approval are separate statuses; none has scientific approval. [The roadmap](roadmap.md) gives the plan and [the assessment format](assessment-format.md) gives the mechanism.

## Terms

- **Template.** A task whose brief, data and answer key take parameters such as region, season or forecast issue. One template yields many instances.
- **Instance.** One template with its parameters fixed.
- **Primary question.** Compute a quantity, follow a standard or produce a valid forecast. The legacy mode column below records the original design orientation. Instruments are optional and can coexist; the rubric lists their roles explicitly.
- **Level 2.** A separate optimized forecast submission with private scoring and a development-score budget. Only weeks 3–4 currently implements it; other entries are plans.
- **Status.** *Implemented*: an executable spec, independent computation and planted controls exist. *Reference written*: archived brief and reference code await conversion. *To build*: a proposal. Certification remains a comparison lock after author feedback and scientific review.
- **Evidence.** Historical counts come from different tasks, contracts and settings and are descriptive only. The dated checkpoint and focused-study reports identify current contracts explicitly.
- **Frontier-hard.** An intended challenge for frontier systems; this label is a design hypothesis until attempts establish difficulty.

## The templates

| # | Template | Family | The agent must | Varies by | Mode | Level 2 | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Diagnostic pack | Downscaling and diagnostics | Perform ten one-step data operations: calendar alignment, duration-weighted rainfall, ensemble flux spread, forecast–observation bias, grid alignment, dipole anomaly, legacy accumulation, multi-model disagreement, rainfall completeness and non-overlapping rolling windows. The pack counts as one entry. | random seed | product | no | reference written | frontier models 10 of 10; Gemini Flash-Lite 6; Qwen 9B 3; Llama 1B and 3B 0 |
| 2 | Kenya rainfall outlook | Outlook products | Read a raw provider forecast and produce the weekly rainfall outlook over a rectangle. | forecast issue, rectangle | product | no | reference written | frontier models 4 of 6 |
| 3 | Kenya heat outlook | Outlook products | Read a raw provider forecast and produce the peak-heat outlook over a rectangle. | forecast issue, rectangle | product | no | reference written | frontier models pass; models of 9B parameters or fewer mostly fail |
| 4 | Kenya forecast revision | Outlook products | Report how the rainfall forecast changed between two issues, as an area-weighted mean per period. | issue pair, rectangle | product | no | implemented: spec v3, 5 development instances | Astra: 2 passing checkpoint attempts; earlier Luna counts use older contracts |
| 5 | Observed Indian Ocean Dipole index | Observed indices and verification | Compute the observed dipole index from sea-surface temperature over two ocean boxes. | dates, ocean boxes | product | no | reference written | not yet run |
| 6 | Indian Ocean Dipole forecast check | Outlook products | Score a provider's dipole forecast against the observed index. | start date, ocean boxes | product | no | reference written | not yet run |
| 7 | Scorecard debugging | Observed indices and verification | Find and correct injected faults in a verification scorecard. | month, variable, injected faults | product | no | reference written | gpt-6-luna reproduced the reference numbers |
| 8 | Station verification | Observed indices and verification | Verify gridded forecasts against station observations. | stations, month | product | later | reference written | Historical Luna headline scores correct; combined diagnostic omits a required unit transformation, confirmed by a one-expression Docker repair |
| 9 | Paper-versus-code audit | Observed indices and verification | Check whether a paper's stated definition matches the code that produced its numbers. | none | product | no | reference written | gpt-6-luna reproduced the numbers 3 of 3 |
| 10 | Probability forecast combination | Seasonal forecast production | Retrieve and consolidate component tercile forecasts, preserving complete-vector support; report weighting sensitivity and disagreement. | source outlook | product | later | implemented: `seasonal-objective-consolidation`, spec v1, 1 instance | Luna passes the lean scientific task and both replays; archived packaging task had 1 of 3 passes |
| 11 | Seasonal rainfall calibration | Seasonal forecast production | Calibrate a seasonal rainfall forecast to the WMO guidance: leave-one-out hindcasts, tercile probabilities, skill against climatology. | region, season, start month | process | planned | implemented: spec v4, 3 development instances | Astra: 2 passing checkpoint attempts, including required practice reviews |
| 12 | Short-rains workflow | Seasonal forecast production | Repair the units of a short-rains forecasting workflow, then test whether predictor search beats a fixed predictor. | region, season | process | yes | reference written | GPT-6 Astra passed the numerical checks; Claude Fable ran out of budget |
| 13 | Seasonal CCA reproduction | Seasonal forecast production | Reproduce a bounded CPT-inspired CCA adaptation with nested selection and expanding validation. | outer validation start, target subset | product | planned | implemented: spec v1, 4 instances | Current CCA instance: Astra and Luna both pass with and without ACCORD (4 attempts) |
| 14 | Monthly cyclic calibration | Seasonal forecast production | Reproduce cyclic monthly standardized-slope calibration, nested whole-year selection and target-free production inference. | fixed original regional experiment | process (original design); product implementation | planned | implemented: `monthly-cycle-calibration`, spec v1, 1 instance | Historical Luna nested validation correct, but all 144 constant-comparator production values wrong; independent checks preserve those distinct results |
| 15 | Weeks 3–4 rainfall | Subseasonal forecast production | Forecast weeks 3–4 rainfall from the ensemble; at Level 2, make it as skilful as possible against withheld observations. | region | outcome | yes | implemented: spec v4, 8 instances | Astra checkpoint: 1 passing submission, 1 budget/delivery failure; skill gains uncertain |
| 16 | Rainfall downscaling | Downscaling and diagnostics | Reproduce rank mapping and fine-grid disaggregation while conserving mapped coarse means. | training period, forecast period | product | planned | implemented: spec v2, 4 instances | Both Astra submissions pass after a versioned area-bound grading correction |
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

Subsequent investigations add four templates outside the original 25-entry count:

| Template | Job | Evidence |
| --- | --- | --- |
| `native-rainfall-reconciliation` | Reconcile native accumulated and curator-derived interval-rate deliveries on common valid weeks | Three initial Astra conditions; physical references and source lineage explicit |
| `seasonal-forecast-audit` | Reproduce a candidate evaluation, diagnose its claims and produce valid alternative forecasts | Clean/faulted instances; annual information-boundary and per-deliverable response controls |
| `mam-multimodel-outlook` | Retrieve native monthly forecasts and observations, prepare four centres, calibrate and issue a MAM rainfall outlook | Independent and native-tool parity on real data; fresh source-service reruns; bounded agent comparison |
| `mam-forecast-synthesis` | Choose a calibration/combination method for twelve blind MAM seasons, with validity and RPS reported separately | Controls and independent scoring pass; expert failed the climatology-improvement gate, so no model attempt |

These bring the executable template count to eleven, without implying eleven
independent weather datasets or scientific approval.

The MAM task uses a prescribed equal-centre combination; it does not complete
portfolio entry 19's proposed learned weighting method. Its first 18-cell
retrospective service window is a workflow experiment, not national coverage.

- **By family:** outlook products 6 (templates 2, 3, 4, 6, 24, 25); observed indices and verification 5 (5, 7, 8, 9, 18); seasonal forecast production 6 (10, 11, 12, 13, 14, 19); subseasonal forecast production 4 (15, 17, 22, 23); research claims and consensus 2 (20, 21); downscaling and diagnostics 2 (1, 16).
- **By timescale:** 9 subseasonal (templates 2, 3, 4, 6, 15, 22, 23, 24, 25), 10 seasonal (10–14, 16, 17, 19, 20, 21), 5 short-range or general (5, 7, 8, 9, 18), plus the diagnostic pack.
- **By mode:** 14 product (templates 1–10, 13, 16, 24, 25), 9 process (11, 12, 14, 17–22) and 2 outcome (15, 23). Entry 10's lean implementation computes a quantity; its archived design was a process task. The mode of templates 12, 14, 16, 20 and 25 is tentative.
- **By level:** 13 have Level 2 now or by design, 2 can gain it later (templates 8 and 10), and 10 are Level 1 only.
- **By status:** 7 implemented (templates 4, 10, 11, 13, 14, 15, 16), 9 with archived reference code, 9 to build.
- **By intended difficulty:** templates 1–10 aim to separate smaller models from frontier models; templates 11–20, 22, 24 and 25 aim to distinguish scientific practice or skill; templates 21 and 23 aim for frontier difficulty. These are hypotheses, not established capability boundaries.
- **By duration:** the diagnostic pack takes seconds per item; the workflow templates take minutes, because each chains fetch, interpret, compute and submit; the research templates take tens of minutes and carry both levels.

## Four design choices apply to every template

- **Briefs are short.** A brief names the product, units and required claims. A prescribed reproduction task also supplies its algorithm as input.
- **Optional guidance is a supplement.** A template's `conventions.md` is handed to the agent only with `--supply`. Prescribed reproduction tasks always stage the algorithm that defines their job. Availability of optional guidance is recorded as an experimental condition.
- **Instances vary the job.** Region and time window are parameters. A fresh attempt starts without earlier agent state; a run with `--parent` receives earlier work. Fresh state does not establish statistical independence, and public historical data may have been encountered in training.
- **Defensible answers pass, and standards are enforced where one exists.** Product templates accept any defensible reading of the brief. Process templates also require conformance to a named standard.

## The limits

- **The instance counts are not independent difficulty evidence.** Implemented templates enumerate candidate instances; proposed portfolio parameters remain unvalidated.
- **Four seasonal templates share data.** Templates 11–14 forecast East African rainfall from the same sources, so four results there are fewer than four independent measurements.
- **Most forecast holdouts are small.** Template 15 has a larger controller-withheld period (208 weekly issues across nine cells), with overlapping target windows. The archived tasks behind templates 12–14 use the same four years; their coverage must be checked before pooling results.
- **Historical observations are public.** A model may know them from training. Private instances reduce the risk; only forecasts scored after they are frozen remove it.
- **The tooling studies are small.** The initial checkpoint compares Python and Rhiza on three tasks with Astra. Focused follow-ups compare Python and ACCORD on two reproductions, including a matched Luna CCA pair. Five subsequent attempts on delivery reconciliation and forecast audit all pass; no executable weather-helper use is observed in those attempts. A later [guided MAM pair](mam-efficiency-study-2026-10-08.md) has genuine helper use, one valid guided completion versus an incomplete Python submission, 6.6% fewer fresh-input-plus-output tokens and 26.7% less agent time. That is an observed single-pair signal, not replicated efficiency or a hard scientific boundary. Retained-work comparisons remain unrun. The [two-track investigation](two-track-investigation-2026-10-08.md) records the current limits.
- **Tooling-use evidence is partial.** Controller traces record catalog paths and library import evidence. These show observed access, not whether tooling caused a better answer.
- **The tooling follow-up is mixed.** The [breadth study](tooling-breadth-study-2026-10-08.md) repeats MAM with both arms passing: guided is 21.7% faster but uses 8.8% more fresh-plus-output tokens. Rhiza adds overhead on revision; native consolidation's correct initial arrays fail command portability. All three guided attempts substantively use helper outputs. The MAM time signal repeats on one instance, while general token savings remain unestablished.
- **The evidence column is thin.** CCA has two backbones under matched focused conditions, but one attempt per condition on one instance. No count supports a stable model ranking. The original three templates also have 36 historical attempts by one model under earlier contracts; those counts do not describe the new policy. See the [checkpoint](checkpoint-2026-10-08.md), [focused study](focused-study-2026-10-08.md) and [historical results](results.md).
- **Partial numerical success is not saturation.** The [historical error localization](../experiments/historical-science-slices-2026-10-08.json) finds a wrong monthly production comparator despite correct nested validation, and a wrong combined station diagnostic despite correct headline scores. A [new judge calibration](../experiments/failure-judge-calibration-eight-call-2026-10-08.json) misses the station error under broad method review, while focused component questions catch it even without controller numeric diagnostics. These are selected failures, not a population difficulty or judge accuracy estimate.
- **No human has approved any template.** Scientific, scoring and redistribution approvals remain false for every template.
