# A canonical retrieval-to-outlook task

This report preserves the initial v1 discovery/budget experiment. The later
[two-track investigation](two-track-investigation-2026-10-08.md) records a
dtype-confound repair in the controller probes and a fresh guided-tool pair;
original submissions and verdicts here remain unchanged.

`mam-multimodel-outlook` is implemented and has one passing Luna submission,
including fresh source retrieval, all numerical checks, changed-source reruns
and supplementary prose review. Required weather tools did **not** improve
completion in this small experiment: both assigned native-tool attempts stopped
while inspecting documentation and APIs. Neither executed the required helpers.
This establishes a concrete discovery/budget problem, not a scientific weakness
of acmadDL or AfricaS2S and not a frontier capability boundary.

## The forecaster's job

Retrieve four distinct C3S centres' member-resolved monthly forecasts/hindcasts
and CHIRPS monthly observations; select valid MAM months, convert native rates,
align the land grid, calibrate each centre, combine probabilities, and report
cross-validated skill and uncertainty. The retrospective instance trains on
1993–2015 and forecasts MAM 2016 on 18 Kenya-interior cells. Ensemble sizes are
25/40/28/31. This is a small service window, not nationwide coverage.

Agents receive endpoint descriptors and parameters, not analysis-ready arrays.
A private HTTP source service exposes curator-produced NetCDF preserving decoded
native monthly values/schema. General Python and toolkit arms have identical
source access. Forecast-year observations remain outside both the actor mounts
and source service. Every replay starts a fresh service with the controller's
chosen source bytes and catalogue hashes. This tests acquisition and preparation
from a snapshot, not live CDS discovery, authentication or provider throughput.

The prescribed recipe is default-Wilks Gaussian ensemble regression, fold-local
tercile thresholds and equal-centre probability averaging. The NumPy/SciPy
reference and independent scalar implementation agree. Actual pinned acmadDL
normalization agrees exactly after float64 promotion; native AfricaS2S
probabilities agree within 1.2×10⁻¹⁵. Both operations are suitable for this task.

## What the grading investigation found

All nine final controls behave as declared: three correct/reordered solutions
pass; wrong month lengths, either missing unit-conversion factor, leaked category
thresholds and member-weighted combination fail by name; cached answers fail
the changed-source rerun. The rubric has three convention decisions and sixteen
readings. Actual Docker actor/replay tests verify the isolated source boundary;
request logs survive scratch cleanup with valid hashes.

The full repository suite passed **185 tests**, with one skipped. Eight targeted
tests also passed after the final controller-environment preflight change.
The [verification record](../experiments/mam-verification-2026-10-08.json)
pins the test log, archived v1 contract, control certificate and Docker evidence.

The first controls exposed two authoring defects before model calls: a scalar
claim was documented where the shared envelope expects a one-entry list, and
known missing-conversion faults initially remained unclassified. Both were
corrected. OLS probabilities can be invariant to predictor rescaling, so the
required rainfall totals are essential evidence of correct physical units.

Correct implementation and good forecast skill remain separate. The recipe's
CV RPSS is **+0.0934**, while withheld-2016 RPSS is **−0.4554**. The independent
private metric agrees. Skill does not gate completion or support a leaderboard
on one neighbouring-cell window and one season. Scientific/redistribution
approval remains pending.

## Four model attempts, two parallel pairs

The initial smaller-backbone pair compared general Python with required
acmadDL normalization and AfricaS2S calibration. Both used the same task,
sources, high reasoning, matched general dependencies, 20 commands and 900
seconds. Rhiza was left out because this experiment targets these two supported
native calibration/preparation operations. Astra was staged but not launched:
the weaker model eventually completed the scientific task with Python.

| Context cap | Condition | Completion | Agent seconds | Commands | Uncached input | Cached input | Output |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 100k | Luna, Python | Budget stop; incomplete | 101.4 | 8 | 43,330 | 72,192 | 9,196 |
| 100k | Luna, required ACCORD | Budget stop; empty submission | 29.6 | 7 | 27,052 | 76,288 | 978 |
| 350k, separate fresh/output caps | Luna, Python | **Pass**, prose also passes | 100.4 | 10 | 43,787 | 155,392 | 7,938 |
| 350k, separate fresh/output caps | Luna, required ACCORD | Budget stop; empty submission | 54.3 | 15 | 46,302 | 326,144 | 1,842 |

The second pair was a declared budget diagnostic: only the budget and its
enforcement changed. It added caps of 100k uncached input plus output, and 20k
output, while increasing the cumulative context ceiling. Fresh workspaces were
used; earlier model failures remain in the results. These are not repeated
measurements at one budget or independent datasets.

The final tool attempt spent nine commands inspecting APIs/source and stopped
with substantial fresh-token, output, command and time headroom. Cached input
was 87% of its cumulative total. The first combined skill read was truncated;
later inspection included a wrong private-module guess. The package operations
were never reached. Required-tool compliance is therefore not satisfied;
forecast science is not evaluable for those empty submissions. They stay in
the assigned arm rather than being dropped.

Across all four attempts: 160,471 uncached input, 630,016 cached input and
19,954 output tokens. Both Python attempts together spent 104,251 uncached
input-plus-output tokens per one valid completion; ACCORD produced no valid
completion, so that ratio is undefined. This is token accounting, not an invoice
or a causal cost comparison. Subscription inference and one subscription judge
request were used; direct paid API spend is **$0**. Judge list-price equivalent
is separately recorded as $0.110516, not a charge.

## Infrastructure and evidence

Two original launches failed before adapter spawn because `CODEX_BINARY` was
unset. They are preserved separately and do not count as model trials. The
launcher now verifies and records the pinned 0.160.0 binary instead of selecting
the auto-updated 0.161.0 symlink. Certification's trial collector also excludes
verified pre-driver environment failures, with explicit evidence; genuine
budget failures still count. Docker Desktop was unavailable at source-freeze
startup and recovered after reopening; its underlying cause remains unknown.
The latest host Python crash report remains the earlier 12:05 UTC threaded-HDF5
incident. Scientific validation uses serial I/O in fresh processes.

The [task guide](../templates/mam-multimodel-outlook/README.md) gives the control
command. The [plan](../experiments/mam-acquisition-study.yaml),
[preflight evidence](../experiments/mam-preflight-2026-10-08.json),
[results](../experiments/mam-results-2026-10-08.json),
[tool-use review](../experiments/mam-tool-use-review-2026-10-08.json) and
[launch recovery](../experiments/mam-launch-recovery-2026-10-08.json) retain the
separate stages. `summarize_mam.py` checks source, system, submission and request-log
integrity without inference. Original runs, submissions and computed assessments
remain attached to their contracts; supplementary judgement is recorded separately.

## Next useful experiment

Stop model expansion here. First make native-tool discovery concise and verify
that an agent reaches the actual operations. A future matched comparison should
cap fresh work and output while allowing sufficient cached-context headroom,
and retain all failures. This experiment does not establish tooling benefit.

A separate **staged, unrun** condition, `mam-luna-accord-guided`, now provides a
[short API guide](../systems/mam-luna-accord-guided/WEATHER_TOOLS.md) and executable
synthetic examples instead of asking the agent to begin with two long skill
pages. The examples successfully execute normalization and both cross-validated
and forecast calibration in the same pinned container. The adapter, budgets,
runtime and scientific task are unchanged from the preceding native-tool
context-budget condition. This is an instruction/discovery intervention;
[validation](../experiments/mam-guided-discovery-validation-2026-10-08.json)
establishes working calls, not an agent completion or tool advantage. The original
four attempts remain the study results. No Astra attempt has run on this task.

For harder canonical forecasting, the [daily-data scout](../experiments/mam-next-data-scout-2026-10-08.json)
identifies genuine daily C3S hindcasts/forecasts plus daily CHIRPS as the strongest
next source lead for calibrated onset and false-start protection. No complete
local triplet is ready. Verify daily interval labels, observation variant,
guard-tail coverage and independent calibration before inference. A chronological
weeks 3–4 forecast with delayed observations is another candidate. Neither has
yet demonstrated frontier difficulty.
