# The objective outlook pilot (roadmap step 5) found four controller defects and one agent that gave up in four minutes

Roadmap step 5 ran one cheap system on one instance, once, to expose contract
and controller defects and to give the first full trace. This record holds what
the run did, what the controller got wrong about it, what changed, and what the
run says about the agent. Terms: a *stage* is one of the eight parts of the
outlook job (acquire, prepare, WVG, eReg, CCA, combine, verify, issue); the
*coverage* check asks whether the submitted arrays carry exactly the required
coordinates; a *rerun* is the controller running the submitted command itself.

## The run

| Item | Value |
| --- | --- |
| Run | `var/template-runs/20261011T113859-objective-seasonal-outlook-gha--mam-2015-L1-outlook-pilot-codex-luna-6e8f2e` |
| System | `outlook-pilot-codex-luna` (Codex CLI 0.160.0, gpt-6-luna, ChatGPT subscription, Docker-only tools) |
| Instance | `gha--mam-2015`, level 1 |
| Budget | four hours, 600 tool calls, 30 minutes per command, 4 million tokens, 6 GB |
| Used | 259 seconds, 14 tool calls, 271,893 tokens (230,144 cached input, 6,116 output) |
| API cost | none for the agent (subscription); the judge made one Opus-class request for 0.15 USD |
| Outcome | fail; 1 of 8 stages passed after the controller fix (0 of 8 before it) |

## What the agent did

- It read the inputs and the practice sheet, fetched every catalogue resource
  through the acquisition service, and inspected three files (calls 1 to 8).
  Two early errors were its own: the runtime has no `requests` module and no
  `curl`.
- At call 9 it wrote one script covering all eight stages. Two crash-fix cycles
  followed (an xarray selection, then a coordinate-length mismatch that it
  "fixed" by labelling the target grid as the model grid).
- At call 13 it printed its own area shares and skill; at call 14 it wrote the
  report and stopped. It used 4.3 minutes of a four-hour budget.
- It did not implement CCA. Its CCA arrays copy the eReg arrays, and its report
  and `answer.json` say so.
- Its eReg regression is fitted on all years including the forecast year. The
  judge caught the contradiction with the report ("fitting quantities are
  computed without the verification year's observation").
- Its arrays carry near-normal (category 1) and nonzero scores on the 969
  unsupported cells, against the brief's rule that unsupported cells hold zero.
- Its script writes a cache under `/work/state`, which is read-only during the
  controller's rerun, so every rerun crashed before writing a store.

## What the controller got wrong, and what changed

1. **One wrong coordinate blanked every stage.** The agent's `plat` had 58
   values against 37 expected. The controller treated a coverage failure as
   "nothing is usable", blocked 20 checks with "the submission has no usable
   answer to check", and failed the schema of all eight stages, including the
   five whose results never touch `plat`. Fixed in `assessment/compare.py`
   (`align_partial`), `assessment/assess.py` and `assessment/stages.py`: a
   coordinate gap takes down only the results laid out on it; the rest are
   framed and assessed; a stage fails its schema only when it owns a result
   that was taken down; checks that need a taken-down result fail "with the
   coverage" and name the result and the gap. The weeks 3–4 template's
   `missing_cases` control changed expectation with the rule: its development
   forecast, which is covered, still regenerates and still follows its inputs.
2. **A stage row did not say why.** `stage.acquire` read "Verdicts: absolute
   fail." while the reason (the replay probe failed) sat one level down. Stage
   rows now quote the detail of any verdict that did not pass.
3. **The envelope did not say the rerun is read-only.** The agent's cache
   under `/work/state` was a reasonable guess from the brief's own paths. The
   envelope now says that during the rerun everything except `{output_dir}` is
   read-only, so caches and scratch files go there.
4. **Two identity checks did not say where.** `issue_identity` said "dominant
   categories disagree" and `score_identity` said "discrepancy 2". Both now
   name the array, count the cells and say how many are unsupported. On this
   run: 969 cells, all 969 unsupported, in both checks.

A new control, `predictor_on_target_grid`, plants the agent's exact mistake
(the interpolated model means delivered as the predictor fields under the
target-grid coordinates) so test 3 certifies the scoped rule: prepare fails its
schema, the three streams and verify are unresolved because prepare is their
upstream, and combine and issue pass. The first certification run of the
control expected verify to pass; the stage layer rightly held it unresolved,
and the expectation was corrected.

## The stage verdicts after the fix

| Stage | Verdict | Why |
| --- | --- | --- |
| acquire | fail | the replay probe failed (the rerun crashed on the read-only `/work/state`) |
| prepare | fail (schema) | `prepare_model_predictor_mm` is laid out on `plat`, which has 58 values instead of 37 |
| wvg | fail | the WVG arrays agree with the reference under accepted readings, but the changed-data rerun crashed |
| ereg | fail | the eReg arrays match no listed reading (fitted on all years) |
| cca | fail | the method-blind gate failed: correlation 0.497 against the controller's CCA, floor 0.6 |
| combine | pass | the objective is the equal-weight mean of the three streams |
| verify | unresolved | upstream prepare failed its schema; its own check also fails on the unsupported cells |
| issue | fail | dominant categories differ on the 969 unsupported cells |

The forecast-year RPSS is 0.036 (reference 0.044 on the same instance); it is
not valid for ranking.

## What the run says about the questions this round must answer

- **At which stage it went wrong:** prepare, by mislabelling the predictor
  grid, and CCA, by not doing it. The stage rows say so without rerunning
  anything. Whether the stage is the same across instances needs the matrix.
- **Scientific, contract, budget or controller:** one of each. CCA and eReg are
  scientific; the predictor grid, the unsupported cells and the read-only cache
  are contract misunderstandings; there was no budget stop; the coverage
  cascade was a controller defect.
- **Does the rubric rank a system that did not finish:** after the fix, yes:
  one stage passed, one is unresolved, six failed, each with its reason.
- **Is the trace readable:** yes. The 14 commands and their results fit on one
  screen; the rerun's crash is in the probe's recorded stderr.

## What this does not establish

- Whether a stronger system or a higher effort setting finishes CCA. The pilot
  system stopped by choice, not by budget.
- Whether the brief's predictor-grid sentence ("`plat`, `plon` the model grid
  as served") is clear to an agent that does not take the shortcut. The
  control shows the grader's behaviour, not the brief's clarity.
- Whether the hard-coded source host (`weather-source:8000`) the agent first
  tried would have broken the rerun; it switched to `acquisition.json` before
  writing its script.

## Re-certification

The coverage rule, the stage detail and the envelope sentence are deciding
changes, so every template whose record the suite keeps current re-certified
under the new fingerprint (`--local-trusted`, 11 October 2026).

- The five locked templates (`kenya-forecast-revision`, `weeks34-rainfall`,
  `rainfall-downscaling`, `seasonal-rainfall-calibration`,
  `seasonal-cca-reproduction`) pass tests 1 to 4 unchanged. The weeks
  `missing_cases` control now fails on coverage alone with the envelope and
  both probes passing, as the scoped rule predicts, and `mislabelled_dates`
  still stops at coverage because neither of its coordinates survives.
- The outlook's first run under the new fingerprint failed test 3 on the new
  control only: the expectation left `stage.verify` to default to pass, and
  the stage layer held it unresolved because prepare is verify's declared
  upstream. The expectation was corrected and the template re-run.
- The outlook's second run (record `20261011T130838`) passes tests 1 to 4 on
  both instances with the corrected expectation; all 22 control rows are as
  expected. Test 5 still needs two agent attempts under this fingerprint; the
  pilot run was assessed under the previous one, so it does not count.

## Re-assessment of 13 October 2026

The first two ablation arms ([record](objective-outlook-ablation-2026-10-12.md))
exposed a reference defect: the two model-mean arrays of `prepare` kept
values on unsupported cells while `practice.md` requires zero there. The
pilot's trace carried the same 1303 mm gap on `prepare_model_hindcast_mean_mm`.
Under the corrected reference (fingerprint `a4f67496…`) the pilot's profile
is unchanged, 1 of 8 stages: its predictor arrays are still on the wrong
grid, its eReg is still fitted on all years, and the rerun still crashes.
The gap it keeps on `prepare_model_forecast_mean_mm` (1198 mm) is its own.
The earlier assessment stays under `controller/assessments/02ec6731….json`.
