"""The directions ladder cuts what the agent is told and leaves the task, the grader and the reference alone."""
import pytest

from assessment.directions import apply, drop_sections, rungs
from assessment.spec import Template

TEMPLATE = "objective-seasonal-outlook"


def _texts():
    template = Template(TEMPLATE)
    params = template.instance("gha--mam-2015")
    return template.brief(params), (template.folder / "practice.md").read_text()


def test_the_ladder_has_four_rungs_and_full_changes_nothing():
    assert rungs(TEMPLATE) == ["full", "no-streams", "brief-only", "minimal"]
    brief, practice = _texts()
    assert apply(TEMPLATE, "full", brief, practice) == (brief, practice)


def test_no_streams_drops_exactly_the_three_stream_sections():
    brief, practice = _texts()
    cut_brief, cut = apply(TEMPLATE, "no-streams", brief, practice)
    assert cut_brief == brief
    for title in ("## Stream 1: WVG", "## Stream 2: eReg", "## Stream 3: CCA"):
        assert title in practice and title not in cut
    for title in ("## Inputs", "## Categories", "## Combination, verification and issue"):
        assert title in cut
    assert "logistic regression" not in cut and "canonical correlation" not in cut
    assert "Unsupported cells" in cut


def test_brief_only_withholds_the_practice_sheet_and_the_pointer_to_it():
    brief, practice = _texts()
    cut_brief, cut = apply(TEMPLATE, "brief-only", brief, practice)
    assert cut is None
    assert "practice.md" not in cut_brief and "three-stream practice" in cut_brief
    assert "results.zarr" in cut_brief


def test_minimal_also_drops_the_stream_list_and_the_leave_one_year_out_rule():
    brief, practice = _texts()
    cut_brief, cut = apply(TEMPLATE, "minimal", brief, practice)
    assert cut is None
    assert "three-stream practice" not in cut_brief and "Western-V-Gradient" not in cut_brief
    assert "must be made as if" not in cut_brief
    assert "results.zarr" in cut_brief and "wvg_hindcast_probability" in cut_brief


def test_unknown_rungs_and_stale_edits_fail_loudly():
    brief, practice = _texts()
    with pytest.raises(ValueError, match="no directions rung"):
        apply(TEMPLATE, "none", brief, practice)
    with pytest.raises(ValueError, match="no longer contains"):
        apply(TEMPLATE, "brief-only", "a brief without the pointer", practice)
    with pytest.raises(ValueError, match="no section titled"):
        drop_sections("## A\nx\n## B\ny\n", ["C"])
    assert drop_sections("intro\n## A\nx\n## B\ny\n", ["A"]) == "intro\n## B\ny\n"
