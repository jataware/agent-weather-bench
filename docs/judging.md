# The locked autojudge

`judges/auto-v1.yaml`, `judges/system-v1.md` and `judges/auto-v1.lock.json` define
the operational assessment contract. The native model identifier and accounting
schedule are pinned from the completed pilot; the code does not choose a floating
latest model or fall back to another judge. Provider availability/rates should be
checked when selecting a new experiment configuration. The request/response contract is covered by tests. The development calibration
pilot also prepares blinded real and constructed cases; its call status and
operational expectations are recorded separately from human judgments.

## Four evidence layers

1. **Validity and numerical checks.** Deliverables, schemas, provenance records,
   retained-file hashes, source coverage and independently calculated scientific
   references. Detailed diagnostics support the task's grouped scientific outcomes.
2. **Trusted execution.** Offline replay from the submitted workflow in the pinned
   runtime. Seasonal inference receives only the forecast batch; observation-based
   skill is a separately reported controller outcome. Replay must match declared
   scientific arrays/answer fields, not optional session notes.
3. **Scientific judgment.** One evidence-citing model assessment of expert, mixed
   and execution outcomes. The packet includes task criteria, submission text/code,
   a verified figure, controller checks/execution evidence, and bounded scientific
   tool traces with explicit omissions. System, model,
   cost and parent labels are omitted. Library names inside artifacts can still
   reveal part of a substrate; complete blinding is not claimed.
4. **Information integrity.** Trusted sandbox configuration and artifact invariants.
   The scientific tool container has no network, host secrets, Docker socket,
   references or other run's controller files. Imported artifacts lack original
   boundary evidence and remain unresolved on integrity.

The controller, adapter integration and Docker daemon are trusted infrastructure.
Custom adapter authors must route model tool execution through the isolated
container. This is not an adversarial sandbox for arbitrary host adapter code.

## Structured ratings and completion

The judge returns exactly the supplied outcome IDs with `score: 0|1|2|null`, a
reason, evidence IDs and uncertainty. Unknown citations, boolean scores, omitted
criteria and invalid/incomplete JSON are rejected. Full credit requires a complete
cited submission artifact; figure-dependent criteria also require a verified
cited figure. Missing or truncated required evidence cannot be assumed correct.

The controller computes weighted score bounds. Unresolved outcomes contribute
zero to the lower bound and their full weight to the upper bound. Unavailable controller infrastructure leaves execution unresolved; scientific
command or output failures remain failures. Numeric failures
and failed replay force the relevant outcome to fail, irrespective of model prose.
Completion requires every required outcome at full credit, passing basic validity,
passing execution requirements and passing trusted integrity. Known failures are
reported as partial/failed; missing judgment or integrity is pending. Free-text
concerns are informational, rather than an additional hidden gate.

Correct negative results can complete. Forecast skill is reported continuously,
with inspected-development status; it never overrides method correctness or
becomes an arbitrary pass threshold. Fixtures are labelled and excluded from
capability claims. Development completion is distinct from task publication approval.

## Locking, retries and audit

```sh
./bench judge status
./bench judge packet RUN_ID
./bench assess RUN_ID
```

The lock fingerprints the judge prompt/configuration, evaluator/controller source,
task contracts/manifests, package configuration and dependency lock. Installed
controller dependencies must also match every pinned version. Drift stops
execution/assessment.
Changing grading means reviewing/versioning it and deliberately running
`./bench judge lock`; it does not change existing raw responses or assessments.
Run reports include fingerprints so scores from different policies are identifiable.

The judge makes one call with no automatic retry. It reserves the next call against
configured token/cost limits. Raw responses, packets, ratings and usage are retained.
Structurally invalid submissions are assessed without paying for model judgment.
Missing credentials or invalid responses leave expert evidence pending and record
the error. After fixing setup, `assess RUN_ID --retry` explicitly creates another
record; all previous attempts and their usage remain available.

The locked judge is a reproducible operational procedure, not a claim of perfect
scientific judgment. Domain-reviewed task definitions, scorer diagnostics and
human audits of borderline or disputed ratings remain necessary release work.
