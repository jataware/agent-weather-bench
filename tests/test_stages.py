"""The per-stage rubric: schema, absolute and local verdicts, the invalid-upstream state and the rollup."""
import copy

import pytest

from assessment import stages
from assessment.outcomes import FAIL, PASS, UNRESOLVED, blocked, headline, outcome
from assessment.rubric import annotate, contract
from assessment.spec import Template

RESULTS = {"a": {}, "b": {}, "c": {"free": True}, "d": {"free": True}}


def _spec(**overrides):
    spec = {"results": RESULTS, "stages": [
        {"id": "first", "requirement": "Make a and b.", "source": "s", "results": ["a", "b"], "absolute": {"results": ["a", "b"]}},
        {"id": "second", "requirement": "Make c from a.", "source": "s", "results": ["c"], "absolute": {"checks": ["invariant.gate"]},
         "local": {"checks": ["invariant.from_own_a"]}, "upstream": ["first"], "weight": 3},
        {"id": "third", "requirement": "Make d from c.", "source": "s", "results": ["d"], "local": {"checks": ["invariant.d_identity"]},
         "upstream": ["second"], "review": ["interpretation.prose"]},
    ]}
    spec.update(overrides)
    return spec


def _checks(**states):
    return {name: outcome(state) if state != "blocked" else blocked("envelope", "unusable") for name, state in states.items()}


def test_every_stage_passes_when_its_verdicts_pass():
    checks = _checks(**{"invariant.gate": PASS, "invariant.from_own_a": PASS, "invariant.d_identity": PASS})
    profile, score = stages.evaluate(_spec(), checks, {"a", "b", "c", "d"}, lambda names: outcome(PASS, "agree"))
    assert [row["state"] for row in profile] == [PASS, PASS, PASS]
    assert score == {"passed": 3, "of": 3, "weighted_fraction": 1.0, "failed": [], "unresolved": []}
    assert checks["stage.second"]["absolute"]["state"] == PASS and checks["stage.second"]["local"]["checks"] == ["invariant.from_own_a"]
    assert checks["stage.first"]["local"] is None and checks["stage.third"]["absolute"] is None


def test_a_broken_upstream_group_fails_its_own_stage_and_leaves_the_local_verdict_downstream_unresolved():
    checks = _checks(**{"invariant.gate": PASS, "invariant.from_own_a": "blocked", "invariant.d_identity": PASS})
    profile, score = stages.evaluate(_spec(), checks, {"b", "c", "d"}, lambda names: outcome(PASS, "agree"))
    first, second, third = (checks[f"stage.{name}"] for name in ("first", "second", "third"))
    assert first["state"] == FAIL and first["blocked_by"] == "schema" and first["schema"]["unusable"] == ["a"]
    assert second["state"] == UNRESOLVED and second["reason"] == stages.INVALID_UPSTREAM
    assert second["local"]["reason"] == stages.INVALID_UPSTREAM and second["local"]["upstream_failed"] == ["first"]
    assert second["absolute"]["state"] == PASS, "the absolute verdict is judged from the controller's inputs and still runs"
    assert third["state"] == PASS, "the third stage's upstream (second) passed its schema"
    assert score["weighted_fraction"] == pytest.approx(1 / 5) and score["failed"] == ["first"] and score["unresolved"] == ["second"]


def test_a_failed_coverage_check_leaves_every_result_unusable():
    checks = _checks(**{"invariant.gate": PASS, "invariant.from_own_a": PASS, "invariant.d_identity": PASS})
    profile, score = stages.evaluate(_spec(), checks, {"a", "b", "c", "d"}, lambda names: outcome(PASS), coverage_failed="lat is wrong")
    assert all(row["state"] == FAIL and row["schema"] == FAIL for row in profile) and score["weighted_fraction"] == 0


def test_an_unresolved_absolute_verdict_with_a_failed_local_verdict_fails_the_stage():
    checks = _checks(**{"invariant.gate": PASS, "invariant.from_own_a": FAIL, "invariant.d_identity": PASS})
    checks["invariant.gate"] = outcome(UNRESOLVED, "open", "unknown_answer")
    profile, _ = stages.evaluate(_spec(), checks, {"a", "b", "c", "d"}, lambda names: outcome(UNRESOLVED, "no reading", "unknown_answer"))
    assert profile[0]["state"] == UNRESOLVED and checks["stage.first"]["reason"] == "unknown_answer"
    assert profile[1]["state"] == FAIL and "invariant.from_own_a" in checks["stage.second"]["local"]["detail"]


def test_a_stage_declares_no_verdict_or_a_free_result_for_reference_agreement_is_rejected():
    with pytest.raises(ValueError, match="declares no verdict"):
        stages.validate(_spec(stages=[{"id": "x", "requirement": "r", "source": "s", "results": ["a"]}]))
    with pytest.raises(ValueError, match="reference-matched"):
        stages.validate(_spec(stages=[{"id": "x", "requirement": "r", "source": "s", "results": ["c"], "absolute": {"results": ["c"]}}]))
    with pytest.raises(ValueError, match="declared before"):
        stages.validate(_spec(stages=[{"id": "x", "requirement": "r", "source": "s", "local": {"checks": ["invariant.k"]}, "upstream": ["y"]}]))
    with pytest.raises(ValueError, match="weight"):
        stages.validate(_spec(stages=[{"id": "x", "requirement": "r", "source": "s", "local": {"checks": ["invariant.k"]}, "weight": 0}]))
    stages.validate(_spec())


def test_the_outlook_contract_gates_completion_on_the_stage_rows_and_names_only_real_checks():
    template = Template("objective-seasonal-outlook")
    rubric = contract(template)
    rows = {row["id"]: row for row in rubric["instruments"]}
    assert [row["id"] for row in rubric["instruments"] if row["id"].startswith("stage.")] == \
        ["stage.acquire", "stage.prepare", "stage.wvg", "stage.ereg", "stage.cca", "stage.combine", "stage.verify", "stage.issue"]
    assert rows["stage.wvg"]["required_for"] == ["completion", "ranking"] and rows["variant"]["required_for"] == []
    assert rows["probe.held_out_year_isolation.wvg"]["decided_by"] == "rerun"
    assert rows["stage.issue"]["review"] == ["interpretation.bulletin_support", "interpretation.bulletin_uncertainty"]
    template.spec = copy.deepcopy(template.spec)
    template.spec["stages"][2]["local"]["checks"].append("invariant.typo")
    with pytest.raises(ValueError, match="no instrument"):
        contract(template)


def test_headline_takes_completion_from_the_stage_rows():
    template = Template("objective-seasonal-outlook")
    result = {"checks": {row["id"]: outcome(PASS) for row in contract(template)["instruments"] if row["id"] != "skill"}}
    result["checks"]["variant"] = outcome(UNRESOLVED, "no reading", "unknown_answer")
    result["checks"]["stage.wvg"] = outcome(FAIL, "leak")
    annotate(result, template, 1)
    headline(result)
    assert result["outcome"] == FAIL and result["unresolved_reasons"] == ["unknown_answer"]
    result["checks"]["stage.wvg"] = outcome(PASS)
    headline(result)
    assert result["outcome"] == PASS, "an unresolved whole-submission match does not block completion once every stage passes"
