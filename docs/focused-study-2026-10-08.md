# Focused difficulty and tooling study

This follows the [three-task checkpoint](checkpoint-2026-10-08.md), with repaired
runtimes, matching documentation, a shared delivery-first instruction, visible
resource budgets and separate frozen system definitions. The
[plan](../experiments/focused-study.yaml) stages expansion after each pair;
[results](../experiments/focused-results-2026-10-08.json) retain individual
contracts, checks, usage and observed tooling use.

## Nested CCA: all four systems pass

One 2005–2019 outer-validation instance, 12 targets and 27 SST predictors:

| System | Completion | Agent time | Cumulative tokens | Observed tooling |
| --- | --- | ---: | ---: | --- |
| Astra high, Python | Pass | 318 s | 97,336 | NumPy/SciPy implementation and independent verification |
| Astra high, current ACCORD | Pass; token cap reached after delivery | 420 s | 205,650 | NumPy/SciPy submission; AfricaS2S used for independent verification |
| Luna high, Python | Pass | 110 s | 175,655 | NumPy/SciPy implementation |
| Luna high, current ACCORD | Pass | 93 s | 161,611 | NumPy/SciPy implementation; no recorded library import |

Every computed check and the required validation-scope prose review passed.
All four selected final configuration ID 8 and produced the same pooled outer RPSS:
0.07694480 fixed versus 0.09922402 nested. These are prescribed reproduction
outputs, not a comparison of the agents' forecasting skill.

The ACCORD agent independently compared its deterministic implementation with
`CCAMethod` for all 14 configurations at two training sizes. Maximum difference
was 3.87e-12 mm. It also rebuilt final probabilities from library fits, adapting
the task's sum-of-squares leverage; maximum difference was 2.22e-15. This is
substantive verification use, though the submitted forecasting code uses only
general scientific Python. An import counter alone would miss that distinction.

These outcomes establish **no tooling advantage** and **no hard capability
boundary**. Astra's library condition spent more time and tokens on documentation
and validation. Luna's library-available condition used fewer tokens and less
time, but did not import the library. One attempt per condition and different
verification effort cannot establish an efficiency effect.
The 180,000-token budget is notification-based and overshot by one response;
the complete passing submission existed before the cap. This also shows why
controller status and scientific completion must remain separate columns.

The specified adaptation differs from complete CPT/AfricaS2S defaults. Providing
exact equations and source excerpts makes the task a bounded reconstruction;
it does not test independent method discovery or an entire operational outlook.
The matched second backbone also passed. Complexity alone did not establish
difficulty here, and further repetitions of this instance would add little
evidence about a hard boundary.

## Conservative downscaling

Both Astra submissions pass after a grading correction, on training through
2008 and forecasts 2009–2012:

| System | Agent time | Cumulative tokens | Delivery |
| --- | ---: | ---: | --- |
| Python | 303 s | 88,800 | Submitted |
| ACCORD available | 310 s | 199,509 | Complete submission before token cap |

Neither used a weather-library import. The grader checks conservative mapped
coarse means, training-local spatial ratios and rank mappings, changed-data
response, raw-scale invariance and source-unit claims. A library named “BCSD”
is not automatically the specified algorithm.

**The first verdicts were unresolved, due to a grader defect.** Both agents
computed pixel area from longitude edges, as the brief specifies. Every rainfall
array matched; only area differed, by 2.0042e-6 m². The original tolerance used
the final magnitude and missed a larger intermediate. Spec 2 derives its bound
from that intermediate. The [derivation](../templates/rainfall-downscaling/geometry-error-bound.md),
new edge-formula control and wrong-radius regression make the fix reviewable.
The full suite passes **125 tests**, and the edge control passes in Docker,
including its required judge.

Agent calls stopped during diagnosis. Both original assessments remain
unchanged. [Separate spec-2 reassessments](../experiments/downscaling-reassessment-2026-10-08.json)
use the frozen submissions and verify byte-identical inputs, brief and envelope.
Both pass every check, including prose. No agent rerun was needed. The summary
keeps submission and assessment versions separate. Certification's automatic
tests pass; its spec-2 trial counter awaits new-version attempts and scientific
approval remains pending.

This is an evaluator boundary, not an agent capability boundary. Two independently
written references both simplified the width to 0.05 and missed an equivalent
implementation. Known-correct controls need algebraic and numerical diversity,
as well as planted scientific faults.

## Tool functionality and the next useful tasks

[Direct diagnostics](../experiments/tooling-diagnostics-2026-10-08.json) exercise
capabilities without paid model calls or pretending they are benchmark attempts:

- Rhiza converts mass-per-area and metre accumulations across irregular step
  durations to the correct rates and rejects already-rate inputs. Its script
  also matches the real Kenya input to within 7.11e-15 mm/day. The original
  reader failed on valid stores without optional consolidated Zarr metadata.
  A new derived image changes its reader to automatic metadata detection;
  all six toy cases now pass across both storage layouts. The
  [original diagnostics](../experiments/tooling-diagnostics-before-reader-repair-2026-10-08.json)
  remain intact. No recorded agent attempt used this new image.
- acmadDL's offline normalization correctly gives 182 versus 180 mm for two
  DJF forecasts spanning leap versus ordinary February, sorts canonical axes,
  and selects a crossing-antimeridian region on a 0–360 grid.

These support a concrete next **tooling benefit** task: ingest mixed raw forecast
conventions, calendar windows and units, then produce one comparable regional
product. Preserve real native inputs and test independent physical totals,
source metadata, seams and reruns. Tools may help these components directly;
the present exact reproductions often require algorithms different from library
defaults. A task on data acquisition would additionally need controlled source
access; these offline checks do not test downloads.

For **hard capability boundary**, move beyond supplied equations toward a
held-out predictor-claim audit or a sequential forecast experiment, with an
attainable independently implemented expert baseline. Require genuinely nested
selection and issue-time information, and distinguish scientific validity from
skill. A repeatable scientific miss is a candidate boundary; inability to beat
climatology on a tiny noisy sample is insufficient. The current runs identify
saturation and grader risks, not a demonstrated frontier limit.

## Selection and accounting

The staged five configurations are Astra Python/Rhiza/ACCORD and Luna
Python/ACCORD. They preserve the original tooling interests while isolating
backbone within a paired comparison. Current local library commits are pinned
in the [runtime manifest](../experiments/runtime-manifest-2026-10-08.json).
The Rhiza catalog is discoverable and its scripts were checked through Python
because `uv` is absent in the offline image. Its prepared, unrun focused
configuration pins the repaired reader image. The core array/I/O stack matches;
ACCORD additionally installs scikit-learn and statsmodels, so this condition is
the full library environment, not an isolated causal test of AfricaS2S alone.
acmadDL remains available, but supplied-input tasks cannot establish acquisition
benefits.

The six focused attempts used subscription inference and no direct API-key
calls: 928,561 cumulative tokens, including 656,896 cached input tokens. Six
required judging requests reported $0.6261312 at list prices, not invoiced API
charges. Control judging is recorded separately. The shared paid API cap remains
$100. Remaining matrix cells are unrun: the tested reproductions saturated and
tool suitability needs to improve before spending on a wider comparison.
