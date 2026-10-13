# Objective outlook: the tooling ablation (roadmap step 6)

Decided and built 12 October 2026, after the pilot
([record](objective-outlook-pilot-2026-10-11.md)). The predeclared plan is
`experiments/ablation-plan-2026-10-12.yaml`. Arms 1 and 2 ran on 13 October 2026; the results
are at the end of this page.

## What the matrix asks, and what it drops

The scientific question of ACCORD is whether domain libraries and weather
skills let an agent complete an operational meteorological pipeline where
generic Python fails. Harness differences (Codex CLI against Claude Code) are
developer minutiae and are dropped. The matrix therefore holds the backbone
and the harness fixed and varies only the tooling, in four arms on
`gha--mam-2015`:

| Arm | System | Libraries installed | Guidance supplied | Image |
| --- | --- | --- | --- | --- |
| 1 baseline | `ablation-sonnet-python` | none | none | `75bd0583…` (the investigation python image) |
| 2 libraries only | `ablation-sonnet-libraries` | africas2s, acmadDL | none (guides removed) | `690b3893…` |
| 3 skills only | `ablation-sonnet-skills` | none (weather_skills_core only, to run the catalog) | Rhiza catalog at `/catalog/skills`; the two ACCORD skill guides at `/opt/accord-current/docs` | `1ffd3d08…` |
| 4 full stack | `ablation-sonnet-full` | africas2s, acmadDL | both | `fe804d16…` |

All four images derive from the matched investigation images of 8 October
(`runtime/Dockerfile.ablation-arms`,
`experiments/ablation-runtime-2026-10-12.json`), so the 242 general package
versions are identical and only the declared weather tooling differs. Arm 3
is the 2×2 reading of "skills without libraries": the Rhiza catalog is a set
of runnable skill scripts with their `SKILL.md` files, and the ACCORD guides
are procedure a solver can follow by hand. An alternative reading, the Rhiza
catalog alone, needs only the `image_paths` and instructions of that system
changed; the image holds both.

## The backbone is a workhorse model

The backbone is Claude Sonnet 5.5 (`claude-sonnet-5-5`, effort high) through
the benchmark's own Anthropic controller (`assessment.adapters.anthropic_driver`),
with Docker-only tools, exactly as the Codex adapters are wired. A frontier
model tends to over-reason or hand-roll the mathematics and so masks what
tooling adds; a Sonnet-class model shows whether libraries and skills give
real uplift or fail to. The effort level is the provider's default for the
model and is held constant, because changing it between turns would restart
the prompt cache.

Three controller changes make a four-hour paid conversation affordable and
survivable; none is a deciding module, so no template re-certified:

- **Prompt caching.** The driver asks for automatic caching and prices the
  provider's cache counters separately (`cache_write_input_tokens`,
  `cached_input_tokens`); `total_tokens` is the provider's full count, cached
  reads included, as the Codex adapters report it. The arms declare
  80,000,000 for that count, because a long cached conversation's total is
  dominated by reads; the dollar cap (`max_usd` 40 per arm) is the binding
  bound.
- **Context management.** Above 300,000 prompt tokens the driver elides the
  oldest long tool outputs (the newest nine turns stay whole) and tells the
  agent so in its system prompt; at 900,000 the run stops rather than fail
  at the window. Every elision is an event in the trace.
- **Refused requests.** A 429, 529 or 5xx answer, which the provider does
  not bill, is retried after 5, 15, 45, 90 and 180 seconds, within the wall
  budget; a transport timeout stays fatal with its cost reserved, as before.

## Substantive use is measured, not inferred

Every arm's record carries the stage profile and, beside it, what the
delivered command actually called. After the assessment the controller
replays the frozen command once more under a call tracer
(`assessment.tracer`): a `sitecustomize` placed first on `PYTHONPATH` wraps
every public function and method of each declared library as it is imported
and counts calls whose caller is not the library itself. The counts are
written under the replay's output directory and discarded with it; that
replay decides nothing. The record (`controller/library-calls.json`, merged
into `substrate_use`) holds per library:

- `static_calls`: the callees the submitted files name, resolved through
  their imports (`import africas2s as ds; ds.optimize(...)` counts as
  `africas2s.optimize`);
- `replay_calls`: the functions the replay actually entered, with counts
  (for instance `africas2s.optimize`, `africas2s.cv.loyo`,
  `africas2s.tercile.to_tercile_cv`, `acmaddl.fetch.fetch`);
- `substantive`: true only when `replay_calls` is not empty.

The import-based record of pull request #1 stays beside it, unchanged. A
library that is installed, imported and then bypassed by hand-rolled
arithmetic, as the pilot agent did when it copied eReg into CCA, now shows
as `used: true, substantive: false`. The tracer chains to the runtime's own
`sitecustomize` (the native import-order workaround), so the replay runs
under the same setup as the assessment's. A process that dies without
Python's exit handlers (a hard kill, `os._exit`) leaves no counts; the
record is a lower bound.

## Cost

The pilot ran on a subscription, so the estimate rests on its trace shape
and the published Sonnet 5.5 prices ($2 input, $10 output, $2.50 cache
write, $0.10 cache read per million tokens, read 12 October 2026 from the
provider's pricing page).

| Case | Turns | Mean cached context | Cost per arm |
| --- | ---: | ---: | ---: |
| typical | 250 | 150,000 | about $10 (reads $3.75, writes $0.75, output $3.75, judge $0.15) |
| cap | — | — | $40 (`max_usd`) |

Four arms: about $40 typical, $160 at the cap. Arms run one at a time,
because Docker Desktop allows 8 GB and each sandbox takes 6 GB with the
assessment replay needing another; four arms at the full wall budget are
sixteen hours, and an arm that quits early, as the pilot did, is minutes.

## What the owner decided on 13 October 2026

- Up to $160 of paid API use for the four arms, $40 per arm, beyond the
  $100 cap of steps 1 to 5.
- Arm 3 is the Rhiza catalog plus the two ACCORD skill guides, as above.
- The arms run in parallel rather than one at a time. The plan file records
  the change: the 6 GB caps are limits, not reservations, so two arms share
  Docker Desktop's 8 GB, and a sandbox killed for memory would count as an
  infrastructure failure and stop the study. Arms 1 and 2 peaked under
  200 MB each.
- `ANTHROPIC_API_KEY` lives in the repository's git-ignored `.env`; the
  launcher sources it and the controller never writes it.

## Results: all four arms (13 October 2026)

Arms 1 and 2 launched at 07:23 UTC and arms 3 and 4 at 10:31 UTC, each pair
in parallel, on `gha--mam-2015`. Runs `20261013T072303-…-ablation-sonnet-python-291492`,
`…-libraries-f41c0f`, `20261013T103127-…-ablation-sonnet-skills-58ab12` and
`…-full-b6149e`. Every number below is under the corrected reference with
the pilot's proposed ruling recorded (fingerprint `2db513ed…`, spec version
2); the assessments under `a4f67496…` (corrected reference, no ruling) and,
for arms 1 and 2, under `02ec6731…` (the defective reference) are kept
beside them in `controller/assessments/`. The arms' verdicts are identical
under the two corrected fingerprints.

| | Arm 1 plain Python | Arm 2 libraries only | Arm 3 skills only | Arm 4 full stack |
| --- | ---: | ---: | ---: | ---: |
| agent time | 414 s | 426 s | 403 s | 428 s |
| tool calls | 11 | 25 | 16 | 14 |
| model calls | 12 | 24 | 15 | 15 |
| output tokens | 46,240 | 39,126 | 33,091 | 41,567 |
| cache reads / writes (tokens) | 285,110 / 56,444 | 1,090,112 / 83,455 | 504,665 / 61,161 | 577,504 / 76,219 |
| agent cost | $0.63 | $0.71 | $0.53 (from the trace) | $0.66 |
| retries, compactions | 0, 0 | 0, 0 | 0, 0 | 0, 0 |
| adapter status | submitted | submitted | execution error (see below) | submitted |
| stages passed | 8 of 8 | 8 of 8 | 8 of 8 | 8 of 8 |
| outcome (computed, judged) | pass, pass | pass, pass | pass, pass | pass, pass |
| reading matched | conservative, actual days, prediction error, fold-only | the same | the same | the same |
| CCA gate: correlation with the controller's CCA (floor 0.60) | 0.679 | 0.997 | 0.997 | 0.997 |
| CCA gate: cross-validated RPSS against the controller's −0.009 (margin 0.08) | +0.003 | −0.011 | −0.011 | −0.011 |
| cross-validated RPSS of the objective (own numbers) | 0.023 | 0.021 | 0.021 | 0.021 |
| 2015 RPSS of the issued outlook (not for ranking) | 0.034 | 0.050 | 0.050 | 0.050 |
| ACCORD guides read (`/opt/accord-current/docs`) | not present | removed | 3 commands (listing, listing, acmadDL data conventions) | 1 command (both `SKILL.md` files) |
| Rhiza catalog named (`/catalog/skills`) | not present | not present | never | never |
| africas2s: imported in chat / in delivered code / called in replay | — | step 4 / no / none | — | no / no / none |
| acmadDL: imported in chat / in delivered code / called in replay | — | no / no / none | — | no / no / none |
| weather_skills_core: imported / called | — | — | no / none | no / none |

**Arms 2, 3 and 4 delivered the same numbers.** Their issued probabilities,
CCA, eReg and WVG hindcasts agree pairwise to 3×10⁻¹⁴. Arm 1 agrees with
them on eReg (2×10⁻¹⁴) and WVG (2×10⁻⁹) and differs on CCA (largest
probability gap 0.36, from its one-mode selection against their three) and
hence on the issued outlook (0.06). Three tooling treatments therefore
produced one pipeline, and the fourth differs only where the brief leaves
the CCA mode search to the solver.

**Substantive use is zero in every arm.** No delivered command called
africas2s, acmadDL or weather_skills_core; the traced replay of each
submission (one process, exit 0) counted no call, and the static scan found
no callee. Arm 2 imported africas2s once to find it and read its CCA
source; arm 4 read the two `SKILL.md` guides in its third command and never
imported either package; arm 3 listed the guides twice and read acmadDL's
data-conventions page; no arm named the Rhiza catalog. Under the
predeclared rule, every arm with tooling is evidence that availability is
not use.

**Arm 3 ended in a transport error after it had delivered.** Its sixteenth
command copied the results store and the answer into `/work/submission` and
wrote the bulletin; the next request to the provider failed with
`ReadError: [SSL: SSLV3_ALERT_BAD_RECORD_MAC]`, which the driver treats as
fatal because a request that fails in transport may or may not have been
billed. The controller recorded `execution_error` and assessed the workspace
as it stood: a complete submission that passes every stage. Two
consequences: the adapter lost its usage record on that path (the cost
above is summed from the trace's fifteen model replies), fixed the same day
in `assessment/adapters.py`, a non-deciding module; and the plan lists an
infrastructure failure among its stop conditions, so whether arm 3 counts
as it stands or is run again is the owner's call. Its agent did nothing
after delivering that a re-run would change, and a re-run costs about $0.6.

**What the agents did.** All four read the inputs, the practice sheet, the
catalog and the provenance page, downloaded and hash-checked every
resource, inspected the files, then wrote their pipeline: arm 1 one
604-line script, arm 2 three modules with unit checks between them, arm 3
a script with a streams module, arm 4 a script with a report generator.
All declared the same readings in `answer.json` (area-conservative
observation aggregation weighted by the cosine of latitude, 92-day MAM
totals from mm/day rates, prediction-error variance, fold-only tercile
boundaries, bilinear interpolation of model means to target cell centres,
ties to near normal).

**The one stage that first came up unresolved was the reference's defect.**
On the first assessment arms 1 and 2 matched no reading because the
reference kept the interpolated model means on the 969 unsupported cells
of `prepare_model_hindcast_mean_mm` and `prepare_model_forecast_mean_mm`,
while `practice.md` tells the solver that every array with latitude and
longitude holds zero there. Both agents followed the practice; on the
2,627 supported cells they agreed with the reference to 3×10⁻¹³ mm, and
the pilot's trace shows the same gap. Under the project rule the defect was
diagnosed on the controls and fixed as a versioned change, not by retrying
the agent: `science.py` and `reference_independent.py` now zero those
cells (no downstream result reads them), a control `unmasked_model_means`
keeps values off support and must match no reading, the template was
re-certified (tests 1 to 4 pass, 24 control rows as expected), and the
frozen submissions were re-assessed with the earlier assessment kept
beside the new one. The pilot's profile did not change (its faults are its
own); its unknown answer now carries a proposed ruling of incorrect
(`rulings.yaml`), which test 5 needs and which awaits the owner's
confirmation.

**Reading, under the predeclared rules.**

- The premise that generic Python fails is not supported on this instance
  with this backbone: the plain-Python arm completed the operational
  pipeline, passed every stage, the method-blind CCA gate and both bulletin
  questions, in eleven commands for $0.63.
- No uplift can be claimed for the libraries or the skills: no arm called
  them, and arms 2, 3 and 4 delivered one and the same pipeline.
- The only difference between arms, arm 1's CCA, is a solver's choice
  within the brief, not a tooling effect; one attempt per arm on one
  instance decides nothing, and the plan requires replication on the OND
  instance before any difference counts.
- The task did not separate the arms. Whether it can separate anything on
  this backbone is now the question for step 7: a harder instance, a
  second episode, or a task whose domain step has no plain-Python route.
- The cost estimate was high by an order of magnitude for this backbone's
  behaviour: it assumed 250 turns, the arms took 12 to 24. Four arms cost
  $2.53 of agent time plus the judge.

## The directions ladder: withholding what the agent is told (13 October 2026, afternoon)

The four arms delivered one pipeline because the practice sheet fixes the
method down to its conventions. On the owner's decision the study then
varied the directions instead of the tooling, with the task, the grader and
the reference fixed (plan `experiments/directions-ladder-2026-10-13.yaml`;
mechanism `assessment.directions`, a runner-side ladder that cuts sections of
the practice sheet or sentences of the brief, records the rung in the run
record and keeps such runs out of certification's test 5). Rungs run so far,
each on the plain-Python arm and the full-stack arm, two at a time: rung 2
`no-streams` (the three stream sections withheld; inputs, categories and
combination kept) and rung 3 `brief-only` (no practice sheet at all). Runs
`20261013T115724-…` and `20261013T122225-…`; every number is under fingerprint
`2db513ed…` with the controller's reruns given the command budget (below).

| Rung | Arm | Stages passed | Prepare | WVG | eReg | CCA gate (corr., floor 0.60) | Reading matched | Tool calls | Agent cost | Library calls in the delivered command | Guides read |
| --- | --- | ---: | --- | --- | --- | --- | --- | ---: | ---: | --- | --- |
| 1 full | plain Python | 8 of 8 | pass | pass | pass | pass (0.679) | yes | 11 | $0.63 | — | — |
| 1 full | full stack | 8 of 8 | pass | pass | pass | pass (0.997) | yes | 14 | $0.66 | none | both `SKILL.md` |
| 2 no-streams | plain Python | 4 of 8 | unresolved (own SST index) | fail | fail (Student-t, gap 0.012) | fail (0.599) | none | 14 | $0.69 | — | — |
| 2 no-streams | full stack | 5 of 8 | unresolved (3-box index) | fail | arrays match the reference to 0 | pass (0.660) | none | 27 | $1.07 | africas2s `CCAMethod.fit/predict/leverage` 2,212 each, `select_modes_north` 96 | guides 3 commands, catalog none |
| 2 no-streams, repeat | plain Python | 5 of 8 | unresolved | fail | fail | pass (0.676) | none | 15 | $0.68 | — | — |
| 2 no-streams, repeat | full stack | 6 of 8 | unresolved | fail | pass | pass (0.662) | none | 33 | $1.06 | none (reimplemented this time) | guides 3 commands |
| 2 no-streams, third | plain Python | 4 of 8 | unresolved | fail | fail | fail (0.535) | none | 14 | $0.67 | — | — |
| 2 no-streams, third | full stack | 6 of 8 | unresolved | fail | pass | pass (0.660) | none | 31 | $1.09 | none | guides 3 commands |
| 3 brief-only | plain Python | 5 of 8 | unresolved (unweighted aggregation, own index) | fail | gap 0.0003 | pass (0.758) | none | 21 | $1.17 | — | — |
| 3 brief-only | full stack | 5 of 8 | unresolved (unweighted aggregation, 3-box index) | fail | gap 0.0003 | pass (0.662) | none | 48 | $1.84 | none (an "africas2s-equivalent" CCA was reimplemented) | guides 9 commands, catalog 2 |
| 3 brief-only, repeat | plain Python | 4 of 8 | unresolved | fail | fail | fail (0.599) | none | 15 | $0.68 | — | — |
| 3 brief-only, repeat | full stack | 5 of 8 | unresolved | fail | unresolved | pass (0.662) | none | 38 | $1.74 | none | guides 4 commands |
| 3 brief-only, third | plain Python | 5 of 8 | unresolved | fail | unresolved | pass (0.779) | none | 15 | $0.80 | — | — |
| 3 brief-only, third | full stack | 5 of 8 | unresolved | fail | unresolved | pass (0.662) | none | 34 | $1.39 | none | guides 4 commands |
| 1 full, OND | plain Python | 8 of 8 | pass | pass | pass | pass (0.993) | yes | 11 | $0.64 | — | — |
| 1 full, OND | full stack | 8 of 8 | pass | pass | pass | pass (0.993) | yes | 15 | $0.77 | none | guides 3 commands |

In every ladder run `combine`, `verify` and `issue` pass, because they are
judged against the submission's own streams. "Unresolved" means the arrays
match no listed reading, so correctness is not established; each such
answer needs a ruling before it can be called wrong.

**What withholding the stream sections did.** Plain Python lost three
stages at rung 2: it invented its own WVG index boxes, fitted a penalized
multinomial regression instead of the centre's unpenalized below-normal
logit with near normal fixed at a third, used a Student-t with n−2 degrees
of freedom in eReg where the practice is Gaussian with the prediction-error
variance, and chose a fixed five modes in CCA, which put it at 0.599 against
the gate's floor of 0.60. The full stack recovered two of the three: its
delivered command calls africas2s's CCA per model (the first substantive use
recorded in this study) and passes the gate at 0.660, and its eReg, built
from the library's ensemble-regression source, matches the reference's
prediction-error reading exactly. That is uplift on CCA and eReg at this
rung, with calls recorded, from one attempt per arm; it counts under the
plan only after the OND replication.

**WVG fails at every rung without its section, in both arms.** The
centre's particulars, the two-box index (Niño 3.4 minus the mean of the
standardized West North Pacific and West Equatorial Pacific boxes) and the
below-normal-only logit with near normal fixed at one third, are in neither
the libraries nor the guides as the practice sheet states them. africas2s
defines its primary `wvg` index with three boxes (West South Pacific added)
and labels it "ICPAC primary definition", with the two-box form as a
variant; the full-stack arm followed the library at both rungs, and its SST
index differs from the reference's by 0.59 (rung 2) and 1.76 (rung 3). The
benchmark's practice sheet and the library disagree on which form is the
centre's. That is a question for the owner and the library's authors; the
template can accept both box readings on a new convention axis once it is
settled.

**Without the practice sheet both arms aggregated observations with an
unweighted block mean.** The accepted readings are the cosine-weighted
conservative mean and bilinear interpolation; the unweighted mean differs by
0.08 mm, far above the tolerance, so both rung-3 answers are unresolved on
`prepare` for that alone. Whether an unweighted block mean of a hundred
0.05-degree cells is a third accepted reading is the owner's call; it would
resolve both rung-3 `prepare` stages.

**Three attempts per cell on MAM (runs `20261013T1157…`, `…1409…`,
`…1531…` for rung 2 and `…1222…`, `…1458…`, `…1609…` for rung 3).** At
rung 2 plain Python scored 4, 5, 4 stages and the full stack 5, 6, 6: the
stack is ahead in every pairing, through CCA (the plain arm missed the
gate twice, at 0.599 and 0.535) and eReg (the stack matched the
prediction-error reading in all three attempts, the plain arm in none).
The stack called africas2s's CCA in one attempt of three and reimplemented
it, after reading the source, in the other two. At rung 3 plain Python
scored 5, 4, 5 and the full stack 5, 5, 5, with no library call in any
attempt and WVG failing in all six. The arms' own variance is one stage;
the rung-2 difference exceeds it in every pairing, the rung-3 difference
does not exist.

**The OND instance replicates the full rung.** Both arms pass 8 of 8 on
`gha--ond-2015` with full directions, at a CCA gate of 0.993, for $0.64
and $0.77. The OND runs at rungs 2 and 3 follow one at a time.

**Rung 3 did not separate the arms, and plain Python scored higher there
than at rung 2.** Both arms passed the CCA gate with hand-rolled CCA (0.758
and 0.662) and matched eReg to 0.0003. The plain arm's rung-2 CCA failure
at 0.599 and its rung-3 pass at 0.758 are two draws of the same agent's
choices (five fixed modes against eight EOFs with selection), not an effect
of the directions. One attempt per cell cannot separate the agent's
variance from the treatment; the ladder needs repeats before any rung-to-rung
difference is read.

**Two controller defects surfaced and were fixed as versioned changes.**
The controller's reruns and probes used the executors' built-in 120-second
deadline, a limit the envelope never states, while the agent worked under a
1,800-second command budget; the rung-2 full-stack command takes 151 seconds
(africas2s's CCA per model) and the rung-3 plain command longer, and both
failed every replay probe on that limit alone. `assessment.runner.ReplayBudget`
now gives reruns the system's command budget, recorded as
`replay_budget_seconds`; the two runs were re-assessed (3 of 8 became 5 of 8
in both). The runner also applied a rung's brief edit twice, which made the
`brief-only` rung refuse to launch; fixed with a regression test. The rung-3
runs were launched before the first fix, so their first assessments carry
the old deadline and are kept under the same fingerprint's history in
`controller/assessments/`.

**Reading, under the predeclared rules.**

- The directions, not the tooling, carried the full-rung result: with the
  stream sections withheld, plain Python drops from 8 to 4 stages.
- The ACCORD stack supplies part of what the practice sheet withheld (CCA
  and the eReg variance reading) when the agent reaches for the library,
  which it did at rung 2 and not at rung 3. Availability still is not use.
- The stack does not supply the centre's WVG as the benchmark states it,
  and the library's own definition disagrees with the practice sheet.
- Six ladder runs cost $6.6 of agent time. Rung 4 (`minimal`) is built and
  not run; the plan runs it only if rung 3 separates the arms, which it did
  not. Repeats of rungs 2 and 3 and the OND replication are the next spend.
