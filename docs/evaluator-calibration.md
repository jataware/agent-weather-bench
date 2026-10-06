# Initial evaluator calibration

The first natural ACMAD cohort exposed a numerical false rejection: a mathematically equivalent pairwise disagreement calculation converted the supplied float32 percentages to fractions before subtracting and converting back. Its largest discrepancy from the float64 reference was about 0.000005722 percentage points, while its grid and missingness agreed. This prompted a narrowly scoped arithmetic policy, supported by independent contrasts. It does not establish expert acceptance of the whole submission.

## Disagreement precision policy

`acmad-objective` checks `disagreement_pp` with an absolute tolerance of approximately **0.000017882 percentage points** and zero relative tolerance. Other fields retain their existing comparison policy. Dimensions, coordinates, missingness, infinities and declared units remain checked.

The allowance comes from bounded float32 arithmetic, rather than rounding up the observed run's error. Let `u = eps(float32) / 2`. Each supplied percentage lies between 0 and 100. For two extrema, converting each to fractions, subtracting, then scaling the difference back gives an absolute forward-error bound no greater than `100 * gamma_3`, with `gamma_3 = 3u / (1 - 3u)`. The bound accounts for endpoint conversion as well as subtraction and rescaling; cancellation makes an absolute allowance necessary near zero. Float32 source quantization is already present in the reference inputs, so the allowance concerns subsequent arithmetic.

Setting relative tolerance to zero also removes the previous larger allowance at high disagreement: an error of 0.00005 percentage points at a disagreement of 100 is now rejected. This policy does not cover lower precision, rounded presentation values, altered grids, filled missing cells or different scientific definitions. The check records its tolerance, maximum finite absolute discrepancy, number of finite entries outside tolerance, structural checks and units.

The regression contrasts independently calculate disagreement by pairwise differences in native percentages and float32 fractions. They cover a valid alternative calculation, single-component and missing support, meaningful disagreement and unit-scale errors, changed grids/dimensions/missingness, infinities, and unchanged strictness for the probability field. Original submissions and assessments are retained; any subsequent assessment should carry the updated evaluator fingerprint.

## Review still needed

Ezekiel remains the initial reviewer of scientific interpretation, provenance, claimed forecast skill and the usability of the retained workflow. Passing the numerical comparison establishes only agreement within this precision policy. Replay success, scientific correctness, complete evidence and expert interpretation remain separate requirements. RCC or additional human testing can broaden calibration later; it is not a prerequisite for the current local development cycle.

## Evidence and failure origin

Judge packets now include bounded controller tool events, without provider responses, model identity, costs or host authentication metadata. Every omitted/truncated event is declared. A corrected exploratory command failure does not invalidate a working final solution; an omitted action in a truncated trace cannot be treated as absent. Neil Hausmann’s substrate summary still distinguishes listing, reading and execution, and remains a lower bound from observable commands.

Unavailable controller infrastructure leaves replay or prediction unresolved; a declared scientific command that fails, or produces malformed/wrong results, fails its own check. Submission integrity, mathematical validity, offline reproducibility, forecast skill and scientific interpretation remain separate. The HTML run report exposes criterion outcomes alongside score bounds.

The new short-rains task has independent numerical implementations and executable target/future perturbation and saved-state inference checks. These can reject specific defects, but neither numerical reference agreement nor a handful of constructed cases establishes reliability of an expert judge. The blinded judge pilot has prepared packets and operational expectations; human labels remain unset. All old assessments retain their evaluator fingerprint.

The frontier pilot also exposed a representation-only false rejection: the task specified training years 1993–2019 but did not prescribe whether `answer.json` should enumerate them or store inclusive endpoints. The checker now accepts either accurate representation, with independent tests rejecting shortened or extended periods and nonnumeric year labels. Task prompts, source inputs, numerical references and original model outputs were unchanged. This changes the evaluator fingerprint, rather than repairing a model’s submission.
