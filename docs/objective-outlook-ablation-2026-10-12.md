# Objective outlook: the tooling ablation (roadmap step 6)

Decided and built 12 October 2026, after the pilot
([record](objective-outlook-pilot-2026-10-11.md)). The predeclared plan is
`experiments/ablation-plan-2026-10-12.yaml`. The runs wait on the budget
go-ahead; results are recorded at the end of this page as they land.

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

## What waits on the owner

- Authorization of up to $160 of paid API use for the four arms, beyond the
  $100 cap of steps 1 to 5.
- `ANTHROPIC_API_KEY` in the environment of the launching shell; the
  controller never writes it anywhere.
- Confirmation of the arm 3 reading above (catalog plus guides), or the
  alternative (catalog alone).
- Optionally, raising Docker Desktop's memory to 14 GB so two arms can run
  concurrently.

## Results

Not yet run.
