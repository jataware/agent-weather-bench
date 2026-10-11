# Grader stress investigation — 8 October 2026

The five existing templates passed this bounded stress test. No new grader defect was found, and no deciding code, template contract or historical assessment was changed. This supports proceeding with the separate ingestion and forecast-audit experiments; it does not establish that the graders cover every scientifically valid method.

This evidence predates the subsequent optional `response_results(results, inputs, params)` controller hook, developed for the new forecast-audit task so changing audit diagnostics cannot masquerade as forecast responsiveness. The [controller revision ledger](../experiments/response-projection-revision-2026-10-08.json) preserves the earlier fingerprints and deciding-file hashes. The five legacy templates keep their default response comparison; their refreshed automatic certification is recorded separately in [response-projection controls](../experiments/response-projection-controls-2026-10-08.json). The original stress evidence below remains under its original fingerprints.

## Legal representations and complete reruns

For one real-data development instance per template, a trusted correct control was serialized eight ways: Zarr 2 or 3, consolidated or unconsolidated metadata, and original or reversed coordinate/dimension order. Every case also used different chunking, moved scalar results between the store and `answer.json` where applicable, and wrote date coordinates as text where applicable.

All **40 representations** agreed by coordinate label and matched an accepted reference where a reference exists. Numeric differences from representation changes were zero. For the reversed, consolidated Zarr 2 case, each submitted command was wrapped to apply the same transformation on every rerun. All **five complete computed assessments** passed, including replay and changed-data or information-boundary probes. This checks the command, rather than merely accepting a one-time edited result store.

| Template | Scientific fault control | Checks that rejected the fault |
| --- | --- | --- |
| Kenya forecast revision, version 3 | Sum cumulative rainfall instead of differencing it | Reference variant |
| Seasonal rainfall calibration, version 4 | Fit each hindcast using its own held-out year | Held-out-year isolation; cross-validation process step |
| Weeks 3–4 rainfall, version 4 | Center a forecast smoother on later issues | Future-information probe |
| Seasonal CCA reproduction, version 1 | Use the complete target history inside outer hindcasts | Outer-year isolation; reference variant |
| Rainfall downscaling, version 2 | Fit each hindcast using its own held-out year | Held-out-year isolation; reference variant |

All five scientific fault controls failed on the intended checks. Separately, swapping two coordinate labels without moving the corresponding data failed numerical comparison in each template. These are distinct from legitimate axis permutations, which move labels and data together.

The seasonal-calibration reference deliberately omits coordinate arrays because the controller first aligns the submission to its required frame. The diagnostic follows that production sequence before matching reference results. Testing the lower-level comparator without this alignment would incorrectly report rejection of reversed arrays; the complete assessor accepts them.

## Different numerical implementations

An independent spherical area expression uses

`sin(latitude + half_width) - sin(latitude - half_width) = 2 cos(latitude) sin(half_width)`

with long-double intermediates. On the downscaling grid it differs from the primary expression by at most **3.501772880554199e-7 m²**, inside the version 2 bound of **0.0002842170943040411 m²**. The equivalent expression passes, while changing the prescribed Earth radius by one metre fails. Analytically specified tied-predictor rank mapping, interpolated values and clamped tails also agree with the implementation. The earlier regression for edge-subtracted longitude widths remains in place.

For CCA, changing predictor column order, target column order and the arbitrary signs returned by EOF/canonical SVDs leaves the scientific forecast equivalent. All **28 combinations** of 14 candidate configurations and two training lengths (12 and 27 years) passed their declared numerical bounds, including leave-one-out uncertainty. Maximum differences were **7.503331289626658e-12 mm** for forecast means and **5.995204332975845e-15** for probabilities.

The CCA checks are mathematical transformations of the same implementation, not a newly independent CCA implementation. The existing independently implemented eigenvalue-based reference provides separate evidence; these checks add ordering and sign coverage. Likewise, storage transformations preserve the control's science rather than supplying another scientific solution.

## Evidence and reproduction

- [Representation and scientific fault results](../experiments/grader-stress-2026-10-08.json), including template fingerprints and hashes of the ten complete assessment files.
- [Numerical equivalence results](../experiments/grader-numerical-stress-2026-10-08.json), with every CCA case.
- [Storage/replay diagnostic](../experiments/grader_stress.py).
- [Numerical diagnostic](../experiments/grader_numerical_stress.py).
- [Small numerical regression](../tests/test_grader_numerical_stress.py).

The generated controls and complete assessment records are under `var/review/grader-stress-2026-10-08-v3/`. Two earlier diagnostic-development runs under the same prefix are excluded: one wrapper accidentally imported controller modules inside a rerun, and one lower-level comparison omitted the seasonal coordinate-alignment step. Neither was an agent attempt or a grader defect. The published JSON contains only the completed corrected run.

Reproduce into a new destination, preserving the recorded evidence:

```sh
.venv/bin/python experiments/grader_stress.py \
  --destination var/review/grader-stress-repeat \
  --output var/review/grader-stress-repeat.json
.venv/bin/python experiments/grader_numerical_stress.py \
  --inputs var/review/grader-stress-repeat/seasonal-cca-reproduction/inputs \
  --output var/review/grader-numerical-stress-repeat.json
.venv/bin/python -m pytest -q tests/test_grader_numerical_stress.py tests/test_downscaling_geometry.py
```

No model calls, paid API calls or prose judging were used. Required prose judgments therefore remain unresolved in the complete assessment files; the positive result is **computed pass**, not a claim that every instrument passed. The scientific controls are existing planted faults, not blind discoveries. One instance per template and this finite set of representations cannot certify all alternative methods, numerical degeneracies or previously unknown mistakes. Scientific approval remains pending.
