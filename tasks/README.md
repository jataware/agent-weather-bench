# Three task packages for joint review

`review-0.2` incorporates [the three exported critiques](../docs/reviews/2026-10-02/response.md).
Seasonal calibration now includes agent acquisition from a source plan; its
normalized local inputs are controller development fixtures. Acquisition runtime
validation is pending. The rubrics have 6/4/4 scored scientific outcomes, with
unweighted validity requirements. All tasks use shared
[provenance](provenance-contract.md) and [command replay](replay-contract.md)
contracts rather than prescribed Python script filenames.

Open [the HTML review index](index.html) in a browser to inspect and critique each
package. Each standalone page includes the prompt, rubric, sources and reference
evidence, with general and per-check critique fields. Notes save in the browser
when local storage is available. Export Markdown to discuss the review, or JSON
to preserve and re-import it. Review notes do not edit package files or approve
an experiment. The pages contain public package metadata, not private reference arrays.

Regenerate the pages after changing a package with
`.venv/bin/python -m weatherbench tasks render`. The Markdown and YAML files remain the
source of truth; exports record their hashes so reviews identify the exact draft.

These are concrete development packages awaiting scientific review by Zeek and
Emmett. They are standalone tasks: sequence order and retained substrate are
defined in [the accretion experiment](../experiments/accretion-review.yaml).
The preparation tooling has no model client and never runs submitted code.

| Package | Scientific work | Main review question |
| --- | --- | --- |
| [Seasonal calibration](seasonal-calibration/prompt.md) | Process monthly ensembles and observations, validate a calibration, and deliver a saved prediction workflow | Are the validation evidence and required scientific checks sufficient while allowing different sound methods? |
| [ACMAD objective](acmad-objective/prompt.md) | Consolidate three component probability products, audit missing support, and test weighting sensitivity | Does this final operational step make a sufficiently substantial standalone task, and is the missing-component rule faithful? |
| [WVG definition audit](wvg-definition-audit/prompt.md) | Read the paper and implementation, recompute two predictor geometries, and explain discrepancies | Is this a useful first literature task, or should it await the author data and become a larger forecast-skill audit? |

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

`prepare` copies existing inputs and computes bounded independent reference
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
