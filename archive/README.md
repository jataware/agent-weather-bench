# Historical pilot archive

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

Archived regression tests run alongside the current tests. Historical task data remain separately shared. Rhiza setup requires an explicit `RHIZA_WEATHER_SKILLS_DIR`, and model credentials come from the controller environment. The closed historical launch guard is preserved. The current CLI does not use that
runner, change its scores, or pool its attempts with new benchmark runs.
