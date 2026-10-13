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

## Results: arms 1 and 2 (13 October 2026)

Both arms launched at 07:23 UTC on `gha--mam-2015` and submitted within
eleven minutes. Runs `20261013T072303-…-ablation-sonnet-python-291492` and
`…-ablation-sonnet-libraries-f41c0f`.

| | Arm 1 plain Python | Arm 2 libraries only |
| --- | ---: | ---: |
| agent time | 414 s | 426 s |
| tool calls | 11 | 25 |
| model calls | 12 | 24 |
| output tokens | 46,240 | 39,126 |
| cache reads / writes (tokens) | 285,110 / 56,444 | 1,090,112 / 83,455 |
| agent cost | $0.63 | $0.71 |
| retries, compactions | 0, 0 | 0, 0 |
| stages passed, first assessment (`02ec6731…`) | 7 of 8 | 7 of 8 |
| stages passed, corrected reference (`a4f67496…`) | 8 of 8 | 8 of 8 |
| outcome (computed, judged) | pass, pass | pass, pass |
| reading matched | conservative, actual days, prediction error, fold-only | the same |
| CCA gate: correlation with the controller's CCA (floor 0.60) | 0.679 | 0.997 |
| CCA gate: cross-validated RPSS against the controller's (margin 0.08) | +0.003 vs −0.009 | −0.011 vs −0.009 |
| cross-validated RPSS of the objective (own numbers) | 0.023 | 0.021 |
| 2015 RPSS of the issued outlook (not for ranking) | 0.034 | 0.050 |
| africas2s: imported in chat / in delivered code / called in replay | — | step 4 / no / none |
| acmadDL: imported in chat / in delivered code / called in replay | — | no / no / none |

**Substantive use.** Arm 2 imported africas2s once, in its fourth command,
to find where the package lived, then read `methods/cca.py` from the
installed source in two commands. Its delivered code (`prep.py`,
`streams.py`, `run.py`) imports neither library; the static scan found no
callee and the traced replay (one process, exit 0) counted no call. The
record therefore reads `used: true, substantive: false` for africas2s and
`used: false` for acmadDL. Under the predeclared rule, arm 2 is evidence
that availability is not use, not evidence for the libraries. Whether
reading the library's CCA source is what put arm 2's CCA at 0.997
correlation with the controller's, against arm 1's 0.679, is a question
for the OND replication; one attempt cannot answer it.

**What the agents did.** Arm 1 listed the workspace, read the catalog and
the provenance page, downloaded and hash-checked every resource, inspected
the five files, and at its ninth command wrote one 604-line `run.py` that
covers all eight stages; two more commands ran it and wrote the bulletin.
Arm 2 explored the same way, read the library source, then built three
modules with unit checks in between (fold bounds, a statsmodels comparison
for the logistic fit, a timing of CCA mode selection) and edited its
bulletin twice. Both declared the same readings in `answer.json`
(area-conservative observation aggregation weighted by the cosine of
latitude, 92-day MAM totals from mm/day rates, prediction-error variance,
fold-only tercile boundaries, bilinear interpolation of model means to
target cell centres, ties to near normal), and their `prepare` arrays agree
with the reference and with each other to 10⁻¹³ mm.

**The one unresolved stage was the reference's defect.** On the first
assessment both arms matched no reading because the reference kept the
interpolated model means on the 969 unsupported cells of
`prepare_model_hindcast_mean_mm` and `prepare_model_forecast_mean_mm`,
while `practice.md` tells the solver that every array with latitude and
longitude holds zero there. Both agents followed the practice; on the
2,627 supported cells they agreed with the reference to 3×10⁻¹³ mm, and
the pilot's trace shows the same gap. Under the project rule the defect was
diagnosed on the controls and fixed as a versioned change, not by retrying
the agent: `science.py` and `reference_independent.py` now zero those
cells (no downstream result reads them), a control `unmasked_model_means`
keeps values off support and must match no reading, the template was
re-certified, and the three frozen submissions were re-assessed with the
earlier assessment kept beside the new one. The pilot's profile did not
change (its faults are its own).

**Reading, under the predeclared rules.**

- The premise that generic Python fails is not supported on this instance
  with this backbone: the plain-Python arm completed the operational
  pipeline, passed every stage, the method-blind CCA gate and both bulletin
  questions, in eleven commands for $0.63.
- No uplift can be claimed for the libraries: the arm that had them did not
  call them, and its stage profile equals the baseline's.
- One attempt per arm on one instance decides nothing; the plan requires
  replication on the OND instance before any difference counts.
- The cost estimate was high by an order of magnitude for this backbone's
  behaviour: it assumed 250 turns, the arms took 12 and 24. The $40 cap
  per arm stands for arms 3 and 4.

Arms 3 (skills only) and 4 (full stack) are next, in parallel.
