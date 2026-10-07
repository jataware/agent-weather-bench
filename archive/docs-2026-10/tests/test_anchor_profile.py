"""Consequential false rejection/acceptance checks for the secondary study."""
import copy
import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]            # the repository root; this folder is an archive
HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("anchor_profile", HERE / "scripts/anchor_profile.py")
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


def feedback():
    return {"scope": "development_only", "max_submissions": 5,
            "requests": [{"query": 1, "status": "scored", "prediction_sha256": "a", "metrics": {"rmse_mm": 11.899738261744238}}],
            "final_score_exposed": False, "final_observations_exposed": False}


def test_unavailable_feedback_is_unknown_not_zero():
    assert study.feedback_boundary({"state": "unavailable", "requests": []})["state"] == "unresolved"
    assert study.feedback_boundary(None)["state"] == "unresolved"


@pytest.mark.parametrize("flag", ["final_score_exposed", "final_observations_exposed"])
def test_missing_final_boundary_flag_is_not_a_pass(flag):
    record = feedback()
    del record[flag]
    assert study.feedback_boundary(record)["state"] == "unresolved"
    record[flag] = True
    assert study.feedback_boundary(record)["state"] == "fail"


def test_invalid_requests_also_consume_allowance():
    record = feedback()
    record["requests"] += [{"status": "invalid"}] * 5
    assert study.feedback_boundary(record)["state"] == "fail"


def test_permitted_adaptive_feedback_is_not_a_failure():
    record = feedback()
    record["requests"] *= 5
    assert study.feedback_boundary(record)["state"] == "pass"


def test_reported_rounding_is_accepted_but_wrong_rmse_is_rejected():
    record = feedback()
    assert study.feedback_metric(record, {"development_skill_claim": "Queried once: RMSE 11.899738 mm"}, "a")["state"] == "pass"
    assert study.feedback_metric(record, {"development_skill_claim": {"rmse_mm": 11.0}}, "a")["state"] == "fail"
    assert study.feedback_metric(record, {"development_skill_claim": {"rmse_mm": float("nan")}}, "a")["state"] == "fail"


def test_prediction_reencoding_is_unknown_instead_of_rejected():
    assert study.feedback_metric(feedback(), {"development_skill_claim": {"rmse_mm": 11.899738261744238}}, "different encoding")["state"] == "unresolved"


def test_infrastructure_failure_does_not_become_scientific_failure():
    assert study.probe_state({"state": "fail", "exit_code": 1, "infrastructure_unavailable": True})["state"] == "unresolved"
    assert study.probe_state({"state": "fail", "exit_code": 1, "detail": "Incorrect scientific array"})["state"] == "fail"
    assert study.probe_state({"state": "pass"})["state"] == "unresolved"


def test_profile_preserves_each_original_parent_weight():
    profile = yaml.safe_load(study.PROFILE.read_text())
    originals = {task: yaml.safe_load((ROOT / "tasks" / task / "rubric.yaml").read_text()) for task in profile["tasks"]}
    study.validate_profile(profile, originals)
    wrong = copy.deepcopy(profile)
    wrong["tasks"]["cca-seasonal-reproduction"]["criteria"][0]["weight"] += 1
    with pytest.raises(AssertionError):
        study.validate_profile(wrong, originals)


def test_packet_keeps_source_complete_and_discloses_budget_omission(tmp_path):
    (tmp_path / "source.txt").write_text("source passage")
    (tmp_path / "large.py").write_text("x" * 100)
    criterion = {"id": "source", "question": "Faithful attribution?", "artifacts": ["source.txt", "large.py", "missing.txt"]}
    packet = study.expert_packet("opaque", "task", criterion, tmp_path, {"static": {"check_results": {}}}, budget=20)
    assert packet["files"]["source.txt"]["complete"] is True
    assert packet["files"]["large.py"]["included_characters"] == 0
    assert "not evidence" in packet["files"]["large.py"]["omission"]
    assert packet["files"]["missing.txt"]["available"] is False
    assert packet["human_label"] is None


def test_natural_station_success_and_fault_remain_separate():
    if not (ROOT / "var/runs" / study.RUNS[2] / "assessment.json").exists():
        pytest.skip("Retained local development run not installed")
    profile = yaml.safe_load(study.PROFILE.read_text())
    record, _ = study.assess_run(study.RUNS[2], profile)
    states = {c["id"]: c["state"] for c in record["criteria"]}
    assert states["observation_truth"] == states["station_interpolation"] == states["headline_metrics"] == "pass"
    assert states["fault_diagnostics"] == states["changed_input_correctness"] == "fail"
    assert states["original_replay"] == "pass"
    assert record["comparison_ready"] is False
    assert any(c["state"] == "fail" for c in record["validity"].values())


def test_correct_fixed_cca_receives_credit_when_nested_solution_fails():
    if not (ROOT / "var/runs" / study.RUNS[0] / "assessment.json").exists():
        pytest.skip("Retained local development run not installed")
    record, _ = study.assess_run(study.RUNS[0], yaml.safe_load(study.PROFILE.read_text()))
    states = {c["id"]: c["state"] for c in record["criteria"]}
    assert states["fixed_cca_predictions"] == "pass"
    assert states["nested_mode_selection"] == "fail"
    assert record["original_score_bounds"] == [0, 20]
    assert record["profile_score_bounds"][0] >= 10
