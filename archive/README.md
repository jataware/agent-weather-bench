# Historical archive

`evaluator-v1-2026-10/` holds the first evaluator (generation 1): the ten task packages under `tasks/`, the `weatherbench/` rubric evaluator, the locked Sonnet judge under `judges/`, its guides, reviews and tests, moved there on 7 October 2026 when `assessment/` and the templates became the only current system. [Its README](evaluator-v1-2026-10/README.md) says what it was, why its judge lock no longer verifies, and how to run it from the archive.

`docs-2026-10/` holds the documents, studies and scripts of the first development cycle, 2 to 6 October 2026, superseded by the task set, the assessment format and the roadmap; [its index](docs-2026-10/README.md) says what each was.

`pilot-2026-10-01/` is the completed ACCORD pilot: its code, configurations,
reports, slides, local data, private controller state and original runs. Historical
run/data/private directories remain ignored by Git. Nothing was deleted to clean
the repository. [The migration receipt](migration.json) records hash verification
of 2,129 moved historical files.

Start with [the historical results](pilot-2026-10-01/report.html),
[the complete historical README](pilot-2026-10-01/README.md), or
[the check-in deck](pilot-2026-10-01/2026-10-01-accord-checkin.pptx).
Raw historical reports and logs retain their original absolute paths and names.
Their relative folder structure is preserved inside the archive; they are evidence
of that experiment rather than entry points for the current framework.

Archived regression tests are not collected by the default test run; run them in place with `PYTHONPATH=archive/pilot-2026-10-01:archive/evaluator-v1-2026-10 .venv/bin/python -m pytest archive/<folder>/tests`; the tests that import modules moved into `assessment/` need the checkout described in the evaluator's README. Historical task data remain separately shared. Rhiza setup requires an explicit `RHIZA_WEATHER_SKILLS_DIR`, and model credentials come from the controller environment. The closed historical launch guard is preserved. The current CLI does not use that
runner, change its scores, or pool its attempts with new benchmark runs.
