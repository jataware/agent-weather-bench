# Efficiency and forecasting difficulty

The two investigations answer different questions. The efficiency track asks
whether Luna can produce the same valid MAM outlook with less inference and
execution work using weather tools. The difficulty track asks whether Luna can
meet a meaningful forecasting objective that leaves scientific choices open.
The [plan](../experiments/two-track-investigation-2026-10-08.yaml) bounds model
attempts, preserves previous evidence and shares two scientific workers across
the tracks.

## Efficiency

Compare fresh Luna attempts on the unchanged `mam-multimodel-outlook` instance:
general Python against native acmadDL/AfricaS2S with a concise, tested API guide.
The backbone, reasoning effort, scientific task, data, compute and budgets match.
Only the weather packages and their discovery material differ. An initial pair
may be followed by one informative replication pair; failures count in the
completion and resource totals.

The comparison records uncached input, cached input and output tokens separately,
agent time, command time and assessment wall time. It checks actual helper use,
not just imports. Direct API spend and subscription token accounting are
different measures: these subscription runs cannot establish invoice savings.
The previous four attempts remain a discovery/budget study, rather than serving
as the control arm for this fresh experiment.

The first fresh pair completed but failed the float64 precision contract: both
summed monthly CHIRPS observations in float32 before converting the total.
Independent reconstruction confirmed their algorithms otherwise agree. That
pair also exposed a probe defect: v1 promoted the whole observation file while
changing one held-out year, so precision changes could be mislabelled leakage.
The original contract and evidence were archived; v2 preserves input dtype in
perturbations and has regression controls for the confound. A separate fresh
precision-clarification pair gives both arms the same instruction to promote
forecasts and observations before arithmetic. It is not a replication of v1.
The total efficiency inference limit remains four attempts in this round.

The fresh precision pair is complete:

| Measure | General Python | Guided acmadDL/AfricaS2S |
| --- | ---: | ---: |
| Scientific completion | Fail: no numerical results before budget stop | Pass: all ten checks, including three replays/probes |
| Fresh input + output tokens | 58,450 | 54,571 |
| Total tokens, including cached input | 372,818 | 352,811 |
| Agent time | 205.2 s | 150.5 s |
| Full CLI time, including assessment | 207.7 s | 197.6 s |

The guided attempt used 6.6% fewer fresh-input-plus-output tokens and 26.7% less
agent time, while producing the only valid completion in this pair. Traces
confirm that returned native normalization and calibration arrays feed the
submission. Both drivers stopped at a token-limit checkpoint; actual overshoots
are included. This is one observed completion/resource signal for the package
and guide bundle, not replicated efficiency or a scientific capability boundary.
The supplementary prose judge was not run. The [full efficiency report](mam-efficiency-study-2026-10-08.md)
and [verification](../experiments/efficiency_verification_2026-10-08.json) retain
all four attempts and keep the two phases separate. Direct paid API spend was
$0; subscription invoice costs are unknown.

## Difficulty

The first candidate is a blind multiyear MAM outlook with free calibration and
combination decisions. It uses real four-centre forecast inputs, trains on
1993–2004 and forecasts 2005–2016. All observations from the forecast years must
remain private. A train-only selected expert baseline and the performance target
must be fixed before model inference. Validity and forecast performance are
separate results; a valid forecast below the target is a performance miss.

This is fixed-calibration retrospective forecasting with final-vintage sources.
It does not establish sequential adaptation or operational-vintage skill.
Uncertainty is assessed across years, without treating neighbouring grid cells
as independent replications. A daily onset/false-start outlook remains the second
candidate, pending genuine daily archive, observation variant, coverage and
independent event/calibration checks.

The MAM candidate failed its pre-inference usefulness gate: the train-selected
ECMWF expert scored RPS **0.47849**, worse than uniform climatology's **0.44290**.
Thus climatology could meet the declared target. The selection and target were
not retuned after this result, and no Luna attempt was spent on it. Its independent
score and controls still provide a reusable free-design forecasting template.

The second executable candidate tests the portfolio's earlier probability-
combination result on genuine ASO 2026 component outlooks, with clean independent
grading and retrieval. It asks for support-aware consolidation and a weighting
sensitivity calculation. The arithmetic may be easy; this is a bounded test of
whether the historical failures survive a clear contract, not a claim of hard
forecast reasoning. Daily onset remains a deferred acquisition lead.

Luna passed that consolidation pilot, including complete-vector support,
coordinate coverage, own-command replay and a changed-input diagnostic with a
partial category vector. It took 63.0 seconds of agent time and 31,646
fresh-input-plus-output tokens. The [original result](../experiments/hard-task-consolidation-results-2026-10-08.json)
is preserved. No stronger-model retry was launched: this clean implementation
does not reproduce the historical difficulty. The [hard-task report](hard-task-search-2026-10-08.md)
records both candidates and their controls. Neither establishes a hard boundary.

No task is called hard because an agent exhausts a budget, cannot discover an
API, or encounters a controller defect. Each candidate needs a checked reference
or score, known-correct controls and scientific faults before a model attempt.

## Research frameworks and the next qualified experiment

The [primary-source review](hard-benchmark-inspiration-2026-10-08.md) covers
AIRS-Bench, RE-Bench, MLE-bench, PaperBench and their experiment frameworks.
The useful design is open method choice, a bounded draft/debug/improve loop,
controller-owned development feedback and independent final scoring. Published
benchmarks' day-long GPU budgets and older-model results do not establish
difficulty for this weather benchmark.

The closest next experiment is the existing weeks 3–4 Level 2 task with an
adaptive bias-correction/CFSv2++ comparator reproduced on the exact frozen
inputs and split. Establish attainable improvement over raw forecasts and
climatology before spending model calls. A new boundary claim requires fresh
final periods or regions; previously inspected holdouts remain development
evidence. A small search condition can use two drafts and two improvements,
one shared resource budget, at most six development-score requests and one
final candidate selected without final-score access. These are next designs,
not additional model runs completed in this round.

The controller already supports the weeks 3–4 RMSE feedback shape. Probabilistic
RPS tasks need a deliberate feedback-schema extension before using the same
loop. AIRA-dojo/AIDE provide useful search mechanisms; Inspect is a possible
future integration layer. No new framework dependency was installed.

## Verification

The full test suite passed **189 tests**, with one skip. The subsequent
brief-launch preflight repair and precision-probe regressions passed six
targeted tests. All ten template briefs rendered across 230
instance/level/supplement variants. The preflight now rejects malformed briefs
before Docker or run-folder creation, preserving the distinction between
authoring failures and actual model attempts. Scientific native I/O remained
serial per process, with at most two shared workers. Original assessments and
historical grading contracts remain preserved.
