import copy
import json
from types import SimpleNamespace

import pytest

from assessment.judge import apply
from assessment.outcomes import headline, outcome
from assessment.rubric import annotate, contract, markdown
from assessment.spec import Template


@pytest.mark.parametrize("text", [None, "", "  \n"])
def test_missing_report_fails_the_envelope_even_when_prose_reviews_are_supplementary(tmp_path, monkeypatch, text):
    from assessment.assess import read_envelope
    monkeypatch.setattr("assessment.assess.read_results", lambda *_: ({"rain": [1]}, {}))
    (tmp_path / "answer.json").write_text(json.dumps({"run": {"argv": ["python", "solve.py", "{input_dir}", "{output_dir}"]}}))
    if text is not None:
        (tmp_path / "report.md").write_text(text)
    _, _, _, problems = read_envelope(SimpleNamespace(spec={"results": {}}), tmp_path)
    assert list(problems) == ["report.md"]
    (tmp_path / "report.md").write_text("Computed rainfall from the supplied data.")
    assert read_envelope(SimpleNamespace(spec={"results": {}}), tmp_path)[3] == {}


def test_supplementary_judge_can_fail_without_changing_completion_or_ranking():
    template = Template("weeks34-rainfall")
    result = {"checks": {row["id"]: {**outcome("pass"), **({"decided_by": "judge", "question": {"kind": "interpretation", "requirement": row["question"], "silence": "passes"}} if row["decided_by"] == "judge" else {})}
                         for row in contract(template)["instruments"] if row["id"] != "skill"}, "skill": {"final": {"rmse_mm": 2}}}
    annotate(result, template, 1)
    headline(result)
    def backend(questions, files):
        return ([{"id": name, "verdict": "fail", "basis": "quoted", "reason": "Contradiction", "citations": [{"source": "report.md", "quote": "contradiction"}]} for name in questions], {})
    apply(result, {"report.md": "contradiction"}, backend)
    assert result["outcome"] == result["ranking_outcome"] == "pass"
    assert result["advisory_outcome"] == result["all_checks_outcome"] == "fail"
    assert result["skill_valid_for_ranking"]
    assert result["checks"]["interpretation.generalization"]["implementation"].startswith("spec.yaml:")


def test_required_judge_gates_both_completion_and_ranking_and_survives_application():
    template = Template("seasonal-rainfall-calibration")
    result = {"checks": {row["id"]: outcome("pass") for row in contract(template)["instruments"] if row["id"] != "skill"}, "skill": {"new_years": {"rpss": 0}}}
    name = "process.plain_language_uncertainty"
    result["checks"][name] = {**outcome("unresolved", reason="judge_not_run"), "decided_by": "judge", "question": {"requirement": "State uncertainty", "silence": "fails"}}
    annotate(result, template, 1)
    headline(result)
    assert result["outcome"] == result["ranking_outcome"] == "unresolved"
    apply(result, {}, lambda *_: ([{"id": name, "verdict": "fail", "basis": "required_statement_absent", "reason": "Absent", "citations": []}], {}))
    assert result["outcome"] == result["ranking_outcome"] == "fail"
    assert result["checks"][name]["required_for"] == ["completion", "ranking"]
    assert not result["skill_valid_for_ranking"]


def test_rubric_exposes_owned_questions_reading_cost_and_every_implementation():
    rubric = contract(Template("kenya-forecast-revision"))
    rows = {row["id"]: row for row in rubric["instruments"]}
    assert rows["variant"]["readings"] == 64 and rows["variant"]["accepted_readings"] == 2
    assert all(row["implementation"] and row["question"] for row in rows.values())
    assert rows["interpretation.generalization"]["required_for"] == []
    assert "spec.yaml:judge_questions" in markdown(rubric)


def test_misspelled_policy_does_not_silently_drop_a_required_check():
    template = Template("kenya-forecast-revision")
    template.spec = copy.deepcopy(template.spec)
    template.spec["assessment_policy"]["completion"].append("probe.typo")
    with pytest.raises(ValueError, match="matches no instrument"):
        contract(template)
