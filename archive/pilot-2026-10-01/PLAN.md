# One small experiment, three candidate tasks

Today's outcome is a measured seasonal smoke and three slides in the existing
check-in deck. The bakeoff narrative is a hypothesis: strong agents can build
useful forecasts, skills may reduce work, and maintained scientific software may
make repeated forecasts cheaper and better. We retain contrary results.

| Candidate | Task and follow-up | Rhiza overlap | ACCORD overlap | What is measured |
|---|---|---|---|---|
| Our seasonal case | Calibrate September-issued OND rainfall; apply saved fit to another batch | Acquisition and rainfall-processing guidance/scripts | DeepScale calibration and Rosetta acquisition | Aggregation, validation, RPS, RMSE, reliability, replay, cost and retained fit |
| Emmett's challenging IOD | Forecast and verify two seven-day dipole windows; another issue | OISST/S2S retrieval and IOD helpers | Rosetta S2S retrieval; index code still needed | Exact dates/index/spread/error, replay and cost; too few windows for calibration |
| Brandon's Kenya rainfall | Six weekly maps and regional ensemble summaries; another archived issue | Native Kenya retrieval, aggregation and plots | Rosetta retrieval; little calibration advantage | Exact totals/spread/coverage, replay and cost; no forecast skill without observations |

All are feasible in generic Python given data access. Toolkit overlap is a reason
to test a case, not a guaranteed advantage. Seasonal data is preloaded only in
today's smoke, so the smoke bypasses retrieval strengths in both toolkits.

The shared evaluator uses numerical gates plus one evidence-citing LLM judge
(data/provenance, processing, results/uncertainty, communication, reproducibility).
Report completeness, scientific quality and effort separately. Judge ratings do
not replace numerical checks. No unagreed forecast-skill or calibration threshold
has been invented.

For the smoke, three initial Fable attempts receive equal limits. Each arm then
gets the same follow-up and its saved files, including incomplete work; repairs
are allowed and reported. A follow-up that finishes an incomplete initial attempt
is recovery, not evidence of a previously working maintained substrate. One Haiku
scratch attempt checks whether model choice changes the result. There are no
fresh-workspace follow-up controls, so savings remain descriptive.

Before a larger run: review these results together, improve toolkit discoverability
if the trace warrants it, audit fresh seasonal verification years, and freeze the
chosen task/reference and budgets. Emmett's case additionally needs authenticated
ECDS retrieval and actual valid-date coverage; the scalar climatology clarification
must be accepted. Kenya is the best next case for retrieval/skills overlap, but it
will not establish improved forecast accuracy on its own. Open-web replication
stays a separate condition. No broad parameter sweep has been launched.
