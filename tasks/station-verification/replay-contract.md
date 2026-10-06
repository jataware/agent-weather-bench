# Station replay contract

Use `execution.json` schema_version 1 with a nonempty replay.argv string array,
including `{input_dir}` and `{output_dir}`. Example:
`["python","workflow.py","--inputs","{input_dir}","--outputs","{output_dir}"]`.
Retain workflow sources under the submission, list them in retained_files, and
list runtime dependencies. The controller stages trusted inputs and executes
network-disabled with at most two CPUs and 4GB memory. Read original input paths
only through `{input_dir}`; write `scores.nc` and `answer.json` to `{output_dir}`.
The controller changes a real East Africa forecast stencil and method mask,
then independently recomputes all required scientific values. Replay is input
sensitivity validation, not a fresh station forecasting holdout.
