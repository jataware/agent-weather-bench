# Parallel investigations — 8 October 2026

The [plan](../experiments/parallel-investigations.yaml) runs three workstreams:
grader stress without inference, rainfall delivery reconciliation for tooling
usefulness, and forecast audit/repair for scientific reasoning. Agent attempts
run two at a time, with a maximum of five initial attempts and no agent retries.
The [machine-readable results](../experiments/parallel-results-2026-10-08.json)
preserve each contract, output, usage and observed tooling access.

All five attempts have completed: three delivery-reconciliation attempts and
two forecast-audit attempts. All pass their declared completion checks, including
the required audit reviews. These instances remain attainable for Astra high;
neither **tooling benefit** nor a **hard capability boundary** is established.
The main gains are two executable task designs and more reliable grading.

Astra high and the subscription harness stay fixed to compare environments before
adding another backbone. Python is the baseline; Rhiza's delivery helpers make
it relevant to ingestion; ACCORD supplies the requested AfricaS2S/acmadDL stack
for both workflows. These are offline frozen-data tasks, so they do not measure
acmadDL's acquisition advantages. The prior Astra/Luna CCA success also argues
for improving task discrimination before expanding the model matrix.

## Grader stress

All 40 legal storage/layout variants passed across the original five templates.
Five complete rewritten controls passed computed assessments and reruns; five
scientific faults and five mislabeled-array comparisons were rejected. Additional
area algebra and 28 CCA basis/sign transformations passed. These are bounded
control results, not proof that all legitimate methods are covered. The
[stress report](grader-stress-2026-10-08.md) preserves its earlier controller
fingerprints and distinguishes computed checks from unrun prose reviews.

## Rainfall delivery reconciliation

The new task uses the real frozen ECMWF issues of 20 and 27 September. The newer
cumulative Zarr is unchanged; the older delivery is explicitly curator-derived
interval-mean NetCDF with time bounds and reversed axes. Both are from the same
model. Two calendar weeks over the service region produce four mm arrays and
wetter/drier claims. This tests scientific integration and metadata, without
pretending to measure acquisition or observation-verified skill.

All three initial conditions pass computed checks and supplementary source-lineage
reviews:

| Astra high condition | Controller stop | Tool calls | Cumulative tokens | Observed weather tooling |
| --- | --- | ---: | ---: | --- |
| Python | Submitted; collection recovered | 5 | 96,551 | None |
| Rhiza | Submitted | 5 | 82,494 | Read relevant skill documentation; no helper execution or library import |
| ACCORD | Token cap after passing delivery | 7 | 170,287 | Read supplied documentation; no recorded weather-library import |

All use the same 242 general package versions, including scikit-learn and
statsmodels. The Rhiza arm adds its skills/core; ACCORD adds AfricaS2S, acmadDL
and its Sheerwater dependency. Exact images and package versions are in the
[environment record](../experiments/investigation-runtime-2026-10-08.json).
Core data/I/O versions and native import-order repair match.

The direct physical tool probes showed relevant helpers work on the actual
input, but all agents independently chose NumPy/xarray endpoint and interval
integration. Rhiza's lower token count is one observation, with different
exploration effort and no executable helper use. It does not establish a causal
tooling advantage. ACCORD hit a notification-based token guard after delivery;
the guard overshoots by one response. Completion and controller stop stay separate.

The Python submission froze normally, but its optional scratch state contained
a symlink to the runtime inputs. The original collector rejected that link and
aborted before saving timing/provenance. Recovery preserved the scientific
submission and input hashes and used the existing final event/token record;
there was no new model attempt. Exact agent duration is unavailable and excluded
from timing comparisons. Its lost end-inspection payload also remains explicitly
unresolved in provenance; numerical and prose assessments pass independently.
The runner now records adapter results before retention
and omits/logs optional state links without following them. Submissions retain
strict collection. [Recovery evidence](../experiments/collection-recovery-2026-10-08.json)
and the [runtime report](investigation-runtime-findings-2026-10-08.md) describe the limits.

## Forecast audit and grading repairs

The audit task supplies plausible candidate code, configuration and a report,
using real SST predictors and rainfall observations. It requires reproduction
of the original numerical experiment, a scientific diagnosis and a valid
replacement or confirmation. Alternative methods, including climatology, are
accepted; skill is descriptive and need not beat climatology.

Clean, global-target-preprocessing, global-predictor-selection and unsupported
development-claim cases are separate opaque instances. Annual interventions
test all 15 hindcast years, changing targets from the cutoff onward and predictor
years strictly later than the cutoff. Three production cutoffs test every later
year boundary. Legitimate later models may incorporate earlier observations.

Independent control review found and repaired these issues before audit inference:

- Changing original diagnostics could satisfy the generic input-response test
  while repaired predictions stayed cached. `response_results` selects scientific
  outputs, and `RESPONSE_GROUPS` requires hindcast and production forecasts to
  respond separately. Full before/after partial-cache controls demonstrate the gap.
- Three sampled cutoffs missed localized look-ahead; all annual and production
  boundaries now have controls, including future-predictor preprocessing.
- A sub-tolerance change in a reported RMSE could reverse a skill claim. The
  controller now derives that claim from actual predictions and frozen targets.
- Scalar metric tolerance could reject valid float32 delivery. The brief specifies
  float64 metric accumulation, permits float32 storage, and uses a derived scalar
  rounding bound with accepted and incorrect-score controls.

The optional response additions preserve the default behavior of previous
templates. Their hashes changed, so a [revision ledger](../experiments/response-projection-revision-2026-10-08.json)
records both controller versions and the explicitly reviewed historical
fingerprints. Old agent assessments are not relabelled or recomputed. Automatic
controls are revalidated separately. A real host crash during threaded HDF5
validation was stopped and diagnosed; subsequent control work uses separate
Python processes. It is distinct from both the old deliberate crash test and
the repaired Docker import-order problem.

All 68 automatic audit control assessments behaved as expected: twelve accepted
methods and 56 planted faults. The final known-correct Docker assessments pass
computed checks in both environments; the required report review passes on the
Python control. The [gate record](../experiments/investigation-audit-gates-2026-10-08.json)
preserves their contract and hashes. The matched Python/ACCORD pair ran on case-c,
where predictor screening uses the whole target record while regression fitting
uses earlier years. Both pass computed checks and the required scientific review:

| Astra high condition | Completion | Calls | Cumulative tokens | Agent seconds | Repaired RMSE, mm |
| --- | --- | ---: | ---: | ---: | ---: |
| Python | Pass | 5 | 86,847 | 247.0 | 166.133459 |
| ACCORD | Pass | 5 | 119,851 | 271.6 | 166.133459 |

Both precisely diagnosed supervised predictor selection over the full target
record, while recognizing that the regression fit and its centering already use
earlier years. Both retained the one-predictor ridge architecture and moved
screening inside each training fold; neither used the accepted climatology
fallback. Their original, repaired and production arrays are bitwise identical
despite independently organized code. Original contaminated RMSE is 150.848485 mm;
expanding climatology is 165.827115 mm. Both correctly report that the honest
repair does not beat climatology. ACCORD documentation was consulted, with no
recorded weather-library import or helper execution. See the
[delivery review](../experiments/audit-delivery-review-2026-10-08.json).

This is success on one deliberately readable faulted workflow. Its configuration
explicitly names whole-record selection, and the brief explains the information
boundary. It does not test acceptance of a clean workflow, establish operational
forecast skill, or locate a frontier capability limit. The valid climatology
control is appropriate for auditing validity; a future learned-forecast task
would need a separate scientific objective.

Both agents found a brief path error: the scientific objective was supplied under
the input directory, while the brief named `/task/scientific-objective.md`.
They read the supplied file and performed the intended audit. Their v1 contracts
and assessments remain unchanged. A one-line v2 correction, explicitly inherited
scientific controls, staging checks and a fresh known-correct Docker assessment
are documented in the [erratum ledger](../experiments/audit-brief-erratum-2026-10-08.json).
The new version has pending agent trials; the completed pair belongs to v1.

The complete test suite passes **140 tests**; the ten targeted audit/response
tests also pass after the path-only v2 correction. Scientific approval remains pending
for both new templates. The transient Docker outage was resolved before the audit
pair launched and is recorded separately from the host HDF5 crash.

## Budget and next decision

The study stopped at its five initial attempts, with two running at a time and
no agent retries. Agent usage totals 556,030 cumulative tokens, including 381,952
cached input tokens and 27,316 output tokens. The 150,000-token notification guard
can overshoot by one response, as happened after ACCORD's ingestion delivery.
Subscription adapters were used; no direct paid API calls were made against the
$100 authorization. Completed-attempt judges have a combined provider list-price
estimate of $0.49149, which is not an invoice and excludes control judging.

The next informative audit experiment is two matched clean/faulty workflows
with neutral configuration names, fully inspectable source and independently
validated controls. Start with Python/Astra to test both diagnosis and false
accusations before repeating unused tooling conditions. A scientific failure
would then need an independent instance and frozen-artifact review before it
supports a boundary claim. For tooling, first demonstrate a relevant helper
solves a genuinely difficult delivery workflow, then compare availability and
actual use across instances; another saturated endpoint calculation is unlikely
to distinguish these systems. No additional attempts from those proposals have
been launched.
