# Bounded pilot evidence

The [checkpoint report](../docs/checkpoint-2026-10-08.md) covers six attempts on
three tasks, Python versus Rhiza, with Astra high. The
[focused report](../docs/focused-study-2026-10-08.md) covers six more: Astra on
CCA/downscaling and Luna on CCA, Python versus current ACCORD. Attempts ran in
pairs, with inspection between pairs. No 25-cell matrix or agent retries ran.

The [parallel investigations](../docs/parallel-investigations-2026-10-08.md)
subsequently add grader stress and two executable tasks. Their separate plan is
`parallel-investigations.yaml`; frozen agent results are collected by
`summarize_investigations.py` into `parallel-results-2026-10-08.json`. The
study completed five attempts, all passing their declared completion checks.
The audit pair remains under v1; its path-only v2 erratum has pending trials and
explicitly inherited scientific controls in `audit-brief-erratum-2026-10-08.json`.
The environment record is `investigation-runtime-2026-10-08.json` (242 general
packages match). Controller changes and historical-contract handling are
explicit in `response-projection-revision-2026-10-08.json`; historical verdicts
remain attached to their original fingerprints. Runtime incidents are described
in [their own report](../docs/investigation-runtime-findings-2026-10-08.md).

| Evidence | Record |
| --- | --- |
| Initial plan and six completed attempts | `grading-checkpoint.yaml`, `checkpoint-results-2026-10-08.json` |
| Adaptive plan and six focused attempts | `focused-study.yaml`, `focused-results-2026-10-08.json` |
| Area-tolerance defect and separate frozen regrades | `downscaling-reassessment-2026-10-08.json` |
| Weeks 3–4 sampling sensitivity | `checkpoint-skill-uncertainty-2026-10-08.json` |
| Images, current library commits, package differences and patches | `runtime-manifest-2026-10-08.json` |
| Native import-order reproduction | `native-import-probe-2026-10-08.json` |
| Latest Rhiza reader image, three native-import checks | `rhiza-reader-native-probe-2026-10-08.json` |
| Actual Rhiza script on real Kenya input | `rhiza-tool-smoke-2026-10-08.json` |
| Toy physical tool checks before/after reader repair | `tooling-diagnostics-before-reader-repair-2026-10-08.json`, `tooling-diagnostics-2026-10-08.json` |

Goals remain **not established**: there is no demonstrated agent-level tooling
benefit or hard scientific capability boundary. CCA passed on both backbones;
tool use was sparse and the specified adaptations often differ from library
defaults. Functional tool diagnostics motivated raw units and irregular durations
in the subsequent reconciliation task. Its implementation and attempts belong to
the separate parallel investigation; neither diagnostic helper success nor
documentation access establishes an agent-level benefit.

The subsequent [MAM acquisition study](../docs/mam-acquisition-study-2026-10-08.md)
adds a real four-centre retrieval-to-forecast task and two parallel Luna pairs.
Its records are `mam-acquisition-study.yaml`, `mam-preflight-2026-10-08.json`,
`mam-results-2026-10-08.json` and `mam-tool-use-review-2026-10-08.json`.
General Python completes the task with the revised context budget; both required
native-tool attempts stop during documentation/API inspection. Two pre-driver
environment failures are retained separately in `mam-launch-recovery-2026-10-08.json`.
No frontier attempt or further retry was launched. Regenerate its integrity-checked
summary with `.venv/bin/python experiments/summarize_mam.py`; it launches no inference.

The prepared five focused configurations are Astra Python/Rhiza/ACCORD and Luna
Python/ACCORD. The focused Rhiza agent condition is **unrun**; its newly derived
reader image was validated directly after discovering optional-metadata failure.
Historical Rhiza attempts retain the original image and weaker discovery guidance.
Different stages must not be pooled into a causal tooling comparison.

Agents and judges used subscriptions, with no direct API-key calls. Provider
list-price estimates are not invoices. The user-authorized paid API cap is $100;
control judging and interrupted attempts have separate records. Initial and
focused summaries report only their own completed attempts.

Regenerate summaries with `.venv/bin/python experiments/summarize_checkpoint.py`
and `.venv/bin/python experiments/summarize_focused.py`. These commands launch
no inference and check contract/configuration drift. They require the local
frozen records under `var/`, which remain outside Git. Docker probes under
`runtime/` exercise native and tooling behavior without crashing host Python.
