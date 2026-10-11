# Guided weather-tool efficiency study

This separate, predeclared study compares fresh Luna attempts on the same canonical MAM outlook task. The intervention bundles the pinned ACCORD weather packages with a concise public-API guide and runnable synthetic examples. The comparator uses general scientific Python. Both use the same Luna backbone, high reasoning effort, adapter, compute allocation and enforced budget caps. This estimates the bundle's practical value, not the isolated effect of a library.

The machine-readable design is `experiments/efficiency_plan_2026-10-08.json`. Four fresh system IDs are reserved: two for the initial parallel pair and two for at most one replication pair. The replication requires a scientifically valid guided completion, substantive use of both weather helpers, successful own-command replay and no known runtime or grading issue. It additionally requires baseline failure or at least 10% improvement in fresh-input-plus-output tokens, cumulative tokens or agent-phase elapsed time. All three comparisons will be reported even when just one triggers replication. Repeating one instance tests stochastic repeatability, not generalization across tasks.

All failures remain assigned to their original arm, including a scientific pass that fails the requested helper-use condition. Imports and the synthetic smoke test do not establish substantive use: returned normalized totals and calibrated probabilities must feed the submitted arrays. The task contract and historical attempts remain unchanged.

Resource reporting includes all failed-attempt usage, cached and fresh input, output, cumulative tokens, elapsed time, command time and HTTP acquisition bytes. Agent-phase elapsed time is separate from total CLI wall time, which includes assessment and replay. Agent time minus measured command time is only a model/adapter/transport overhead proxy. Native calibration can reduce code-writing effort while increasing runtime. Success-adjusted resources divide total arm consumption by scientifically valid completions; this is undefined when there are none. Fresh-input-plus-output is a resource proxy, not a dollar-weighted price. Direct paid API use is $0; subscription invoice costs are unknown. No dollar savings or statistical significance is claimed.

The launcher pins Codex CLI 0.160.0 by version and SHA256, validates all study configuration hashes and the existing scientific/Docker control gates, and refuses to reuse an invocation directory. No automatic retries or paid API fallback are allowed.

The initial pair finished with two submitted, reproducible envelopes and two original computed failures. The guided arm substantively used native `normalize` for all four centres and native `calibrate` for LOYO hindcasts and the 2016 outlook; those returned arrays directly feed the submission. Imports and the synthetic example were excluded from this compliance finding.

| Initial matched attempt | General Python | Guided ACCORD |
| --- | ---: | ---: |
| Original computed result | fail | fail |
| Own-command replay | pass | pass |
| Fresh input tokens | 65,201 | 31,910 |
| Cached input tokens | 197,120 | 183,040 |
| Output tokens | 7,645 | 6,905 |
| Cumulative tokens | 269,966 | 221,855 |
| Fresh input + output | 72,846 | 38,815 |
| Agent phase, seconds | 107.1 | 117.1 |
| Full CLI including assessment, seconds | 147.3 | 168.2 |

Guidance coincided with 46.7% less fresh-input-plus-output and 17.8% fewer cumulative tokens, but 9.2% more agent-phase time and 14.2% more full CLI time. There are no valid completions under the unchanged strict contract, so resources per valid completion are undefined. These are descriptive resource differences between two failed attempts, not demonstrated efficiency at producing a valid forecast.

Both attempts sum native float32 CHIRPS monthly observations before converting the totals to float64. Their seasonal observations differ from the accepted float64 calculation by at most 0.0000229 mm; per-centre probabilities differ by at most 0.0000000538. Both match the intended calendar integration, fold-local calibration and equal-model recipe apart from this precision difference. The accepted recipe and tolerances remain unchanged, and the original verdicts are preserved.

Both also fail the held-out-observation intervention. Its dtype conversion affects the entire monthly observation field, including the otherwise unchanged training years; those submissions therefore perform their remaining training sums at a different precision during the intervention. Independent review confirmed that this confounds the assertion that the held-out forecast used its own verifying observation. This failure alone does not establish scientific leakage. The predeclared replication gate is false, and no replication attempts have launched.

Frozen helper-use evidence and call counts are in `experiments/efficiency_tool_review_2026-10-08.json`; the counts are derived from executed code paths and original traces, rather than added instrumented counters, and an independent source review confirmed them. One successful calculation calls normalization four times and calibration twice. The agent phase made 17 real-data normalization calls and eight calibration calls across five invocations, including debug runs; its separate synthetic example made one and two calls respectively. Each of the three original controller replays made four and two real-data calls. Complete accounting and verified source-transfer evidence are in `experiments/efficiency_results_2026-10-08.json`.

Independent review confirmed the intervention's dtype confound. The initial plan, results, gate and review were archived with a SHA256 manifest in `experiments/efficiency_initial_evidence_2026-10-08/`. The original pair is historical v1 evidence, and its verdicts remain unchanged.

The independent diagnostic reproduces every required result from both submissions when using their rounded observation totals; probability residuals are at most 1.34 × 10⁻¹⁵. The original held-out intervention creates a 3.58 × 10⁻⁸ forecast difference, while the intervention preserving the original dtype produces exactly zero difference. This supports a precision-only implementation error in both submissions and a separate false leakage attribution by the original probe. It does not erase their genuine mismatch with the declared float64 error bounds. Diagnostic evidence is retained in `var/review/efficiency-precision-review-20261008/diagnostic.json`.

A separate precision-clarification phase was declared in `experiments/efficiency_precision_plan_2026-10-08.json` and run after the narrow v2 probe repair passed its control gates. Both received the identical instruction: “Promote forecast rates AND CHIRPS monthly values to float64 before any summation/interpolation.” All other scientific instructions, adapters, backbone, reasoning effort, compute and budgets remained matched. This asks whether valid-completion efficiency can be measured after common precision clarification; it is not a replication of the initial pair. The four model attempts across both phases are now complete. No third pair or automatic retries occurred.

| Fresh precision-clarification attempt | General Python | Guided ACCORD |
| --- | ---: | ---: |
| Original computed result | fail: missing results | pass: all ten checks |
| Driver stop | token limit | token limit |
| Own-command replay | blocked by missing envelope | pass |
| Fresh input tokens | 46,964 | 43,265 |
| Cached input tokens | 314,368 | 298,240 |
| Output tokens | 11,486 | 11,306 |
| Cumulative tokens | 372,818 | 352,811 |
| Fresh input + output | 58,450 | 54,571 |
| Agent phase, seconds | 205.2 | 150.5 |
| Full CLI including assessment, seconds | 207.7 | 197.6 |

Guided ACCORD produced a scientifically valid, fresh-data-responsive and reproducible forecast while generic Python stopped with only `run.py`. Guided used 6.6% less fresh-input-plus-output, 5.4% fewer cumulative tokens and 26.7% less agent-phase time. Full CLI time was 4.9% lower despite performing all three numerical replays; Python's failed envelope blocked those replays. This is a useful observed completion and resource signal from one matched pair, not a stable performance ranking or a frontier capability boundary.

Both adapters hit the requested cumulative token cap at a usage checkpoint; actual usage overshot 350,000 and is reported in full. The guided envelope was complete before stopping. Its later calls checked source provenance, coordinates, dtypes and a fresh own-command rerun. Python spent late calls appending its implementation and never executed that script before stopping. All original stop statuses remain visible; scientific validity is determined from artifacts and the controller's replays.

The guided code substantively calls normalization four times and calibration twice per own-command calculation. Its agent phase additionally performed four exploratory real-data normalization calls, then five script invocations, making 24 real-data normalization and ten calibration calls in total; the separate synthetic example made one and two respectively. All three controller replays used the native calculation again. Required outputs consume the returned native arrays, rather than a separate replacement implementation. The initial native forecast result omits the singleton forecast-year axis, which the agent repaired by adding that axis; it also corrected a general RPS one-hot axis error. No private-module exploration or added task solver was needed. Frozen source and trace evidence is in `experiments/efficiency_precision_tool_review_2026-10-08.json`.

The guided valid completion consumed 54,571 fresh-input-plus-output tokens; Python has zero valid completions, so its resources per valid completion are undefined. Its reported command time is mostly exploration and file writing, whereas the guided command time includes native calculations and reruns: these are not comparative library-runtime benchmarks. Historical cross-validated RPSS was +0.0934, while withheld-2016 RPSS was −0.4554; passing the recipe does not establish a skilful withheld-season forecast. The supplementary prose judge was not run.

Every active token component is lower for guided ACCORD in this pair: fresh input by 7.9%, cached input by 5.1%, and output by 1.6%. Both report zero cache-write tokens. For a hypothetical variable token charge `F*p_fresh + C*p_cached + O*p_output`, any nonnegative rates with a positive billed denominator therefore imply a reduction between 1.6% and 7.9%, assuming these are the only active metered classes and there are no fixed or tool fees. This is a rate-weighted per-attempt proxy, not a subscription invoice or a dollar savings claim. Reasoning tokens are already included in output.

The complete four-attempt ledger is `experiments/efficiency_all_phases_results_2026-10-08.json`: 1,217,450 cumulative tokens, including 992,768 cached input tokens and 37,342 output tokens. Fresh input was 187,340 tokens. All failures are included. Comparison and success-adjusted efficiency remain phase-specific because the grading version and common precision instruction changed. Direct paid API spending was $0; subscription invoice cost is unknown. The native guide and examples merit a broader matched study, but this bounded investigation stops here.
