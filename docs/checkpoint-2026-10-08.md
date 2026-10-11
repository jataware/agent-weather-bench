# First grading checkpoint

Six completed attempts, three tasks, one instance per task, GPT-6 Astra at high
effort, Python versus the original Rhiza weather-skills image. These are paired
exploratory attempts, without repeats. The frozen [plan](../experiments/grading-checkpoint.yaml)
and [machine-readable results](../experiments/checkpoint-results-2026-10-08.json)
record contracts, image IDs, usage and individual checks. Earlier results use
different contracts and remain in [the historical report](results.md).

| Task | Python | Rhiza available | What the result establishes |
| --- | --- | --- | --- |
| Kenya forecast revision | Pass; 125 s, 74,707 tokens | Pass; 140 s, 75,296 tokens | Both computed an accepted reading and passed reruns and claims. |
| Seasonal rainfall calibration | Pass; 248 s, 84,603 tokens | Pass; 229 s, 71,047 tokens | Both followed the required practice, including the required prose review. |
| Weeks 3–4 rainfall | No submission at token cap; 285 s, 129,130 tokens | Complete passing submission at token cap; 380 s, 124,065 tokens | One bounded workflow delivered; the other kept exploring. |

All five complete submissions also passed supplementary prose reviews. The
empty submission failed the envelope; downstream checks were blocked and its
judge was not called. The 120,000-token cap is checked on cumulative provider
notifications and can be exceeded by one response. Token totals include cached
input; they are not all newly generated tokens.

Two earlier attempts were stopped to investigate host crash notifications and
are excluded explicitly. Their partial evidence remains under `var/template-runs/`.

## Scientific findings

Kenya and prescribed seasonal calibration did not challenge this backbone on
these instances. The seasonal submissions independently used the same Student-t
OLS construction and obtained new-year RPSS 0.49747. That diagnostic has only
24 cells and two years; this template disables skill ranking.

The complete weeks 3–4 submission achieved withheld RMSE 14.16860 mm, compared
with 14.89005 for the raw model and 14.28153 for climatology: improvements of
4.85% and 0.79%, respectively. Its development improvement over climatology
was 0.46%. These small differences, dependent overlapping windows and one
attempt do not establish a reliable skill advantage. Validity and skill are
separate findings. The empty submission is a workflow/budget failure, not
evidence of scientific incapability.

A paired moving-block bootstrap retaining all nine cells together also spans
zero improvement. With eight-week blocks, the exploratory 95% interval is
−4.04% to +4.34% skill over climatology and −7.21% to +14.07% over the raw model.
Four- and thirteen-week blocks lead to the same qualitative finding. This is
sampling sensitivity for one historical submission, not a general confidence
interval for a model ranking. The [diagnostic and assumptions](../experiments/checkpoint-skill-uncertainty-2026-10-08.json)
are recorded separately from benchmark scores.

No Rhiza submission imported `weather_skills_core`. Two agents briefly listed
the catalog; the weeks 3–4 agent did not discover it in its commands. Catalog
availability produced no demonstrated tooling benefit. This is a discovery and
experimental-design finding. The catalog's documented `uv run` invocation was
also unavailable; installed scripts can instead run with `python`.

## Runtime and grading findings

The repeated macOS Python crash dialogs came from a regression test deliberately
sending a real host process SIGSEGV. The test now simulates the same executor
result without crashing Python. The full suite passed 124 tests.

A separate Linux native-library fault affected both weeks 3–4 attempts. They
recovered using explicit h5netcdf reads. It reproduces with
`import cfgrib; import pyproj`, whereas the reverse order exits cleanly. xarray
backend discovery imports cfgrib before rioxarray, which imports pyproj. Merely
upgrading xarray or removing netCDF4 did not fix it. A derived image initializes
pyproj first; default and explicit reads then pass in Python, Rhiza and ACCORD
arms. This is an import-order workaround, not an upstream binary repair.

Historical attempts retain their original images and traces. New configurations
pin repaired images separately. `runtime/probe_io.py` reproduces the I/O check
inside Docker with core dumps disabled; it never crashes host Python.

The grader exposes one assembled rubric with each question, implementation and
completion/ranking role. Generic prose checks are supplementary in these tasks;
specifically required scientific-practice reviews still gate completion.
`assess --control correct` gives author feedback before certification. All five
templates have independent numerical agreement and planted-control checks;
scientific approval remains pending.

## Next bounded comparisons

Two goals guide the next attempts:

- **Tooling benefit:** a paired improvement in correctness, delivery, time or
  tokens, with evidence the relevant tool was used. Start with Python versus
  current AfricaS2S on nested CCA, followed by conservative downscaling if the
  first pair reveals no grader or runtime defect. A library's named method may
  differ from the task's exact adaptation; those differences must be assessed.
- **Hard capability boundary:** a reproducible scientific error under a clear,
  functioning contract, independently checked against a correct control.
  Missing artifacts, runtime faults and exhausted exploration budgets remain
  separate. A first failure is a candidate requiring targeted follow-up.

Every new condition receives the same delivery-first workflow guidance and
visible remaining tool/token budgets. Freeze configurations before launch; run
two attempts concurrently and inspect before another pair. The broader
five-system matrix remains staged behind these checks. Additional backbones
should answer a concrete difficulty comparison.

## Resource accounting

The six completed agents reported 558,848 cumulative tokens, including 352,256
cached input tokens. Five judging requests reported $0.504142 at provider list
prices. Agents used ChatGPT subscription authentication and judges used Claude
Max; these estimates are not API invoices. No direct API-key call was made.
Interrupted attempts and control-validation judging have separate records and
are not included in these six-attempt totals. The authorized paid API cap remains
$100 across the investigation.
