# Agent Weather Bench documentation

This folder develops the benchmark proposal from the completed ACCORD pilot.
The proposed task set and scoring framework are for discussion and expert review.

- [Original proposal](proposal-original.md) preserves Zeek's supplied draft, with paragraph spacing normalized.
- [Review and framework design](benchmark-design.md) addresses the argument, evaluation contract, substrate experiments, cost, and accretion.
- [Candidate task portfolio](task-portfolio.md) proposes twelve tasks spanning existing workflows, published outlooks, and literature claims, with explicit readiness requirements.
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
