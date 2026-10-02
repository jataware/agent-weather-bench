# WVG definition audit review

Review the [prompt](prompt.md), [rubric](rubric.yaml), and [input manifest](input-manifest.json).

## Changes after your critique

Four scored outcomes replace twelve leaves: index reconstruction, comparison,
scientific interpretation and reusable workflow. Box/composite means,
standardization and gradient checks support one reconstruction outcome. File and
schema validity, source coverage and structured provenance are prerequisites.
Replay accepts a declared CLI or other supported command rather than requiring
a Python script.

The scientific topic and controlled geometry comparison are retained. Real ERSST
data support the reference; independent NumPy/xarray calculations agree. The
shorter baseline, equal-box compositing and weighting rules remain curator choices.
Matching the reference establishes neither forecast skill nor exact published
index reconstruction.

## Decisions still open

- Confirm caption-derived geometry, inherited units/provenance and equal-box compositing with domain reviewers.
- Supply approved frozen literature context before a controlled run.
- Obtain the author workbook before adding a distinct predictability audit; previous download failures remain unresolved.
- Review weights and complete clean replay/expert-evidence adapters.

Your [original critique](../../docs/reviews/2026-10-02/wvg-definition-audit-critique.md)
and [the revision response](../../docs/reviews/2026-10-02/response.md) are retained.
Scientific, scoring and redistribution approval remain pending. No agent attempt
was launched for this revision.
