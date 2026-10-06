# Short-rains full replay and saved-state inference

Retain executable code, original source inputs and a fitted state in the
submission. Use this task-specific interface in `execution.json`:

```json
{
  "schema_version": 1,
  "replay": {"argv": ["python", "workflow.py", "--inputs", "{input_dir}", "--outputs", "{output_dir}"]},
  "predict": {"argv": ["python", "workflow.py", "--model", "{model_path}", "--inputs", "{input_dir}", "--outputs", "{output_dir}"]},
  "model_path": "model.json",
  "retained_files": ["workflow.py", "model.json", "inputs/rainfall.nc", "inputs/sst.nc", "inputs/forecast-index.nc", "inputs/candidates.json"],
  "dependencies": ["Python, numpy, scipy, xarray, netCDF4 from pinned benchmark image"]
}
```

Filenames and programming language may differ. The controller substitutes
`{input_dir}`, `{output_dir}` and `{model_path}`, runs from the retained submission
root offline, and checks required scientific outputs. Both commands must honor
alternate input/output directories. Full replay recomputes from inputs.
Prediction loads the state without fitting or reselecting and emits `forecast.nc`.
It must work without rainfall observations and must respond correctly to changed
allowed predictor values.

The evaluator additionally changes the 2011 held-out and later rainfall, and
observed SST from September 2011 onward. Historical model probabilities,
thresholds and selections through the September 2011 forecast must remain
unchanged. RPS for altered targets is expected to change and is excluded from
that invariant. This corresponds to the public fitting and issue boundaries.
Code/state review remains necessary; numerical agreement alone cannot establish
that all fitted values came from the declared procedure.
