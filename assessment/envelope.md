# What to deliver

This part is the same for every task. Write these under `/work/submission`.

**1. `results.zarr`** — every array the brief names, in one Zarr store (format version 3).

- Store each array under the name the brief gives it, with the dimension names the brief gives.
- Give every dimension a coordinate array of the same name that holds its labels. `xarray.Dataset.to_zarr(path, zarr_format=3)` writes exactly this.
- The controller matches your arrays to its own by dimension name and by label. The order of the dimensions and the order of the labels are yours to choose.
- Write dates as dates (`datetime64`) or as `YYYY-MM-DD` text.

**2. `answer.json`** with these sections:

- `results` — any result the brief names that is a single number.
- `choices` — an object recording any convention or assumption you adopted that changes the numbers. Free text.
- `claims` — the conclusions the brief asks you to state.
- `method` — only when the brief asks for it: one entry per named step, each with `what` you did and `where` in your submission the code is. `where` is `{"file": ..., "symbol": ...}` for a function or variable name that appears in the file, or `{"file": ..., "lines": [first, last]}`.
- `run` — `{"argv": [...]}`, the command that regenerates your results.

**3. The code your run command needs.** The controller runs `argv` from your submission folder, offline, after replacing `{input_dir}` and `{output_dir}` in it. The command must read the data from `{input_dir}` and write a fresh `results.zarr` and `answer.json` into `{output_dir}`. The controller reruns it on changed data for the same task, so every result must come from the data. The task's own parameters, such as its dates and region, may be written into your code.

**4. `report.md`** — a short account of what you did, what the numbers mean, and their limits.

Use any language, any library in the runtime and any file layout. No other paperwork is required.
