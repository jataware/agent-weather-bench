# CCA replay and saved-state inference

```json
{
  "schema_version": 1,
  "replay": {"argv": ["python", "workflow.py", "--inputs", "{input_dir}", "--outputs", "{output_dir}"]},
  "predict": {"argv": ["python", "workflow.py", "--model", "{model_path}", "--inputs", "{input_dir}", "--outputs", "{output_dir}"]},
  "model_path": "model.json",
  "retained_files": ["workflow.py", "model.json", "inputs/predictors.nc", "inputs/targets.nc"],
  "dependencies": ["Python, NumPy, SciPy, xarray from pinned image"]
}
```

Names and language may differ. Replay recomputes `hindcasts.nc` and `forecast.nc`
from the nominated inputs. Prediction loads fitted transforms, CCA coefficients,
uncertainty and thresholds, and emits `forecast.nc` without targets, refitting,
reselection, or reliance on cached forecasts. Commands run offline in a retained
read-only submission; the substituted output path is the writable destination.

The controller multiplies all2011-and-later rainfall by1.7 and changes SST from2012
onward. Outer predictions/probabilities/thresholds/selections through2011 must stay
unchanged; verification of modified targets and full-fit diagnostics are excluded.
It then removes known retained `targets.nc` and `hindcasts.nc` files and changes
2020-and-later SST with a fixed nonuniform vector. Predictions must reflect the
original fitted state on changed allowed predictors. Static code/state review
is still necessary to audit disguised copies of observations under other names.
