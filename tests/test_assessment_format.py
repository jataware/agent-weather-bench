"""The generic assessment format (docs/assessment-format.md) and its first template."""
import importlib.util
import json

import numpy as np
import pytest

from assessment.assess import assess
from assessment.compare import EnvelopeError, compare, normalise
from assessment.execute import Local, valid_argv
from assessment.judge import interpret, validate_verdict
from assessment.outcomes import FAIL, PASS, UNRESOLVED, combine, outcome
from assessment.spec import ROOT, Template
from assessment.variant import decide, table

KENYA = "kenya-forecast-revision"
needs_data = pytest.mark.skipif(not (ROOT / "var/private/templates" / KENYA / "stores").is_dir(),
                                reason="Private template data missing; run: python -m assessment prepare kenya-forecast-revision --source DIR")
RESULTS = {"latitude": {"kind": "coordinate", "tolerance": {"atol": 1e-6}},
           "field": {"dims": ["period", "latitude"], "tolerance": {"atol": 1e-3, "rtol": 0}}}


# ---- outcomes: three states, never merged ---------------------------------------

def test_outcomes_keep_unresolved_apart_from_failure():
    assert combine([outcome(PASS), outcome(UNRESOLVED, reason="judge_not_run")]) == UNRESOLVED
    assert combine([outcome(UNRESOLVED, reason="missing_evidence"), outcome(FAIL, "wrong number")]) == FAIL
    assert combine([outcome(PASS), outcome(PASS, reason="ambiguous_variant")]) == PASS
    with pytest.raises(ValueError):
        outcome(UNRESOLVED, "no reason given")
    with pytest.raises(ValueError):
        outcome(FAIL, "a failure is demonstrated, not unexplained", reason="missing_evidence")


# ---- comparison is by coordinate label ------------------------------------------

def test_arrays_are_compared_by_coordinate_not_storage_order():
    reference = {"latitude": np.array([3.0, 1.5, 0.0]), "field": np.array([[1.0, 2.0, 3.0]])}
    flipped = normalise(RESULTS, {"latitude": [0.0, 1.5, 3.0], "field": [[3.0, 2.0, 1.0]]})
    assert compare(RESULTS, flipped, reference)[0]
    mislabelled = normalise(RESULTS, {"latitude": [0.0, 1.5, 3.0], "field": [[1.0, 2.0, 3.0]]})
    assert not compare(RESULTS, mislabelled, reference)[0]
    other_cells = normalise(RESULTS, {"latitude": [3.0, 1.5], "field": [[1.0, 2.0]]})
    assert not compare(RESULTS, other_cells, reference)[0]


def test_tolerance_is_absolute_and_small():
    reference = {"latitude": np.array([0.0]), "field": np.array([[10.0]])}
    assert compare(RESULTS, normalise(RESULTS, {"latitude": [0.0], "field": [[10.0009]]}), reference)[0]
    assert not compare(RESULTS, normalise(RESULTS, {"latitude": [0.0], "field": [[10.002]]}), reference)[0]


@pytest.mark.parametrize("raw", [None, {"latitude": [0.0]}, {"latitude": [0.0], "field": [1.0]},
                                 {"latitude": [0.0], "field": [[float("nan")]]}, {"latitude": [0.0, 1.0], "field": [[1.0]]},
                                 {"latitude": [0.0], "field": [["a"]]}])
def test_unusable_results_are_an_envelope_error(raw):
    with pytest.raises(EnvelopeError):
        normalise(RESULTS, raw)


def test_run_command_needs_both_placeholders():
    assert valid_argv(["python", "solve.py", "--inputs", "{input_dir}", "--output", "{output_dir}"])
    assert not valid_argv(["python", "solve.py", "--output", "{output_dir}"])
    assert not valid_argv("python solve.py {input_dir} {output_dir}")


# ---- judge verdicts are void unless their quotes are exact -----------------------

def test_no_judge_leaves_obligations_unresolved_not_failed():
    rows = interpret(["generalization"], {"report.md": "text"})
    assert rows["generalization"]["state"] == UNRESOLVED and rows["generalization"]["reason"] == "judge_not_run"


def test_inexact_quote_voids_the_verdict():
    files = {"report.md": "The newer forecast is wetter in week one."}
    exact = {"verdict": "pass", "reason": "bounded claim", "citations": [{"source": "report.md", "quote": "wetter in week one"}]}
    assert validate_verdict(exact, files)["state"] == PASS
    inexact = {**exact, "citations": [{"source": "report.md", "quote": "wetter in week 1"}]}
    assert validate_verdict(inexact, files)["reason"] == "invalid_citation"
    one_sided = {"verdict": "fail", "reason": "overclaim", "citations": [{"source": "report.md", "quote": "wetter in week one"}]}
    assert validate_verdict(one_sided, files)["reason"] == "invalid_citation"


# ---- the Kenya template ---------------------------------------------------------

@pytest.fixture(scope="module")
def kenya():
    return Template(KENYA)


@pytest.fixture(scope="module")
def controls(kenya):
    module = importlib.util.spec_from_file_location("kenya_controls", kenya.folder / "controls/build.py")
    loaded = importlib.util.module_from_spec(module)
    module.loader.exec_module(loaded)
    return loaded


def test_spec_is_well_formed(kenya):
    assert kenya.spec["mode"] == "product" and len(kenya.combinations()) == 64
    accepted = [c for c in kenya.combinations() if not kenya.pitfalls_in(c)]
    assert {c["negative_increments"] for c in accepted} == {"clipped", "unclipped"} and len(accepted) == 2
    assert kenya.spec["public_conventions"] == []          # naming conventions to the agent would reveal the pitfalls
    assert len(kenya.hooks.candidate_instances()) == 48
    for params in kenya.development_instances():
        assert len(kenya.brief(params).split()) <= 150


@needs_data
def test_two_reference_implementations_agree(kenya, tmp_path):
    params = kenya.instance("service-area--weeks-1-2")
    kenya.hooks.stage_inputs(kenya.private, params, tmp_path / "inputs")
    for combination in kenya.combinations():
        a, b = (f(tmp_path / "inputs", params, combination) for f in (kenya.hooks.reference, kenya.hooks.independent))
        assert all(a[name].shape == b[name].shape and np.max(np.abs(a[name] - b[name])) < 1e-9 for name in a)
    assert all(row["passed"] for row in kenya.hooks.regression_checks(tmp_path / "inputs"))


@needs_data
def test_changed_data_alters_every_reading(kenya, tmp_path):
    params = kenya.instance("central--weeks-2-3")
    for name in ("original", "changed"):
        kenya.hooks.stage_inputs(kenya.private, params, tmp_path / name)
    kenya.hooks.perturb_inputs(tmp_path / "changed", 7)
    before, after = table(kenya, tmp_path / "original", params), table(kenya, tmp_path / "changed", params)
    assert all(not compare(kenya.spec["results"], y[1], x[1])[0] for x, y in zip(before, after))
    clipped, unclipped = (next(r for c, r, _ in after if not kenya.pitfalls_in(c) and c["negative_increments"] == v) for v in ("clipped", "unclipped"))
    assert not compare(kenya.spec["results"], clipped, unclipped)[0]     # the injected dips separate the two accepted readings


def _assess(kenya, controls, name, instance, tmp_path):
    params = kenya.instance(instance)
    kenya.hooks.stage_inputs(kenya.private, params, tmp_path / "inputs")
    submission = controls.build(name, tmp_path / "inputs", params, tmp_path / "submission")
    return assess(kenya, params, submission, Local(), tmp_path / "work")


@needs_data
def test_correct_solution_passes_and_judge_checks_stay_unresolved(kenya, controls, tmp_path):
    result = _assess(kenya, controls, "correct", "service-area--weeks-1-2", tmp_path)
    assert result["computed_outcome"] == PASS and result["outcome"] == UNRESOLVED
    assert result["unresolved_reasons"] == ["judge_not_run"]
    assert result["matched_conventions"]["negative_increments"] == ["clipped"]      # settled by the changed-data probe


@needs_data
def test_pitfall_is_named(kenya, controls, tmp_path):
    result = _assess(kenya, controls, "pitfall_same_lead", "service-area--weeks-1-2", tmp_path)
    assert result["checks"]["variant"]["state"] == FAIL and result["checks"]["variant"]["pitfalls_certain"] == ["same_lead"]
    assert all(result["checks"][f"probe.{name}"]["state"] == PASS for name in ("replay", "changed_data", "changed_instance"))


@needs_data
def test_coinciding_pitfall_is_separated_by_the_changed_instance_probe(kenya, controls, tmp_path):
    """On this instance weighted and unweighted means agree within tolerance, so the numbers alone cannot tell."""
    params = kenya.instance("central--weeks-1-2")
    kenya.hooks.stage_inputs(kenya.private, params, tmp_path / "inputs")
    rows = table(kenya, tmp_path / "inputs", params)
    pair = [i for i, (c, _, _) in enumerate(rows) if c["area_weighting"] in ("cos_latitude", "unweighted")
            and not [p for p in kenya.pitfalls_in(c) if p != "unweighted"] and c["negative_increments"] == "clipped"]
    assert decide(kenya, rows, pair)["reason"] == "ambiguous_variant"
    for name, state in (("pitfall_unweighted", FAIL), ("correct", PASS)):
        submission = controls.build(name, tmp_path / "inputs", params, tmp_path / name / "submission")
        result = assess(kenya, params, submission, Local(), tmp_path / name / "work")
        assert result["first_match_conventions"]["area_weighting"] == ["cos_latitude", "unweighted"]
        assert result["checks"]["variant"]["state"] == state
        assert result["checks"]["probe.changed_instance"]["chosen_to_separate_accepted_from_pitfall"]
    assert result["matched_conventions"]["area_weighting"] == ["cos_latitude"]


@needs_data
def test_cached_answer_passes_replay_and_fails_changed_inputs(kenya, controls, tmp_path):
    result = _assess(kenya, controls, "cached_output", "service-area--weeks-1-2", tmp_path)
    states = {name: row["state"] for name, row in result["checks"].items()}
    assert states["variant"] == PASS and states["probe.replay"] == PASS
    assert states["probe.changed_data"] == FAIL and states["probe.changed_instance"] == FAIL


@needs_data
def test_missing_answer_fails_the_envelope_and_nothing_else_is_guessed(kenya, controls, tmp_path):
    result = _assess(kenya, controls, "no_answer", "service-area--weeks-1-2", tmp_path)
    assert result["checks"]["envelope"]["state"] == FAIL and result["computed_outcome"] == FAIL
    assert result["checks"]["variant"]["reason"] == "not_assessed"


# ---- string coordinates and coverage (outcome mode has no reference answer) ---------

FORECAST = {"issue": {"kind": "coordinate", "dtype": "string"}, "cell": {"kind": "coordinate", "tolerance": {"atol": 0}},
            "rain_mm": {"dims": ["issue", "cell"], "tolerance": {"atol": 1e-4, "rtol": 0}}}


def test_forecast_is_aligned_to_the_required_cases_by_label():
    from assessment.compare import align
    frame = {"issue": np.array(["2020-01-05", "2020-01-12"]), "cell": np.array([0.0, 1.0])}
    shuffled = normalise(FORECAST, {"issue": ["2020-01-12", "2020-01-05"], "cell": [1, 0], "rain_mm": [[4.0, 3.0], [2.0, 1.0]]})
    assert align(FORECAST, shuffled, frame)["rain_mm"].tolist() == [[1.0, 2.0], [3.0, 4.0]]
    for issues in (["2020-01-05"], ["2020-01-05", "2020-01-19"]):
        short = {"issue": issues, "cell": [0, 1], "rain_mm": [[1.0, 2.0]] * len(issues)}
        with pytest.raises(EnvelopeError):
            align(FORECAST, normalise(FORECAST, short), frame)


# ---- development feedback for Level 2 --------------------------------------------

def test_feedback_counts_every_request_and_never_returns_private_errors(tmp_path):
    from assessment.feedback import DevelopmentFeedback
    (tmp_path / "work/submission").mkdir(parents=True)
    (tmp_path / "work/submission/good.json").write_text('{"value": 2}')
    (tmp_path / "work/submission/bad.json").write_text("not json")

    def score(answer):
        if answer.get("value") != 2:
            raise ValueError("withheld target is 17.5 mm")
        return {"rmse_mm": 1.5}
    feedback = DevelopmentFeedback(tmp_path / "work", tmp_path / "controller", score, max_submissions=3)
    assert json.loads(feedback.query("good.json")["stdout"]) == {"rmse_mm": 1.5}
    for name in ("bad.json", "../escape.json"):
        reply = feedback.query(name)
        assert reply["exit_code"] == 1 and "17.5" not in reply["stderr"]
    denied = feedback.query("good.json")
    assert denied["exit_code"] == 1 and denied["feedback_remaining"] == 0
    summary = feedback.public_summary()
    assert [row["status"] for row in summary["requests"]] == ["scored", "failed", "failed"] and summary["limit_denials"] == 1
    assert "private_error" not in json.dumps(summary) and not summary["final_score_exposed"]


# ---- the weeks 3-4 rainfall template (outcome mode, two levels) --------------------

WEEKS = "weeks34-rainfall"
needs_weeks = pytest.mark.skipif(not (ROOT / "var/private/templates" / WEEKS / "source-subset.nc").is_file(),
                                 reason="Private template data missing; run: python -m assessment prepare weeks34-rainfall")


@pytest.fixture(scope="module")
def weeks():
    return Template(WEEKS)


@pytest.fixture(scope="module")
def weeks_controls(weeks):
    module = importlib.util.spec_from_file_location("weeks_controls", weeks.folder / "controls/build.py")
    loaded = importlib.util.module_from_spec(module)
    module.loader.exec_module(loaded)
    return loaded


def test_outcome_spec_has_no_reference_answer_and_two_levels(weeks):
    assert weeks.spec["mode"] == "outcome" and weeks.combinations() == [{}] and not hasattr(weeks.hooks, "reference")
    assert weeks.spec["level2"]["feedback"]["max_submissions"] == 5
    params = weeks.development_instances()[0]
    assert len(weeks.brief(params).split()) <= 150
    assert "score_development" in weeks.brief(params, level=2) and "score_development" not in weeks.brief(params)


@pytest.mark.parametrize("template_name, systems", [(KENYA, ["kenya-revision-fixture"]), (WEEKS, ["weeks34-fixture", "weeks34-level2-fixture"]),
                                                    ("seasonal-rainfall-calibration", ["seasonal-calibration-fixture"])])
def test_certification_and_fixtures_are_current(template_name, systems):
    template = Template(template_name)
    record = json.loads((template.folder / "certification.json").read_text())
    assert record["fingerprint"] == template.fingerprint(), f"Rerun `python -m assessment certify {template_name}`"
    assert record["automatic_tests_passed"] and record["certified"] is False
    for system in systems:
        assert (ROOT / "systems" / system / "solve.py").read_bytes() == (template.folder / "controls/solve.py").read_bytes()


@needs_weeks
def test_two_scoring_implementations_agree_and_match_the_earlier_task(weeks, tmp_path):
    params = weeks.instance("final-2018-2021--all-cells")
    for which, rmse in (("raw_model", 14.8901), ("climatology", 14.2815)):       # the values recorded for the packaged task
        forecast = weeks.hooks.baseline_results(weeks.private, params, which)
        a, b = weeks.hooks.score(forecast, params, weeks.private), weeks.hooks.independent_score(forecast, params, weeks.private)
        assert abs(a["rmse_mm"] - b["rmse_mm"]) < 1e-9 and round(a["rmse_mm"], 4) == rmse
    assert all(row["passed"] for row in weeks.hooks.regression_checks(tmp_path))


def _assess_weeks(weeks, weeks_controls, name, tmp_path, instance="final-2015-2017--all-cells"):
    params, control = weeks.instance(instance), weeks_controls.CONTROLS[name]
    weeks.hooks.stage_inputs(weeks.private, params, tmp_path / "inputs")
    submission = weeks_controls.build(name, tmp_path / "inputs", params, tmp_path / "submission")
    requests = control.get("feedback_requests")
    feedback = None if requests is None else {"requests": [{"query": i + 1} for i in range(requests)], "limit_denials": 0}
    return assess(weeks, params, submission, Local(), tmp_path / "work", level=control.get("level", 1), feedback=feedback)


@needs_weeks
def test_any_valid_method_passes_and_is_scored(weeks, weeks_controls, tmp_path):
    result = _assess_weeks(weeks, weeks_controls, "valid_climatology", tmp_path)
    assert result["computed_outcome"] == PASS and result["skill_valid_for_ranking"]
    assert abs(result["skill"]["final"]["skill_vs_climatology"]) < 1e-9          # it is the climatology baseline
    assert result["checks"]["probe.responds_to_inputs"]["responds_to"] == ["training_targets"]


@needs_weeks
def test_forecast_that_uses_later_information_fails_only_the_causality_probe(weeks, weeks_controls, tmp_path):
    result = _assess_weeks(weeks, weeks_controls, "uses_later_forecasts", tmp_path)
    failed = [name for name, row in result["checks"].items() if row["state"] == FAIL]
    assert failed == ["probe.no_future_information"] and not result["skill_valid_for_ranking"]
    assert result["skill"]["final"]["rmse_mm"] > 0                               # the score is still reported, beside the failure


@needs_weeks
def test_unit_error_and_missing_cases_are_caught_without_a_reference(weeks, weeks_controls, tmp_path):
    scaled = _assess_weeks(weeks, weeks_controls, "multiplied_by_14", tmp_path / "a")
    assert scaled["checks"]["invariant.magnitude_of_a_14_day_total"]["state"] == FAIL
    short = _assess_weeks(weeks, weeks_controls, "missing_cases", tmp_path / "b")
    assert short["checks"]["coverage"]["state"] == FAIL and short["checks"]["probe.replay"]["reason"] == "not_assessed"
    assert "skill" not in short


@needs_weeks
def test_level2_claim_must_equal_the_controller_score(weeks, weeks_controls, tmp_path):
    honest = _assess_weeks(weeks, weeks_controls, "level2_true_score", tmp_path / "a")
    assert honest["level"] == 2 and honest["computed_outcome"] == PASS and honest["checks"]["feedback.limit"]["requests"] == 2
    inflated = _assess_weeks(weeks, weeks_controls, "level2_overclaimed_score", tmp_path / "b")
    assert inflated["checks"]["claim.development_rmse_mm"]["state"] == FAIL
    assert inflated["skill"]["final"] == honest["skill"]["final"]                # a false claim does not change the measured skill


# ---- the seasonal rainfall calibration template (process mode) ----------------------

SEASONAL = "seasonal-rainfall-calibration"
needs_seasonal = pytest.mark.skipif(not (ROOT / "var/private/templates" / SEASONAL / "forecast-development.nc").is_file(),
                                    reason="Private template data missing; run: python -m assessment prepare seasonal-rainfall-calibration")


@pytest.fixture(scope="module")
def seasonal():
    return Template(SEASONAL)


@pytest.fixture(scope="module")
def seasonal_controls(seasonal):
    module = importlib.util.spec_from_file_location("seasonal_controls", seasonal.folder / "controls/build.py")
    loaded = importlib.util.module_from_spec(module)
    module.loader.exec_module(loaded)
    return loaded


def test_process_spec_follows_the_standards_checklist(seasonal):
    import yaml
    checklist = yaml.safe_load((ROOT / "standards" / seasonal.spec["standard"] / "checklist.yaml").read_text())
    assert checklist["status"] == "draft_from_secondary_source"            # no domain scientist has signed it off
    assert {step["id"] for step in seasonal.spec["process"]} == {step["id"] for step in checklist["steps"]}
    assert set(seasonal.matched()) & {"hindcast_probability", "forecast_probability"} == set()   # any sound calibration is acceptable
    assert len(seasonal.brief(seasonal.development_instances()[0]).split()) <= 150


def _assess_seasonal(seasonal, seasonal_controls, name, tmp_path, instance="train-1993-2002--new-2003-2004--all-cells"):
    params = seasonal.instance(instance)
    seasonal.hooks.stage_inputs(seasonal.private, params, tmp_path / "inputs")
    submission = seasonal_controls.build(name, tmp_path / "inputs", params, tmp_path / "submission")
    return assess(seasonal, params, submission, Local(), tmp_path / "work")


@needs_seasonal
def test_seasonal_reference_implementations_agree(seasonal, tmp_path):
    params = seasonal.instance("train-1993-2000--new-2001-2002--southern-rows")
    seasonal.hooks.stage_inputs(seasonal.private, params, tmp_path / "inputs")
    given = seasonal.hooks.example_free_results(tmp_path / "inputs", params)
    for combination in seasonal.combinations():
        a, b = (f(tmp_path / "inputs", params, combination, given) for f in (seasonal.hooks.reference, seasonal.hooks.independent))
        assert set(a) == set(b) and all(np.max(np.abs(a[name] - b[name])) < 1e-9 for name in a)
    assert all(row["passed"] for row in seasonal.hooks.regression_checks(tmp_path))


@needs_seasonal
def test_conformant_solution_passes_every_computed_step(seasonal, seasonal_controls, tmp_path):
    result = _assess_seasonal(seasonal, seasonal_controls, "correct", tmp_path)
    steps = {name[8:]: row for name, row in result["checks"].items() if name.startswith("process.")}
    judged = {name for name, row in steps.items() if row.get("decided_by") == "judge"}
    assert judged == {"documented_calibration", "documented_cross_validation", "plain_language_uncertainty"}
    assert all(row["state"] == PASS for name, row in steps.items() if name not in judged)
    assert steps["documented_calibration"]["pointer"] == {"file": "solve.py", "symbol": "def calibrate"}
    assert result["computed_outcome"] == PASS and result["outcome"] == UNRESOLVED and result["unresolved_reasons"] == ["judge_not_run"]
    assert steps["model_forecast_prepared"]["conventions_that_matter"] == ["month_lengths"]


@needs_seasonal
def test_skipped_cross_validation_fails_its_own_step_only(seasonal, seasonal_controls, tmp_path):
    result = _assess_seasonal(seasonal, seasonal_controls, "skipped_cross_validation", tmp_path)
    failed = sorted(name for name, row in result["checks"].items() if row["state"] == FAIL)
    assert failed == ["probe.held_out_year_isolation", "process.cross_validated"]
    assert result["checks"]["process.cross_validated"]["source"] == "practice 5"


@needs_seasonal
def test_valid_negative_result_conforms(seasonal, seasonal_controls, tmp_path):
    """A climatological forecast scores zero under every reading; its observed categories still show the boundaries were held out."""
    result = _assess_seasonal(seasonal, seasonal_controls, "accepted_climatological_forecast", tmp_path)
    assert result["computed_outcome"] == PASS and abs(result["skill"]["new_years"]["rpss"]) < 1e-12
    assert result["matched_conventions"]["category_thresholds"] == ["leave_one_out"]


@needs_seasonal
def test_missing_or_false_method_pointer_is_unresolved_not_failed(seasonal, seasonal_controls, tmp_path):
    missing = _assess_seasonal(seasonal, seasonal_controls, "no_method_statement", tmp_path / "a")
    false = _assess_seasonal(seasonal, seasonal_controls, "false_method_pointer", tmp_path / "b")
    for result in (missing, false):
        row = result["checks"]["process.documented_calibration"]
        assert row["state"] == UNRESOLVED and row["reason"] == "missing_evidence" and row.get("decided_by") != "judge"
        assert result["computed_outcome"] == UNRESOLVED and not [n for n, r in result["checks"].items() if r["state"] == FAIL]


# ---- substrate use: the original path monitor plus library imports ------------------

def test_library_imports_are_recorded_beside_the_original_monitor(tmp_path):
    from assessment.substrate import substrate_record
    from weatherbench.substrate_use import substrate_use
    run = tmp_path / "run"
    (run / "logs").mkdir(parents=True)
    (run / "frozen").mkdir()
    commands = ["ls /substrate/skills", "python -c 'import numpy; from africas2s.calibration import fit'", "cat /substrate/skills/START.md",
                "python /work/submission/solve.py", "python - <<EOF\nimport acmaddl_extra\nEOF"]
    lines = []
    for number, command in enumerate(commands):
        lines.append(json.dumps({"type": "adapter", "event": {"type": "execute", "command": command}}))
        lines.append(json.dumps({"type": "tool_result", "exit_code": 0, "seconds": 0.1}))
    (run / "logs/events.jsonl").write_text("\n".join(lines) + "\n")
    (run / "frozen/solve.py").write_text("import xarray as xr\nimport acmaddl\n")
    (run / "frozen/notes.md").write_text("we could import africas2s here\n")
    record = substrate_record(run, {"substrate": {"paths": [], "libraries": ["africas2s", "acmaddl", "rosetta"]}})
    assert record["mounted_files"] == substrate_use(run) and record["mounted_files"]["read"] == 1 and record["mounted_files"]["listed"] == 1
    assert record["libraries"]["africas2s"] == {"commands_importing": 1, "first_step": 2, "submitted_files_importing": [], "used": True}
    assert record["libraries"]["acmaddl"]["submitted_files_importing"] == ["solve.py"] and record["libraries"]["acmaddl"]["commands_importing"] == 0
    assert record["libraries"]["rosetta"]["used"] is False
    assert substrate_record(run, {"substrate": {"paths": []}})["libraries"] == {}
    with pytest.raises(ValueError):
        substrate_record(run, {"substrate": {"libraries": ["os; rm -rf"]}})


# ---- defects found by the first agent attempts, kept as regression tests ------------

@needs_data
def test_changed_data_probe_keeps_the_store_exactly_as_exported(kenya, tmp_path):
    """The first agent opened the stores with consolidated metadata, which an earlier perturbation dropped."""
    import filecmp
    import xarray as xr
    params = kenya.instance("service-area--weeks-1-2")
    for name in ("original", "changed"):
        kenya.hooks.stage_inputs(kenya.private, params, tmp_path / name)
    kenya.hooks.perturb_inputs(tmp_path / "changed", 3)
    for store in sorted((tmp_path / "original").glob("*.zarr")):
        twin = tmp_path / "changed" / store.name
        files = sorted(p.relative_to(store) for p in store.rglob("*") if p.is_file())
        assert files == sorted(p.relative_to(twin) for p in twin.rglob("*") if p.is_file())
        assert {f.parts[0] for f in files if not filecmp.cmp(store / f, twin / f, shallow=False)} == {"tp"}
        with xr.open_zarr(twin, consolidated=True) as ds:
            assert ds.tp.attrs["units"] == "kg m**-2"


@needs_data
def test_one_unusable_result_fails_the_envelope_and_the_rest_is_still_assessed(kenya, controls, tmp_path):
    params = kenya.instance("service-area--weeks-1-2")
    kenya.hooks.stage_inputs(kenya.private, params, tmp_path / "inputs")
    submission = controls.build("correct", tmp_path / "inputs", params, tmp_path / "submission")
    answer = json.loads((submission / "answer.json").read_text())
    answer["results"]["regional_change_mm"] = [answer["results"]["regional_change_mm"]]         # one array with the wrong shape
    (submission / "answer.json").write_text(json.dumps(answer))
    result = assess(kenya, params, submission, Local(), tmp_path / "work")
    assert result["checks"]["envelope"]["state"] == FAIL and result["checks"]["envelope"]["unusable_results"] == ["regional_change_mm"]
    assert result["checks"]["invariant.change_equals_current_minus_previous"]["state"] == PASS
    assert result["checks"]["probe.changed_data"]["state"] == PASS                # the maps still follow the inputs
    assert result["checks"]["variant"]["state"] == UNRESOLVED and result["computed_outcome"] == FAIL
    assert result["matched_conventions"]["rainfall_semantics"] == ["differenced_cumulative"]


def test_method_pointer_must_name_code_not_quote_a_phrase():
    from assessment.assess import _pointer_resolves
    files = {"run.py": "def calibrate(x):\n    return x\nanswer = {'where': 'calibrate loop and full-fit loop'}\n"}
    assert _pointer_resolves({"file": "run.py", "symbol": "def calibrate"}, files)
    assert _pointer_resolves({"file": "run.py", "symbol": "calibrate"}, files)
    assert _pointer_resolves({"file": "run.py", "lines": [1, 2]}, files)
    assert not _pointer_resolves({"file": "run.py", "symbol": "calibrate loop and full-fit loop"}, files)   # present only because the script writes it
    assert not _pointer_resolves({"file": "run.py", "symbol": "fit_model"}, files)
    assert not _pointer_resolves({"file": "run.py", "lines": [2, 9]}, files)
    assert not _pointer_resolves({"file": "other.py", "symbol": "calibrate"}, files)
