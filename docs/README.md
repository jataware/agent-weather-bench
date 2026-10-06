# Agent Weather Bench documentation

This folder develops the benchmark proposal from the completed ACCORD pilot.
The implemented development tasks and scoring framework remain open to expert review.

- [Original proposal](proposal-original.md) preserves Zeek's supplied draft, with paragraph spacing normalized.
- [Review and framework design](benchmark-design.md) addresses the argument, evaluation contract, substrate experiments, cost, and accretion.
- [Proposed starting set of 25 tasks](task-set.md) consolidates the ten packaged tasks, the earlier weather-skills-bench cases and nine gap-filling additions into one list of task templates with two levels.
- [Proposed assessment format](assessment-format.md) defines one submission envelope, three assessment modes and seven check types, including conformance to WMO seasonal forecasting standards and narrow evidence-cited interpretation checks. It is a proposal and is not implemented.
- [Candidate task portfolio](task-portfolio.md) proposes twelve tasks spanning existing workflows, published outlooks, and literature claims, with explicit readiness requirements.
- [Source grounded shortlist](task-candidate-shortlist.md) audits nine new paper, repository and benchmark candidates, with inspected sources, data gaps and packaging priorities.
- [Week development plan](week-development-plan.md) targets ten validated examples and defines the autonomous preparation and quality requirements.
- [Overnight development audit](overnight-development.md) records the ten implemented tasks, actual new solver trials, concrete evaluator repairs and remaining calibration work.
- [Subseasonal leaderboard track](subseasonal-leaderboard-track.md) describes implemented bounded feedback and separate final scoring, plus proposed competition extensions.
- [Next frontier challenge](frontier-challenge-next.md) specifies stronger subseasonal baselines, full-grid support and sequential observation availability, with a small validated reference prototype and explicit remaining work.
- [Next judge calibration work](judge-calibration-next.md) maps four-task contrast coverage, provisional agent review and the remaining independent-label requirements.
- [Evaluation development plan](evaluation-development.md) maps task requirements to evidence, develops two candidate briefs, and calibrates every existing task using natural attempts, constructed cases and trace review.
- [Evaluator calibration](evaluator-calibration.md) records the precision policy, independent contrast tests and remaining human review.
- [Task audit results](task-audit-results.md) records twelve actual task attempts, frontier output-capacity limits, scientific defects, costs and the limits of the difficulty claim.
- [Short-rains task development](short-rains-task-development.md) records the real source repair, independent references, counterfactual probes and limits of the frontier difficulty claim.
- [Seasonal rubric proposal](seasonal-rubric-proposal.yaml) makes the existing Kenyan study-box experiment concrete as a rubric tree. Its weights and new evidence checks are proposed, not implemented or reviewed.
- [First task package review](task-package-review.md) introduces three concrete standalone packages, their local inputs and numerical checks, and the scientific decisions for joint review.
- [Interactive task review pages](../tasks/index.html) display each package with editable critique fields and Markdown/JSON export; open directly in a browser.
- [Response to the task critiques](reviews/2026-10-02/response.md) records the revised acquisition, provenance and simpler rubrics, and compares the seasonal draft with the completed pilot.
- [Task authoring](task-authoring.md) gives package files, data boundaries, and the current code registration points.
- [Internal setup](internal-setup.md) explains checkout checks, the separately shared task data, Docker builds, and pending review and license work.
- [README and brand preview](assets/brand/index.html) displays the public introduction, diagram, visual identity, and sharing assets offline.

The main accretion design now runs systems across standalone benchmark tasks with
retained/reset comparisons. Sequence order belongs to the experiment; the
portfolio's explicit follow-ups are optional complementary tests of targeted reuse.

The completed experiment is seasonal rainfall calibration in a Kenyan study box,
using the [archived smoke contract](../archive/pilot-2026-10-01/smoke/task.yaml)
and [revised protocol](../archive/pilot-2026-10-01/revision/PLAN.txt).
The six-week Kenya outlook is a separate archived candidate. Current task definitions
do not reinterpret historical results.

Use `./bench tasks list` to inspect current tasks without model calls.
The [harness guide](harness.md) describes system registration, adapters, run storage
and retained/reset task sequences. The [judge contract](judging.md) specifies
locked scoring, execution evidence, pending outcomes and retry records.
Historical code and commands are documented under [archive](../archive/README.md).
