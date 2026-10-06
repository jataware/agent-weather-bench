# Weather forecasting task packages for review

`review-0.2` incorporates [the three exported critiques](../docs/reviews/2026-10-02/response.md).
Seasonal calibration now includes agent acquisition from a source plan; its
normalized local inputs are controller development fixtures. A verified, training-only
frozen native-source transport now supports development attempts. The rubrics score
distinct scientific outcomes, with unweighted validity requirements. All tasks use shared
[provenance](provenance-contract.md); the first three use the shared
[command replay](replay-contract.md), while the short-rains task defines
alternate-input replay and saved-state inference in its own contract. The new
verification, optimization and multivariate tasks likewise define their specific
changed-input or saved-state contracts.

Open [the HTML review index](index.html) in a browser to inspect and critique each
package. Each standalone page includes the prompt, rubric, sources and reference
evidence, with general and per-check critique fields. Notes save in the browser
when local storage is available. Export Markdown to discuss the review, or JSON
to preserve and re-import it. Review notes do not edit package files or approve
an experiment. The pages contain public package metadata, not private reference arrays.

Regenerate the pages after changing a package with
`.venv/bin/python -m weatherbench tasks render`. The Markdown and YAML files remain the
source of truth; exports record their hashes so reviews identify the exact draft.

These are concrete development packages awaiting scientific review by Zeek. They are standalone tasks: sequence order and retained substrate are
defined in [the accretion experiment](../experiments/accretion-review.yaml).
The preparation tooling has no model client and never runs submitted code.

| Package | Scientific work | Main review question |
| --- | --- | --- |
| [Seasonal calibration](seasonal-calibration/prompt.md) | Process monthly ensembles and observations, validate a calibration, and deliver a saved prediction workflow | Are the validation evidence and required scientific checks sufficient while allowing different sound methods? |
| [ACMAD objective](acmad-objective/prompt.md) | Consolidate three component probability products, audit missing support, and test weighting sensitivity | Does this final operational step make a sufficiently substantial standalone task, and is the missing-component rule faithful? |
| [WVG definition audit](wvg-definition-audit/prompt.md) | Read the paper and implementation, recompute two predictor geometries, and explain discrepancies | Is this a useful first literature task, or should it await the author data and become a larger forecast-skill audit? |
| [Short-rains workflow](short-rains-workflow/prompt.md) | Repair a real unit convention, select predictors with nested rolling verification, calibrate forecasts and retain a saved fit | Can a model complete a source-driven scientific adaptation with honest uncertainty and no leakage? |
| [WeatherBench verification](weatherbench-verification/prompt.md) | Reconstruct valid-time, area-weighted metrics and diagnose comparison faults on real public forecasts | Does the comparison preserve common support and undefined scores while remaining reusable on changed forecasts? |
| [Subseasonal optimization](subseasonal-optimization/prompt.md) | Improve real weeks 3–4 precipitation forecasts with bounded development feedback and separate final scoring | Are gains admissible and reproducible, and does the interpretation distinguish development selection from final performance? |
| [Seasonal CCA reproduction](cca-seasonal-reproduction/prompt.md) | Reconstruct multivariate dimension reduction, nested mode selection, calibration and saved-state inference | Are equivalent sign/rotation choices accepted while full-training leakage and cached inference are rejected? |
| [Station verification](station-verification/prompt.md) | Decode real NOAA observations and compare grid-to-station interpolation on exact UTC valid-time support | Are missingness, quality flags and zero-support stations retained honestly, with common cases for method comparison? |
| [Monthly cyclic calibration](monthly-cycle-calibration/prompt.md) | Fit cyclic monthly slopes with nested whole-year validation and assess statistical sharing | Does excluding only one month leak the other eleven targets into the smoother, and is a supported negative result interpreted honestly? |
| [Conservative downscaling](conservative-downscaling/prompt.md) | Diagnose unresolved source units, calibrate ranks and preserve calibrated coarse volume on a fine grid | Does physical conservation hold for the correct mapped quantity, with training-only spatial detail and saved inference? |

Each directory contains a prompt, task specification, source record, rubric tree,
and focused review sheet. [The review guide](../docs/task-package-review.md) explains
the proposed review order and current limitations. Expert approval is deliberately
unset; preparing a package does not constitute scientific sign-off.

Local input copies and controller references are kept in `var/private/tasks/`
and ignored by Git. A tracked `input-manifest.json` records hashes and visibility.
No full repository or controller reference should be mounted into an agent.
The public papers and institutional source records are linked; literature access
must be supplied through a frozen corpus or a permitted document snapshot when
an experiment is launched. The packet itself does not imply open-web access.

From the project root:

```sh
.venv/bin/python -m weatherbench tasks prepare
.venv/bin/python -m weatherbench tasks validate
.venv/bin/python -m pytest -q
```

`prepare` verifies frozen inputs and computes bounded independent reference
calculations. It does not fit an agent calibration or launch attempts. `validate`
checks manifests, references and rubric structure. An optional static check of
an already available submission is:

```sh
.venv/bin/python -m weatherbench tasks check acmad-objective --submission /path/to/submission
```

Static checks cannot establish clean replay, saved-state use, scientific
interpretation or information integrity. They report unresolved rubric leaves
and cannot declare completion. Those checks need trusted execution evidence and
expert review before an experiment can use the packages.
