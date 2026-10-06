# Full replay and saved-state inference

Retain code, fitted state and original inputs; use:

```json
{
  "schema_version":1,
  "replay":{"argv":["python","workflow.py","--inputs","{input_dir}","--outputs","{output_dir}"]},
  "predict":{"argv":["python","workflow.py","--inputs","{input_dir}","--outputs","{output_dir}","--model","{model_path}"]},
  "model_path":"model.json",
  "retained_files":["workflow.py","model.json","inputs/training.nc","inputs/development-features.nc","inputs/final-features.nc"],
  "dependencies":["Python,numpy,xarray,scipy,netCDF4 in the pinned benchmark image"]
}
```

The command working directory is the retained submission root. Both commands
must honor alternate input and output directories. Full replay uses the frozen
method/hyperparameter selection, trains from supplied training.nc and recreates
both prediction files. It must not call development feedback during replay.
Inference uses saved model state and works after training.nc and original output
predictions are removed. It produces both development/final prediction files.
The controller changes permitted raw-CFSv2 features and compares inference with
replay under the same changes. This tests state/code consistency and alternate
inputs, rather than requiring every valid method to use raw-CFSv2. A seasonal
climatology may legitimately ignore it; this alone does not prove leakage freedom
or correctness of the declared method. Code and trace review remain necessary.
