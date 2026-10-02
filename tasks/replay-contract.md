# A workflow contract independent of language or toolkit

Deliver `execution.json`, the retained data/workflow/fit artifacts it needs, and
`handoff.txt`. There is no required programming language or script filename.
Command-line skills, library workflows, shell scripts and compiled programs can
all satisfy the same contract within the experiment's declared runtime.

```json
{
  "schema_version": 1,
  "replay": {"argv": ["weather-tool", "run", "--output", "{output_dir}"]},
  "retained_files": ["retained/input.nc", "workflow-config.json"],
  "dependencies": ["weather-tool: pinned version in the assigned runtime"]
}
```

This example uses a placeholder tool name. Provide the actual command as an
array of arguments. The evaluator substitutes `{output_dir}` and runs it from
the retained submission root in a fresh runtime with networking disabled. It
compares the regenerated required scientific artifacts, including the numeric
fields of `answer.json`; optional session notes do not have to be identical.

For seasonal calibration, also declare:

```json
{
  "predict": {"argv": ["weather-tool", "predict", "--forecast", "{forecast_path}", "--output", "{output_path}"]}
}
```

The prediction command receives a new `forecast(year,member,lat,lon)` in mm and
writes the prediction schema in the task prompt. It must load the saved fitted
state without refitting. Include its fitted-state files in `retained_files` and
identify them in the handoff. Learning/calibration commands may differ from
inference commands; the evaluator needs the two declared entry points.

All `retained_files` paths are relative to the submission and refer to existing
files. List dependencies even when supplied by the assigned substrate; they
must be pinned before a run. The same installed-tool policy applies to every
condition. The agent need not replace a skill's CLI with custom Python to comply.

The present checker validates this manifest but never executes its commands.
Trusted replay, frozen-fit verification and tool/runtime adapters remain required
before launch. A valid manifest alone is not replay evidence.
