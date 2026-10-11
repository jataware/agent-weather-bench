# Forecast audit investigation — 8 October 2026

The initial CCA reproduction task was saturated by both Astra and Luna. This investigation changes the demand: the agent audits a working forecast experiment, determines whether its evidence supports its report, and produces a defensible replacement. A hard capability boundary is a hypothesis, not a finding from these controls.

## The task

`seasonal-forecast-audit` uses the same frozen real JJA SST / OND rainfall subset as the CCA task: 27 predictor cells, twelve East African rainfall cells, target years 1993–2019, and production predictor years 2020–2023. It does not simulate weather or pretend final-vintage observations are real-time archives. Files are restored from the existing private snapshot with SHA256 checks; source records accompany the candidate.

Four opaque development cases distinguish different scientific diagnoses:

| Case | Candidate | Expected audit |
| --- | --- | --- |
| case-a | Fixed ridge model; centering and fitting use earlier targets within each fold; report states retrospective limits | Clean pipeline and supported report |
| case-b | Target mean computed over the entire record before expanding regression fits | Preprocessing leaks held-out and later targets |
| case-c | Predictor screened using correlations with the entire target record before expanding fits | Selection leaks held-out and later targets |
| case-d | Numerically clean past-only candidate; report explicitly reuses architecture-development scores as an independent final test and deployment evidence | Valid past-only hindcasts, unsupported report |

These cases are author-visible in this document. The agent sees candidate code, configuration and report, not an answer key or a fault-named instance. The code is intentionally readable: this first investigation establishes whether scientific auditing and repair works before increasing subtlety.

The delivery includes reproduction of the original 15 × 12 hindcasts and pooled RMSE, freely chosen repaired hindcasts, four production forecasts, an expanding-climatology diagnostic, three structured audit/skill claims, and a report with concrete code or report evidence. A clean candidate may be retained. A repaired method need not beat climatology. The known-valid ridge control currently scores worse than climatology and still meets the scientific checks; a distinct climatology control is also accepted.

## How grading avoids a prescribed repair

There is no reference match for repaired forecasts. Coverage, nonnegative rainfall, independently recomputed metrics, numerical reproduction of the supplied original, information-boundary interventions and claims are separate instruments. The original candidate has a fixed numerical answer because reproducing the evidence under audit is part of the job. Its primary implementation uses a dual ridge solve; the independent reconstruction uses a primal normal equation and scalar predictor-correlation loops. The score's independent implementation uses scalar accumulation and cumulative past means rather than the main xarray/vectorized calculation.

Input-response checks compare only the repaired forecasts: changed original-audit diagnostics cannot rescue cached forecasts. Explicit `RESPONSE_GROUPS` additionally requires both the hindcast and production deliverables to respond to at least one permitted input change; climatology can satisfy both through changed training targets alone. A planted cached control recomputes the diagnostics and metrics while retaining its predictions, and must fail this check.

The target interventions test every year from 2005 through 2019, replacing targets from that year onward and predictors from strictly later years; the forecast's own JJA predictors remain available. Predictions **through** that cut must remain unchanged; later predictions may legitimately change as those observations enter training. Separate production interventions test each cut at 2021, 2022 and 2023, requiring forecasts before the cut to remain unchanged. The probes exercise information boundaries of the entire computation rather than checking names of fitted estimators. A localized lookahead control that uses 2007 observations only for its 2006 forecast demonstrates why testing just a few cuts would miss faults between them. The global-screening control is numerically insensitive at the 2017 and 2018 cuts because the selected predictor does not change there, and fails at thirteen other cuts. These are finite interventions, not a proof against an adversarial program.

The original code, configuration and report also appear in the instance brief so the report judge has the evidence it needs. A required report judge checks whether the diagnosis has concrete evidence and the score's scope is honestly stated. It is never the only detector of leakage: global target preprocessing, global feature selection, global future-feature standardization, direct target use and localized one-year lookahead are all planted numeric controls separated by target interventions. Unsupported structured report claims also fail deterministically. No significance test or skill threshold gates completion; scores remain diagnostic, with ranking disabled for this small retrospective sample.

Float64 replay/reconstruction tolerances use an operation allowance of one million and magnitude 10,000 mm, giving `2.220446049250313e-6 mm`. This deliberately accommodates different valid linear solvers and aggregate evaluation order while remaining tiny relative to rainfall and planted faults. Coordinates remain exact. The three reported RMSE scalars permit one float32 storage rounding at 10,000 mm, giving `0.0011920928955078125 mm`; their arithmetic must accumulate in float64 from the delivered forecasts. Repaired forecasts may be float32. An accepted float32 forecast/scalar control checks serialization and arithmetic, while a 1 mm metric error is rejected. Skill claims are recomputed from delivered forecasts and the template-relative frozen target file `var/private/templates/seasonal-forecast-audit/agent-inputs/targets.nc`; they do not trust reported scalars. Claims are checked on the original frozen instance, not controller perturbation reruns.

## Initial experiment

The proposed first agent pair is matched Astra/Python and Astra/ACCORD on one faulted instance, after automatic controls and a Docker/judge check pass. This compares full environments and does not isolate one library. A second case is justified only if the pair reveals an informative difference or a reproducible scientific failure; a pair that passes establishes attainability for those systems, not a hard boundary. Model attempts and their costs are recorded by the controller separately from these deterministic controls.

Scientific approval and redistribution approval remain pending. Automatic controls establish implementation checks, not domain certification or a demonstrated capability limit.


## Runtime finding during author validation

An attempted optimization used Python threads to assess independent control groups. The controller's netCDF4/HDF5 reads were not thread-safe: HDF5 errors appeared and a separate threaded partial-cache diagnostic exited with signal11. This is an author-validation infrastructure failure, not an agent result. The threaded controller was stopped, logs preserved under `var/review/audit-certification-threaded-failure.log`, and all frozen source hashes verified intact. Subsequent validation uses serial controllers or fresh interpreter processes with independent HDF5 state, at most two concurrent control workers. The original Docker import-order issue is separate.


## Grading defects found before agent evaluation

Independent review exposed two further false acceptances in the first draft. A cached hindcast could be masked by responsive production forecasts, and cached production could be masked by responsive hindcasts. Full serial assessments confirmed both passed the earlier response projection. Replaying those exact submissions with per-deliverable response groups now fails the cached group in each direction; the unchanged other group still responds as expected. Historical diagnostics remain in `var/review/audit-partial-cache-before-groups.json`, with corrected response evidence in `var/review/audit-partial-cache-after-groups/diagnostic.json`.

A second defect trusted the submitted RMSE scalar when deciding the skill claim. Lowering climatology's reported RMSE by `1e-6 mm` stayed within numeric tolerance but falsely produced a positive skill claim. The revised claim computes skill directly from the delivered forecast arrays and frozen truth: that control remains within scalar tolerance, but its manufactured improvement claim fails while controller skill is exactly zero. The accepted float32 control has scalar error `2.7506769e-6 mm`, and a deliberately wrong 1 mm metric fails. These precision diagnostics are retained in `var/review/audit-precision-controls/diagnostic.json`.

The core extensions are optional. Earlier templates retain their original default input-response semantics; their historical comparisons and deciding-code snapshots are preserved separately by the investigation controller. No audit model attempts were spent finding these defects.


## Automatic validation completed

All four automatic certification tests pass under the final template fingerprint. The validation covers **68 assessments across four instances**: twelve known-correct or accepted-method assessments (ridge, climatology and float32 storage) and 56 planted-fault assessments. Every control produced its intended computed results. Independent score implementations agree exactly, and the independent primal/dual candidate reconstruction checks pass on all four cases. Ten targeted scientific and response-group tests pass. Required prose judging, agent trials and scientific approval remain separate gates.

Two fresh interpreter workers completed all control assessments without further native failures. The final report initially could not serialize a NumPy boolean in the independent-regression evidence. Converting that flag to a builtin boolean changed no calculation. The certificate reuses the completed, hash-recorded worker result files and reruns the cheap independent agreement checks; `certification.json.control_evidence` records this recovery explicitly. No agent inference was repeated or used to validate the repair.


## Completed initial pair and path erratum

Both Astra-high attempts on case-c, Python and ACCORD, pass computed checks and the required scientific report review. Both identify whole-record supervised predictor screening, move it into each expanding training fold, retain the candidate's fixed one-predictor ridge architecture, and honestly report worse skill than climatology. Their delivered original, repaired and production arrays agree bitwise. Original RMSE is 150.848485 mm; honest repaired RMSE is 166.133459 mm versus expanding climatology's 165.827115 mm. Neither used the accepted climatology fallback or executed a weather-specific helper. ACCORD documentation was consulted. The [combined report](parallel-investigations-2026-10-08.md) records usage and the study's limits; [independent delivery review](../experiments/audit-delivery-review-2026-10-08.json) records hashes and the numerical comparison.

These two attempts belong to v1. Both agents found its wrong `/task/scientific-objective.md` pointer and read the authoritative file supplied under the input directory. The v2 brief corrects that path, with no scientific change. The [erratum ledger](../experiments/audit-brief-erratum-2026-10-08.json) records archived v1 contracts and reviewed trials, unchanged implementation hashes, inherited scientific-control evidence, four staging checks and a fresh Docker known-correct assessment. No v2 agent trials have been run; its trial status remains pending. Original v1 assessments are preserved.

This establishes attainability on one deliberately readable faulty workflow. It does not test whether agents accept a clean workflow, and does not establish a hard capability boundary or operational forecasting skill. A matched clean/faulty audit with neutral configuration names is the next focused experiment; it has not been launched.
