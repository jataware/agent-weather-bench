# The first evaluator (generation 1), archived 7 October 2026

This folder holds the first generation of the benchmark, moved here by `git mv`
when `assessment/` became the only evaluator. Nothing was deleted. The current
system is described in the root README and in `docs/assessment-format.md`.

## What it was

- `tasks/` — ten task packages, each with a `task.yaml`, a private rubric
  (`rubric.yaml`), frozen inputs and a replay contract. A task was scored by a
  rubric tree: deterministic leaves computed by the controller, and judged leaves
  rated by a locked model judge.
- `weatherbench/` — the evaluator package: `runner.py` (one attempt of one system on
  one task), `evaluation.py` and `verification.py` (the rubric leaves),
  `judge.py` (the locked Sonnet judge), `acquisition.py` (controller-mediated
  retrieval of native sources into the sandbox), `feedback.py` (development-score
  feedback), `report.py` and `cli.py` (the run index and the `weather-bench` command),
  and `task_tools/` (the data preparation, review pages and reference code of the ten
  tasks).
- `judges/` — the judge definition (`auto-v1.yaml`, `system-v1.md`) and its lock file.
- `experiments/` — two experiment sequences run with this evaluator.
- `requirements-controller.lock` — the pinned controller environment the lock covered.
- `docs/` — the harness guide, the task-authoring guide, the internal setup notes, the
  two reviews of the evaluator, and the brand preview page with its figure
  (`agent-task-comparison.*`).
- `tests/` — the regression tests of this evaluator. They import `weatherbench` and
  the moved modules below; they are not collected by the default test run.

## The judge lock is no longer verified

`judges/auto-v1.lock.json` records SHA-256 digests of `judges/*`,
`requirements-controller.lock`, `pyproject.toml` and every file under
`weatherbench/`, all at their former top-level paths. Those paths moved into this
folder, `pyproject.toml` now describes the current package, and five modules left
`weatherbench/` for `assessment/` (see below). The lock therefore no longer matches
any live tree. The scores recorded under the old judge id stay valid as history; no new
score can be produced under that lock.

## What moved into `assessment/` instead of here

`runtime.py` (the Docker sandbox), `adapters.py` (the JSON-lines command adapter and
the Anthropic driver), `model.py`, `storage.py`, `systems.py` and `substrate_use.py`
(the tooling-use monitor from pull request #1, unchanged) now live in `assessment/`.
The copies in `assessment/` drop two things only this evaluator used: the
`acquisition` hook of the sandbox and the `acquire` tool of the adapters. The
`weatherbench/` package in this folder is therefore incomplete on its own.

## Running it from the archive, if anyone must

1. Check out the last commit with the evaluator at the top level:
   `git checkout 0930264` (7 October 2026, branch `dev/assessment-format`).
2. Create the controller environment from `requirements-controller.lock` and build
   the runtime image as `docs/internal-setup.md` describes.
3. Run `python -m weatherbench run <task> --system <system>`; see `docs/harness.md`.
4. Expect the judge lock to verify at that commit and nowhere else.

The archived tests can be run in place with
`PYTHONPATH=archive/evaluator-v1-2026-10 .venv/bin/python -m pytest archive/evaluator-v1-2026-10/tests`;
the ones that import the moved modules will fail until step 1 above is done.
