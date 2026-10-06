# What to deliver

This part is the same for every task. Write three things under `/work/submission`.

**1. `answer.json`** with these sections:

- `results` — the named quantities the brief asks for, as numbers or nested lists.
- `choices` — an object recording any convention or assumption you adopted that changes the numbers. Free text.
- `claims` — the conclusions the brief asks you to state.
- `method` — only when the brief asks for it: one entry per named step, each with `what` you did and `where` in your submission the code is. `where` is `{"file": ..., "symbol": ...}` for a function or variable name that appears in the file, or `{"file": ..., "lines": [first, last]}`.
- `run` — `{"argv": [...]}`, the command that regenerates your results.

**2. The code your run command needs.** The controller runs `argv` from your submission folder, offline, after replacing `{input_dir}` and `{output_dir}` in it. The command must read the data and the task parameters from `{input_dir}` and write a fresh `answer.json`, with at least `results`, into `{output_dir}`. Do not hard-code the data or the parameters: the controller reruns the command on changed data and on changed parameters.

**3. `report.md`** — a short account of what you did, what the numbers mean, and their limits.

Use any language, any library in the runtime and any file layout. No other paperwork is required.
