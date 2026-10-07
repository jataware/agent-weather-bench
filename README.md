![Agent Weather Bench — A benchmark for AI forecast research](docs/assets/brand/hero.svg)

## Which frontier models and agent frameworks can reliably complete substantive weather-forecasting workflows, with what scientific validity, cost, time, and expert intervention?

Agent Weather Bench assesses complete scientific workflows for subseasonal-to-seasonal (S2S) forecasting: acquiring and interpreting data, investigating methods, writing and adapting scientific code, producing forecasts, and verifying results. We compare how models and harnesses perform, and whether tooling—skills, scientific libraries, literature retrieval, and earlier work—makes those workflows more reliable and efficient. Agents submit code, numerical results, and explanations that are checked against the template's requirements.

The benchmark draws on scientific reproduction benchmarks such as [PaperBench](https://openai.com/index/paperbench/) and [SciReplicate-Bench](https://arxiv.org/abs/2504.00255). It uses forecasting research to test whether agents can implement scientific methods, run valid experiments, and support their conclusions with evidence.

For AI and machine learning researchers, the benchmark provides common templates and checks to compare agents, the models that power them, and the tools and methods they use. It measures whether the work was done right, its scientific correctness, cost, and time. Further experiments test whether skills, workflow code, access to literature, or earlier work improve performance.

For forecasters, the goal is to provide evidence for choosing agents and supporting methods for specific tasks. Results should show which work a system completes correctly, where it fails, and where expert review is needed.

[The attempt](#the-attempt) · [Templates](#templates) · [The checks](#the-checks) · [Systems and supplements](#systems-and-supplements) · [Run a template](#run-a-template) · [Results](docs/results.md) · [Roadmap](docs/roadmap.md)

## The attempt

![A template and its tooling go into a sandbox with an agent; the controller inspects what comes out](docs/figures/overview.png)

The question is: under what conditions can a forecaster's task be handed to an agent system and come back right? A template is a canonical forecasting job stated as a product, with frozen data and a budget. An instance of it goes into an offline sandbox with an agent and whatever tooling the run supplies: skills, libraries, earlier work, and any supplement such as a conventions sheet. What comes out is a submission in a fixed envelope: labelled arrays, an answer file, the code that regenerates the results and a report, plus the trace. The controller, the trusted evaluator, checks the submission by computation against a private reference under every defensible reading of the brief, by rerunning the agent's own code on changed data, and by a narrow judge that answers one question at a time on exact quotations. Every check returns pass, fail or unresolved.

One run of one system on one instance is an attempt. A system is a model, the harness that drives it, and the tooling in its workspace. The set has 25 templates in six families, checked in product, process or outcome mode; three are built and certified so far. [The roadmap](docs/roadmap.md) states the system, the open work and the eight planned experiments in three pages. [The results so far](docs/results.md) give the first 36 attempts and what the checks caught. [The task set](docs/task-set.md) and [the assessment format](docs/assessment-format.md) hold the detail.

## Templates

A template is a task whose brief, inputs and answer key take parameters such as region and time window, so one template yields many instances. Each template declares a mode. In product mode the controller compares the agent's numbers with a private reference. In process mode it also checks the method against a published standard, step by step. In outcome mode it scores a forecast against withheld observations. Level 1 is the plain submission. Level 2 is a separate, optimized submission for the same instance, which the agent may tune with a limited number of development scores; its skill ranks a leaderboard once its validity checks pass.

The three templates below are certified: each passes the five certification tests in the offline Docker runtime (two independent reference implementations agree; a known-correct submission passes; deliberately incorrect submissions fail on the right check; the separability of every pitfall is measured; cheap-model attempts leave no answer unclassified). Scientific approval by a domain expert is a separate gate, and no template has it yet. The attempts column counts the attempts assessed under each template's current spec version and fingerprint; earlier attempts are in [the results](docs/results.md).

| Template | Mode | Levels | Spec version | Instances | Attempts under the current contract | Certification |
| --- | --- | --- | --- | --- | --- | --- |
| `kenya-forecast-revision` | product | 1 | 2 | 5 | 4 | five tests passed; expert approval pending |
| `seasonal-rainfall-calibration` | process | 1 | 3 | 3 | 4 | five tests passed; expert approval pending |
| `weeks34-rainfall` | outcome | 1 and 2 | 3 | 8 | 3 | five tests passed; expert approval pending |

[The task set](docs/task-set.md) lists all 25 templates with their parameters, modes and levels.

## The checks

Each template has a spec: the named results with their error bounds, the conventions the brief leaves open with each reading marked accepted or a named pitfall, the invariants any valid answer obeys, the probes to run, the claims to check, the process steps to verify and the questions a judge decides. The controller holds a private reference function that computes the answer under every defensible reading.

The agent submits a fixed envelope and is free in everything else: labelled arrays in a Zarr store, an answer file with numbers, choices, claims and the run command, the code that regenerates the results, and a short report. The method is not prescribed.

The controller decides each check one of three ways. **Computation** compares the results with the reference under every reading, so a known wrong reading is named as a pitfall, and scores forecasts against withheld observations. **A rerun** executes the agent's own code on changed data: the results must follow the data and must not use what a valid method may not use, such as a held-out year or a forecast from the future. **The judge**, Claude Opus 5.5 with no tools and a fixed prompt, answers one narrow question at a time, such as whether the report says what the code and the numbers say. Every passage the judge relies on must appear in the cited file, or the verdict is discarded.

Every check returns pass, fail or unresolved. Fail means the submission is at fault, with the pitfall or defect named. Unresolved means a cause outside the submission, with a reason code, and is never counted as a fail. An attempt passes only when every check passes, the judge's included; the computed part is also reported on its own. There are no weights.

| Check | Who decides | What unresolved means |
| --- | --- | --- |
| `envelope` | computation | The run command could not be executed, so nothing could be regenerated. |
| `coverage` | computation | The required cases could not be enumerated because the envelope is unusable. |
| `variant` | computation | The results that can be read match only accepted readings, but a result they rest on is unusable. |
| `invariant.<name>` | computation | The result the rule inspects is unusable. |
| `probe.<name>` | a rerun of the agent's code | The rerun could not be carried out, or the result it compares is unusable. |
| `claim.<name>` | computation | The results the claim rests on are unusable. |
| `feedback.limit` | computation, Level 2 only | No trusted record of development-score requests exists. |
| `process.<id>` | a rerun, computation or the judge, by the evidence the step names | A check the step rests on is unresolved, or the standard's step can be read two ways. |
| `interpretation.<name>` | the judge | The judge was not run, its reply was voided for an inexact quotation, or it could not decide. |

The controller keeps the provenance. It records the hashes of the inputs and of every submitted file, the source versions, the full tool trace, the tooling used, the cost and the time. The agent writes none of it, so an administrative slip cannot fail a check. The format is defined in [the assessment format](docs/assessment-format.md) and used through the [`assessment/`](templates/README.md) package.

## Systems and supplements

![Benchmark design: compare models, harnesses and tooling on the same template instances. A template states a product with frozen data and a budget; an agent in a sandbox hands back a submission and a trace; the controller checks it against a private reference, by rerunning the code on changed data, and by a judge on exact quotations. Every check returns pass, fail or unresolved. Episodes keep the earlier submission for the next instance.](docs/assets/brand/benchmark-design.svg)

[Open the diagram at full size](docs/assets/brand/benchmark-design.svg).

| Dimension | Comparison |
| --- | --- |
| Model capability | How reliably does each model complete the same instances with general tools? |
| Harnesses | How do different agent loops perform on the same instances under matched data access and resource budgets? |
| Tooling | How does performance change when we add skills, libraries, retrieval, or earlier work? |
| Cost and time | What does a passing submission cost, and how long does it take? Include failed attempts. |
| Reuse | Does agent-owned work from an earlier instance improve performance on the next one? |

The tooling is the skills, libraries, retrieval resources, or earlier work in the agent's workspace. A run can also supply a conventions sheet or a method description with `--supply`; each is recorded as a supplement of the run, so a comparison can separate knowing the conventions from applying them.

For model comparisons, keep the harness, templates, inputs, tooling, budgets, and checks fixed. Record provider and model versions, tokens, costs, and wall time. For tooling comparisons, also hold the model and harness fixed, and report the cost of creating the tooling separately. For harness comparisons, hold the model, templates, data access, resource budgets, and checks fixed while allowing orchestration to differ, and record each harness's version, configuration, and tools so the complete system being assessed is clear. Reuse experiments compare second episodes with plain attempts, and counterbalance instance order to separate reuse from difficulty.

## Run a template

Use Python 3.12 or later and Docker. Agent code runs only in the offline Docker runtime, never on the controller host. From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m assessment templates
.venv/bin/python -m assessment prepare kenya-forecast-revision --source ../weather-skills-bench/fixtures
.venv/bin/python -m assessment instances kenya-forecast-revision
.venv/bin/python -m assessment brief kenya-forecast-revision service-area--weeks-1-2
.venv/bin/python -m assessment certify kenya-forecast-revision
.venv/bin/python -m assessment assess kenya-forecast-revision service-area--weeks-1-2 PATH/TO/SUBMISSION
.venv/bin/python -m assessment run kenya-forecast-revision service-area--weeks-1-2 --system kenya-revision-fixture
.venv/bin/python -m assessment run kenya-forecast-revision central--weeks-2-3 --system kenya-revision-fixture --supply conventions
.venv/bin/python -m assessment run kenya-forecast-revision north-west--weeks-3-4 --system kenya-revision-fixture --parent RUN_ID
.venv/bin/python -m assessment run weeks34-rainfall final-2015-2017--all-cells --system weeks34-level2-fixture --level 2
.venv/bin/python -m assessment runs
.venv/bin/python -m assessment reassess RUN_ID
.venv/bin/python -m assessment judge RUN_ID
.venv/bin/python -m assessment judge-calibration
.venv/bin/python -m assessment attempts kenya-forecast-revision
```

- `run` launches a system on an instance, assesses its submission and has the judge decide the questions no computation can settle. `--no-judge` leaves those unresolved.
- `--supply conventions` hands the agent the template's conventions sheet as a supplement.
- `--parent RUN_ID` starts a second episode: the earlier run's submission is placed under `/work/prior`, and the agent may use it or not.
- `--level 2` requests the optimized submission and enforces the development-score limit.
- `reassess` assesses an existing run again under the current spec and code; `judge` has the judge decide a run's open questions; `attempts` refreshes the fifth certification test from the runs on disk.
- A system is defined in `systems/<id>/system.yaml`. To run the Codex systems after the command-line install has moved past the verified version, name the verified binary and use the pinned system: `export CODEX_BINARY=$HOME/.codex/packages/standalone/releases/0.160.0-aarch64-apple-darwin/bin/codex`, then `--system codex-luna-pinned`.

[The templates guide](templates/README.md) explains each command, the sandbox boundary, the adapter protocol, the tooling-use record and the data layout.

## Write and certify a template

A template folder holds `spec.yaml`, `brief.md`, `reference.py`, `reference_independent.py`, `instances.yaml`, `sources.json`, `controls/` and, after certification, `certification.json`; a process-mode template also names its standard under `standards/`. Freeze the source data and record its hashes, write the reference function and a second implementation that shares no code with it, declare each tolerance as an error bound, label every convention accepted or pitfall, build the controls, and run `certify`. The spec version is locked only after the fifth test, cheap-model attempts with every unknown answer ruled on. [The templates guide](templates/README.md) gives the file-by-file instructions and the hooks `reference.py` must provide.

## Results

36 attempts by one cheap model, gpt-6-luna, through one harness have been assessed on the three templates: 23 passed every check, the judge's included. The judge decided 151 questions, failed 8 and matched the expected verdict on all 12 of its control cases. Every failure has a named cause. [The results](docs/results.md) give the tables, the tooling comparison and the eight controller defects the attempts found.

## The template set

The 25 templates fall into six families: outlook products, observed indices and verification, seasonal forecast production, subseasonal forecast production, research claims and consensus, and downscaling with the diagnostic pack. Three are certified; the rest are specified with their parameters, mode and level, and two are marked frontier-hard. [The task set](docs/task-set.md) is the full list.

## Roadmap

[The roadmap](docs/roadmap.md) states what is built, what remains (the tooling images, the conventions sheets, the remaining templates, the spending limits) and the eight planned experiments: the model ladder, harnesses, tooling value, supplements, second episodes, Level 2, process conformance and the frontier-hard templates.

## Repository layout

- `assessment/` — the controller: the specs' loader, the sandbox, the checks, the judge, certification and the command line.
- `templates/` — the three certified templates and [the guide](templates/README.md) to writing one.
- `standards/` — the published standards that process-mode templates cite, as checklists.
- `systems/` — the system definitions: model, harness and tooling image for each system id.
- `runtime/` — the offline Docker runtime images.
- `docs/` — [the roadmap](docs/roadmap.md), [the results](docs/results.md), [the task set](docs/task-set.md), [the assessment format](docs/assessment-format.md), [the changelog](docs/CHANGELOG.md), the figures and the brand assets.
- `tests/` — the controller's tests, including the check that every certification is current.
- `var/` — runs, staged data and private instances; not committed.
- `archive/` — the first evaluator, the pilot and superseded documents, kept intact and not current.

## Licence and status

The repository is a first release of the template format and its controller. Template data are shared separately. No licence has been selected yet.
