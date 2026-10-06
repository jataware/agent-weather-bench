# Local judge calibration preparation

The next deliverable should be a **local, blinded contrast-review bundle spanning all four existing tasks**, with independent reviews and a disagreement queue for Ezekiel. This is more useful than further judge-prompt polishing on seven ACMAD examples. Tonight can establish evidence coverage, executable defect detection and candidate judge failure modes. It cannot establish expert accuracy without reviewed labels or turn agreement between agents into scientific ground truth.

No API calls or external export are needed for preparation and subscription-agent review. The seven Anthropic packets remain blocked pending explicit export permission; their status is `var/calibration/judge-pilot/prepared-status.json`. The existing $3 reservation covers seven original calls, not an expanded paired experiment.

## Evidence already available

Paths below are relative to the repository. The companion `var/calibration/judge-coverage-inventory.json` records concrete sources and construction gaps. Existing cases have been inspected during task development; all belong in development.

| Task | Useful existing contrasts | What remains to construct |
|---|---|---|
| ACMAD objective | Six cases in `var/calibration/cases/20261005T115816-acmad/`: baseline, missing support, wrong weighting, unsupported skill, cached replay, missing manifest. Three natural attempts include genuine percentage-scale errors and a scientifically correct float32 alternative. | A complete independently implemented alternative; a source-attribution-only error; a bounded-trace contradiction. Forecast-target leakage is inapplicable to this combination-only task. |
| WVG definition audit | Three natural attempts in `var/calibration/wvg-natural-cohort.json`: correct scientific arrays with absent output-directory placeholder, or schema-valid replay that writes to a read-only path. One report overattributes standardization to the paper; this is a proposed expert concern, not a confirmed label. | Verified complete alternative; signed-gradient or geometry error; a controlled paper-versus-curator attribution pair with identical arrays; corrected exploration versus false final claim. Target leakage is inapplicable to this observed-index audit. |
| Seasonal calibration | `var/calibration/seasonal-natural-contrast-cases/`: thousandfold unit error, negative probabilities, full-fit resubstitution. Natural runs additionally expose full-training thresholds used for held-out verification, incomplete delivery and corrected acquisition failures. | A complete valid baseline and alternative; one isolated fold-preprocessing leak; a saved-state refitting defect; unsupported reliability/skill prose and a trace contradiction on an otherwise complete parent. Existing constructed copies inherit an unfinished parent. |
| Short-rains workflow | `var/calibration/short-rains-{baseline,outer-target-leak,cached-inference}/controller-validation-docker.json`: baseline passes; leaked workflow fails the temporal probe; cached inference fails changed-predictor prediction. Astra passes every controller probe. Long-output Fable has correct arrays with incomplete provenance/execution/handoff. | Independent complete alternative; isolated unit/calendar error; source-availability and retrospective-real-time claim pairs; trace contradiction and uncertainty overclaim. Negative nested-versus-fixed results already supply a positive control: honest lack of gain must not lose credit. |

`tests/test_disagreement_precision.py` and `tests/test_short_rains_workflow.py` also contain equivalence and representation checks. Unit tests are scorer coverage, not complete submissions or judge-calibration examples. Do not count them as task attempts.

## Distinguish an oracle from a proposed judgment

Store expectations outside the blinded packet. Each expectation names its criterion, evidence, allowed ratings and basis:

- **Operational oracle:** a recorded numerical failure; an actual replay failure; absence of required execution metadata; a measured perturbation violation. These can constrain relevant completion requirements without claiming all other scientific criteria fail.
- **Contract-backed contrast:** report text asserts observed skill without observations, or code explicitly copies finished arrays. The intended defect is inspectable, but useful correct content may justify partial credit. Record the permitted range rather than inventing an exact expert score.
- **Expert uncertainty:** adequacy of uncertainty assumptions, source interpretation, reliability diagnostics and scientific conclusions. Preserve candidate ratings, competing rationales and `human_label: null` until Ezekiel reviews them.

Static array agreement and successful unchanged-input replay do not establish recomputation. Passing a temporal probe excludes the particular tested dependence, not every possible leakage channel. Missing handoff does not erase independently demonstrated scientific success. A corrected exploratory failure must not become a final-workflow failure. If truncation prevents a decision, preserve uncertainty.

## A paired evidence experiment

Make fresh copies of each reviewable packet, retaining the same task prompt, criteria, artifacts, image and trusted controller checks. Condition A omits only `controller:tool_trace`; condition B includes the existing bounded trace and its omission markers. Calling A “artifact-only” is shorthand: both conditions retain controller evidence, including acquisition and execution checks. Removing those too would test a different intervention.

Randomize opaque packet IDs and review order; use fresh reviewer contexts and identical instructions. Keep model identity, costs, parent lineage and expectations out of reviewer packets. Reviewers must return criterion-level ratings, cited evidence and explicit uncertainty. Original packets, requests, frozen outputs and logs remain immutable. For synthetic report/code contrasts, label construction in the private manifest and never fabricate trusted execution events.

The seven existing packets are ACMAD-only and expose just `scientific_report` and `reusable_workflow`. Only p01, p04 and p07 have actual traces; paired review of the other four is a no-information control. Add natural WVG, seasonal and short-rains packets to exercise their different expert criteria. Preserve pipeline diagnostics on structurally invalid examples as a separate lane: ordinary `assess` skips paid judgment when basic validity fails.

Compare per-criterion changed decisions, cited contradictions found, unsupported full-credit ratings, correct alternatives rejected, abstentions, invalid response schemas and corrected exploratory errors penalized. Report denominators and task/parent groupings. Do not use a weighted overall score or agent agreement as a judge-accuracy estimate. Neil's substrate listing/reading/execution counts remain engagement evidence, not proof of understanding or a hidden scoring bonus.

## Development and check split

All current attempts, inspected fixtures, paper excerpts and their mutated siblings form the **development** set. Keep every common parent and its mutations together; splitting one fixture's easy error from its baseline leaks the solution into the check set.

Before further prompt tuning, freeze a new **check** set from newly completed parent workflows that reviewers have not inspected. Use distinct implementations and, where feasible, separate frozen data windows or source instances. Reserve at least one valid alternative and one important defect per relevant task, with siblings kept together. Their task methods still overlap with development: call this a disjoint case check, not an independent domain-generalization benchmark. A newly added task family can later provide a stronger transfer check. Do not inspect checks to tune the prompt; once a check informs development, retire it from checking and replace it.

## Reproduction and optimization need different judgments

A paper/method reproduction track judges scientific correctness against its declared contract. A subseasonal competition track first enforces information, reproducibility and validity gates, then ranks a declared forecasting metric under comparable search, compute and score-feedback budgets. A valid method with no improvement can be scientifically satisfactory while ranking poorly; judge prose cannot substitute for measured leaderboard skill.

Freeze a private final time period separately from public development feedback. Log every score query, candidate selection, consumed compute and retry, including failures. Historical public targets are not untouched simply because a controller withholds them from this run. Optimization-experiment validity is currently a coverage gap: construct tuning against the final period, repeated feedback-driven selection and unequal-budget contrasts before claiming a trustworthy optimization leaderboard.

## Concrete overnight output

Local preparation provides seven expanded packets under `var/calibration/judge-expanded/`, including six additional WVG, seasonal and short-rains cases and an unchanged ACMAD copy. The public four-case reviewer directory contains the pinned prompt, packets, figures and hashes; expectations and lineage remain outside it. The selected subset contains ACMAD numerical success, WVG broken replay, seasonal correct LOO predictions with incorrect verification labels, and short-rains numerical/execution success. No network export, paid calls, prompt changes or new lock were required.

Two fresh-context subscription helper reviewers completed eight responses on that subset. All pass the existing JSON/citation validator; three of 13 paired criterion ratings differ. The [review queue](../var/calibration/judge-local-review/README.md) includes a code-visibility misstatement, partial-credit versus uncertainty decisions, and shared packaging deductions. Large packets omit core workflow/model artifacts, although relevant bootstrap code remains visible inside one truncated file; evidence selection and criterion-specific truncation interpretation need attention before prompt tuning.

The reviewers are not the locked `auto-v1` model. No trace ablation or native autojudge inference was run, and these familiar cases remain development evidence with human labels unset. Paired artifact/controller versus trace review remains a next experiment. Ezekiel can review the consequential queue tomorrow rather than labeling everything tonight; validated expert judging remains later work.

## Implemented evidence selection correction

The pinned packet policy is now `declared-science-v2`. Its artifact text budget remains **90,000 decoded characters**, with the tool trace separately bounded at 18,000 serialized characters. Task contracts and controller records are separate evidence; this is not a 90,000-character limit on the entire JSON request. Selection still uses only the frozen submission inventory and never executes submission code.

Report, answer, execution declaration and handoff come first. Up to 60,000 characters of the existing total are reserved for declared replay/prediction entrypoints and fitted state, preventing oversized report or answer metadata from consuming all scientific evidence capacity. Entry-point/supporting code has a 48,000-character per-file cap; fitted text state has a 24,000-character cap. Source-passage filenames containing `literature`, `excerpt` or `paper-notes` precede provenance and supporting code. Provenance has a 6,000-character prefix cap; other text retains the 18,000-character cap. Ordering is deterministic, and roles denote declarations/filename classes rather than controller-certified relevance. Several large entrypoints can still exceed the global budget.

The execution declaration is parsed as bounded JSON only (65,536 bytes maximum). Paths must exactly match existing relative inventory entries; absolute paths, traversal, aliases and symlinks cannot introduce outside evidence. Every eligible text file records its hash, total/included/omitted characters, selection role, prefix range, cap and omission reason. Budget-exhausted files remain explicitly represented with empty text and `truncated: true`. PNG verification is unchanged. The full-credit validator continues to require a complete cited submission artifact, so a partial file never silently becomes a complete citation. Visible passages in a partial file may still support limited conclusions.

Optimization evidence now recognizes the `score_development` tool alongside execute/acquire. Bounded traces retain the submitted prediction filename, public query/remaining counts, development-only scope, prediction hash and existing aggregate metric stdout. `controller:feedback` retains only the public feedback-summary/request fields, excluding ledger snapshots, private errors, provider and cost metadata. Score feedback is evidence about the observed experiment, with no extra scoring bonus; trace omissions remain explicit.

The [same-submission comparison](../var/calibration/judge-packet-policy/comparison.json) uses the completed Astra short-rains run and its preserved original evaluation. Both policies include exactly 90,000 artifact characters. Previously omitted `workflow.py` and `model.json` now appear completely: 14,565 and 20,035 characters respectively. The 2,270-character literature note is also complete. `documentation.py` increases from 18,000 to 22,166 of 34,498 characters and remains explicitly partial; provenance decreases from 18,000 to 6,000 of 34,070. Report, answer, execution and handoff remain complete. Numeric inventories and other supporting artifacts still have omissions. This corrects a measured evidence-coverage defect without claiming that every scientific concern is now reviewable.

The fresh comparison packet, verified PNG and hashes are under `var/calibration/judge-packet-policy/`; frozen outputs and original packets are unchanged. Thirty-three targeted tests pass across packet, trace and existing harness checks. New regression checks exercise bulky report/provenance/inventory competition, declared scientific source/state inclusion, exact per-file and global limits, traversal/oversized/invalid manifests, complete-file citation restrictions, stable selection, PNG validity, trace omission and optimization-feedback identity boundaries. No inference calls, new ratings, human labels or judge-accuracy estimates were produced by this change. Root integration regenerates the evaluator lock only after all concurrent task changes finish.

## Completed task expansion and follow-up checks

Ten packages now validate, and eight additional real solver attempts cover all six
new tasks. The [development audit](overnight-development.md) separates numerical
science, delivery, replay and measured forecast performance. Natural monthly
calibration and station-verification errors broaden the defect corpus; valid
downscaling with negative skill supplies a consequential positive interpretation
case. These are inspected development parents, not independent expert labels.

A two-reviewer diagnostic check of the revised packet policy exposed a shared
error: an unavailable feedback ledger had been sanitized into an empty-looking
record, and both reviewers inferred zero requests. The controller now retains
the unavailable state and explicit unknown history, and the copied judge prompt
instructs reviewers to read that state. Original diagnostic reviews remain
preserved; the repair is not evidence of measured judge accuracy after correction.

Two fresh-context reviewers then reviewed new CCA and subseasonal parent packets
in opposite orders. Four responses validate; one of six criterion pairs differs.
The [new-parent queue](../var/calibration/judge-new-parent-review/README.md) records
the admissibility/evidence-omission disagreement and shared concern about reported
validation metrics. Source excerpts and fold/metric records still have coverage
gaps under the finite text budget. Those gaps must remain explicit rather than
become assertions that the implementation is scientifically wrong. These parents
are now development cases and need replacing for future check-set claims.

Final controller repairs sample adjacent tool request/result pairs together,
record source declaration coverage separately from stale file hashes, and provide
ungraded bounded array diagnostics even when metadata fail. The monthly trial
now exposes missing units and the 34.9691 mm production discrepancy together.
The full suite passes 261 tests; all ten frozen input/source manifests validate.
Original executed assessments retain their fingerprints. Final static overlays
and packet previews are separate evidence, with original execution hashes; no
extra Docker replay was run after disk pressure was reported.

Human labels, native locked-model judgment and a paired trace-ablation experiment
remain unfinished. Automatic approval review still blocks the Anthropic artifact
export pending explicit permission. No new paid calls were made. Next prioritize
Ezekiel's short consequential review queue and a fresh parent-level contrast set,
with complete method-source evidence, over another round of prompt polishing.
