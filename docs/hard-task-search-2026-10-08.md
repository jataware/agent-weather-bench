The bounded scientific-difficulty search has not established a hard model capability boundary. Its first new canonical forecasting task was built and graded, then stopped **before inference** because its train-selected comparator did not beat climatology on blind verification. This stop was declared before inspecting withheld scores. No threshold, target period or selected method was changed after verification.

The `mam-forecast-synthesis` task uses the genuine four-centre C3S/CHIRPS source snapshot. It exposes model seasonal totals for 1993–2016, but observations only for 1993–2004. The twelve seasons 2005–2016 remain controller-private. A frozen HTTP catalogue still requires acquisition; curator-normalized seasonal totals deliberately isolate forecast-method decisions from the earlier native-unit/calendar exercise. This is fixed calibration across retrospective historical products, not sequential updating or historical real-time-vintage validation. Systems may choose any valid calibration/combination, and constant climatology is valid. Ordered three-category RPS is averaged within each year and then across years, with probability validity separate from the declared performance target.

Before any private score, the comparison design fixed 25 candidates: four Gaussian-regression single-centre forecasts or their equal probability average, each with shrinkage alpha 0, .25, .5, .75, 1 toward uniform climatology. Selection minimized mean RPS over chronological development seasons 2000–2004, each fit using only earlier training years. The selected method was ECMWF without shrinkage. Its blind mean RPS was **0.478486**, versus **0.442901** for uniform climatology and **0.541399** for raw equal-centre member probabilities. The expert was worse by 0.035585. The descriptive paired annual circular-block bootstrap interval for expert minus climatology was [-0.061116, 0.133181], based on twelve annual blocks, not216 independent cell-years. The predeclared inference gate required at least 0.01 absolute expert improvement; it failed, so there was no Luna attempt. Uniform climatology already meets the target of matching or beating both comparators. This candidate cannot support a difficulty claim, even though the forecast-selection question itself is canonical.

The primary and independent scalar scores agree within 5.55e-17; independently computed Gaussian probabilities agree within 9.44e-16. Native versus independently integrated/interpolated source totals agree within 1.14e-13 mm. Automatic controls pass for the expert, climatology, raw ensemble probabilities and coordinate reorder. Percent/wrong-sum faults fail the probability rule; target-period pooling fails a probe that compares actual earlier forecast probabilities after later forecast predictors change. No generic response gate rejects legitimate constant forecasts. The selection code/design/input hashes are locked before private scoring. Original source snapshots and assessments remain unchanged. Scientific approval remains pending, and no model certification was claimed.

Evidence: [predeclared design](../experiments/hard-task-mam-expert-design-2026-10-08.json), [baseline verification](../experiments/hard-task-mam-baseline-verification-2026-10-08.json), [template](../templates/mam-forecast-synthesis/README.md), and its `sources.json` and `certification.json`.

The daily onset/dry-spell alternative remains a deferred acquisition lead. Local caches did not contain a complete raw daily hindcast/forecast/observation triplet with the required event guard tail and independently checked interval semantics. A forecast-only normalized daily file is not enough. CHIRPS3 daily products also need their disaggregation variant recorded; their timing is not equivalent to an independent daily station blend. No scientific challenge was manufactured from an incomplete archive. The bounded [daily-data scout](../experiments/mam-next-data-scout-2026-10-08.json) records actual source paths and official product documentation.

The second candidate, `seasonal-objective-consolidation`, revisits the original probability-combination job with the three real ASO2026 local ACMAD-replication component products. It removes the archived task's plot/handoff/provenance packaging burden, preserves HTTP acquisition, and checks the scientific operation with new independent NumPy and scalar references: complete-vector availability, equal-component headline probabilities, nominal 2/8/8 sensitivity, support counts and category disagreement. Inherited skill/dry masks remain untouched. It is explicitly a likely easy canonical production step, not a claimed hard design or forecast-skill evaluation. One validated Luna pilot is planned; a pass ends this round with no boundary found. The [second predeclared design](../experiments/hard-task-consolidation-design-2026-10-08.json) fixes that interpretation before inference.

The consolidation authoring loop caught a real grading limitation before any model call: the common result envelope rejects missing values, including correct all-NaN forecast vectors on unsupported cells. The first certification therefore failed even though the two mathematical references agreed to 1.11e-16 on finite entries. Its original record remains under `var/review/hard-task-consolidation/certification-first.json` and `var/certification/seasonal-objective-consolidation/`. The repair is template-local: unsupported probabilities and disagreements use numeric zero storage fills, with `available_components==0` as the explicit absence mask. Those zeros are never interpreted as forecast distributions. The source NaNs remain unchanged, and no shared grader code or old template fingerprint was edited.

The real ASO source is sparse: of 25,921 cells, 22,581 have no complete component, 3,010 have one, 328 have two, and only 2 have all three. Source masks remove whole vectors in this snapshot, so naïve per-category averaging would accidentally agree with complete-vector selection on the original data. The controller now injects a single partial category vector in a diagnostic **copy** at a cell with overlapping genuine support. A per-category averaging fault must pass the original base arrays but fail changed-input regeneration. Both the supplementary toy fixture and this actual probe distinguish the scientific rule without pretending that fabricated missingness occurred historically. All three original source files have identical coordinates and retain their archived hashes.

The single actual Luna/Python consolidation pilot **passed** every completion instrument: coverage, numeric reference, support/simplex rule, replay and the partial-vector changed-source probe. It submitted in 62.99 agent seconds using 10 tool calls; CLI wall time including assessment was 72.51 seconds. Usage was 119,909 input tokens including 92,672 cached tokens, plus 4,409 output tokens: 27,237 uncached input tokens and 124,318 total tokens. There were no paid API calls; the subscription invoice cost is unknown. Both reruns retrieved the current catalogue and all three source files, with hash-verified controller acquisition evidence. This is one successful completion of a bounded objective-production operation; it does not establish saturation, observation-verified forecast skill, broad capability, or a weather-package advantage. No frontier comparison or extra attempt was run.

The initial pilot invocation never reached the adapter: literal JSON braces in the new brief caused formatting to fail. Its unchanged created-run record contains no events, driver log, usage or assessment. The literal braces were escaped, the rendered brief was smoke-checked, and the new fingerprint was recertified and proven in the same hardened Docker image before the **first actual model call**. The original prelaunch failure, readiness manifests and recovery invocation are preserved separately. Root also added a runner preflight and regression so future brief-format failures occur before run creation or Docker startup. This is an authoring/controller defect, not a failed model attempt.

Final consolidation evidence is in [pilot results](../experiments/hard-task-consolidation-results-2026-10-08.json), [prelaunch failure proof](../experiments/hard-task-consolidation-prelaunch-failure-2026-10-08.json), [final readiness](../experiments/hard-task-consolidation-readiness-rendered-2026-10-08.json), and [template](../templates/seasonal-objective-consolidation/README.md). Its frozen fingerprint is `615fea8bc4e687dc17a0105b97abb353cc387bd210a885a42ef23079729f57ff`. Automatic certification tests 1–4 pass; one trial is not full model certification or scientific approval. The original submission and assessment remain immutable.

This bounded track built **two new executable task templates**, inspected a deferred daily-data candidate, qualified one free-method forecasting target, and ran **one actual Luna attempt**. The MAM target was uninformative; the consolidation pilot passed. **No hard capability boundary was found.** A next research-style forecasting benchmark should first qualify attainable blind improvement over strong baselines using training/development information, provide enough independent temporal verification cases, and then permit bounded method search. It should not make this used holdout into a development set, retune this failed gate, or equate adding prescribed steps with scientific difficulty.

The final synthesis certificate also passes automatic tests1–4 after the README and literal-brace fix; its fingerprint is `d0f38aef16d5056579d99ac36afba0ea13394369aa4a0b7e4194586155fbd291`. Its trial count remains zero by design. The consolidation certificate's trial ledger has been refreshed to one passing current-fingerprint attempt, with full model certification still pending because it requires at least two attempts. No extra inference was spent to satisfy that administrative threshold. The [round manifest](../experiments/hard-task-round-summary-2026-10-08.json) records both frozen task identities and exact call counts.

The subsequent audit returned to actual incomplete original tasks rather than
inventing a harder target. In monthly cyclic calibration (#14), historical Luna
correctly implemented fitted moments, nested whole-year selection, outer
predictions and verification. Its constant-slope production comparator instead
used the lambda .25 cyclic coefficients: all 144 corresponding production
values were wrong, with maximum error 34.9691 mm and difference RMSE 9.1503 mm.
The other three systems' production predictions agreed within 2.85e-14 mm.
The old checker reported missing units before comparing those values, and grouped
production failure under a nested-selection label. The original assessment was
already partial; this audit identifies the scientific error hidden by that
diagnostic ordering rather than inventing an original false pass.

In station verification (#8), the headline and other four diagnostic variants
were correct. The combined diagnostic omitted the Celsius-as-Kelvin substitution:
all eight combined values were wrong, with maximum error 270.5651 K. Two fresh
serial Docker executions confirm causation at the code-expression level: changing
only `if v==2` to `if v in (2,4)` fixes every numerical field, while the other eight
fields remain bit-for-bit identical. See the [slice comparisons](../experiments/historical-science-slices-2026-10-08.json)
and [surgical replay](../experiments/station-surgical-replay-2026-10-08.json).

A new [eight-request judge calibration](../experiments/failure-judge-calibration-eight-call-2026-10-08.json)
found a broad review that confidently approved this faulty station method. Its
citations were valid; the reasoning missed the combined transformation. Broad
review caught the monthly error. Questions about each implicated component caught
both errors and passed narrow expression repairs and unaffected components. Both
detections survived removal of the controller's numeric-diagnostic file, with
task documents, source, reports and structured answers retained. These are two
selected failures and single reviews, not population estimates. The historical
attempts ran no model judge, so this is new calibration rather than evidence of
an original judge miss. CLI list-price usage totaled $1.041; actual subscription
billing is unknown.

The executable `monthly-cycle-calibration` template preserves the original
scientific code byte-for-byte and all 23 reference arrays exactly; a separate
FFT/scalar-covariance driver agrees within 3.64e-12. Fitted, nested, verification,
production, unit declarations and five rerun/isolation instruments are visible
separately. Eight controls and an actual Docker correct-control assessment pass.
Saved inference is tested without known target/result files and with changed SST;
this cannot prove the absence of hidden renamed targets or equivalent hidden
refitting, which remain code-review obligations. Array unit attributes are
documentary; the task separately checks unit declarations and numerical quantities.

Prelaunch review found a curated AfricaS2S function excerpt in the inherited
inputs. It was removed from actor staging before either fresh attempt; archived
private bytes and scientific input files remain unchanged. The [unlaunched plan](../experiments/monthly-fragility-prelaunch-hold-2026-10-08.json)
is preserved separately. The replacement [frozen pair](../experiments/monthly-fragility-v2-plan-2026-10-08.json)
uses ordinary optional library documentation, identical runtime/budgets and high
reasoning for Luna and Astra, one attempt each with no retries. This pair is
matched to itself, while the historical Luna attempt used medium reasoning and
a different runtime, tool budget and delivery contract. It is a fresh test of
the preserved scientific job, not a matched estimate of longitudinal improvement.

Both fresh attempts completed successfully:

| System | Computed checks | Agent seconds | Tool calls | Fresh input + output tokens |
| --- | --- | ---: | ---: | ---: |
| Luna, high reasoning | 16/16 pass | 113.73 | 9 | 42,439 |
| Astra, high reasoning | 16/16 pass | 330.07 | 5 | 45,928 |

All five rerun/isolation probes pass for each, including saved-state inference
after targets and known result stores are removed and production SST changes.
A separate [FFT verification](../experiments/monthly-fragility-v2-numeric-verification-2026-10-08.json)
agrees on all 23 frozen arrays within their declared bounds; production predictions
differ by at most 5.69e-14 mm. Static code review confirms that both inference
commands read fitted parameters and predictors, without accessing targets or
refitting. Both use NumPy/xarray, with no observed weather-library execution.
Their three supplementary prose-judge checks remain unresolved because these
attempts used `--no-judge`; completion passes under the explicitly declared
numerical policy. This is not an all-instruments prose certification.

The [two-attempt results](../experiments/monthly-fragility-v2-results-2026-10-08.json)
verify actual public input inventories, immutable artifact bundles and traces.
Test 5 now records both classified current-fingerprint trials; all five
certification tests pass, while scientific approval remains pending. Its prelaunch certificate
was saved before updating this non-deciding status metadata; the scientific
fingerprint remains `45b7ffbdf625119333a5a2510ae51221437ce1d3d61b4f0922d66179a44b592d`.
The [trial review](../experiments/monthly-fragility-v2-trial-review-2026-10-08.json)
records that update separately. Twenty targeted regression tests pass.

The fresh pair supplies no failure-based capability boundary or tooling benefit.
The historical implementation errors and new broad-judge miss are concrete
fragility evidence, and successful fresh completions show that those observations
must not be promoted into a persistent inability claim. Single successful pilots
likewise do not establish saturation. No extra attempts or target changes were
made after seeing these results.
