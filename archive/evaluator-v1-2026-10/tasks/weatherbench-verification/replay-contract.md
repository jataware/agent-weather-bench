# Offline replay and changed-forecast verification

Follow the shared `../replay-contract.md`, and include both `{input_dir}` and
`{output_dir}` in `replay.argv`. Example structure:

```json
{"schema_version":1,"replay":{"argv":["python","workflow.py","--inputs","{input_dir}","--outputs","{output_dir}"]},"retained_files":["workflow.py"],"dependencies":["numpy: assigned runtime","xarray: assigned runtime"]}
```

Use actual retained files and installed dependency versions. The controller
stages trusted input bytes under a new directory for an ordinary replay, then
changes an HRES temperature slice and availability slice in a separate replay.
It independently recomputes expected metrics and verifies every scientific
field. There is no model training or saved-state inference requirement.
The constructed changed-input probe is verification sensitivity, not weather
skill or a pristine holdout score. No retained input path may override it.
