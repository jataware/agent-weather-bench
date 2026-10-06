# Monthly-cycle replay and fitted-state prediction

```json
{
  "schema_version": 1,
  "replay": {"argv": ["python", "workflow.py", "--inputs", "{input_dir}", "--outputs", "{output_dir}"]},
  "predict": {"argv": ["python", "workflow.py", "--model", "{model_path}", "--inputs", "{input_dir}", "--outputs", "{output_dir}"]},
  "model_path": "model.json",
  "retained_files": ["workflow.py", "model.json", "inputs/predictors.nc", "inputs/targets.nc"],
  "dependencies": ["Python NumPy SciPy xarray in pinned benchmark image"]
}
```

Use any language/filenames with equivalent interfaces. Replay recomputes
hindcasts.nc and forecast.nc from nominated input paths. Prediction loads the
original fitted state and emits forecast.nc without any target observations,
refitting, reselection or copying the original forecast.

The controller multiplies every monthly target from2011 onward by1.7 and changes
predictors for target years 2012 onward. Fitted outer predictions, coefficients,
moments and selections through2011 must be unchanged; verification against changed
truth is excluded from this invariant. It then removes retained targets.nc and
hindcasts.nc files, changes2020-and-later SST by a month-varying vector and checks
saved-fit inference. Commands run from a read-only retained submission root and
must use the writable substituted output directory. Code/state review is still
needed to detect target copies under other filenames or hidden refitting.
