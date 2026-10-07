# Replay, held-out truth probe and observation-free inference

Use execution.json with:

```json
{
 "schema_version":1,
 "replay":{"argv":["python","workflow.py","--inputs","{input_dir}","--outputs","{output_dir}"]},
 "predict":{"argv":["python","workflow.py","--inputs","{input_dir}","--outputs","{output_dir}","--model","{model_path}"]},
 "model_path":"model.json",
 "retained_files":["workflow.py","model.json","inputs/coarse-forecast.nc","inputs/fine-training.nc","inputs/geometry.nc"],
 "dependencies":["Python numpy scipy xarray netCDF4 in the pinned image"]
}
```

Both commands must honor alternate paths and run offline. Full replay produces
forecast.nc, hindcasts.nc and fitted state from trusted inputs. Predict uses saved
state and produces forecast.nc without fine-training.nc or original derived arrays.

The controller changes2001fine observed rainfall within the training record:
its own2001leave-one-out hindcast must remain unchanged; predictions for other
years or production may change. This guards the exclusion boundary for one fold;
it does not prove every fold is leakage-free. Code and saved-state review remain
necessary. Private2009–2016truth is never supplied.

The controller changes allowed forecast predictors for2009–2016. Saved-state
predictions must match the prescribed inference from retained fitted state and
changed allowed inputs, without observations or refitting. Full replay under a
positive affine transformation of ALL raw predictors must preserve output values;
this invariance does not resolve raw source units.
