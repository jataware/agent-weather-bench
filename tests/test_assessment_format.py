"""The generic assessment format (docs/assessment-format.md) and its first template."""
import importlib.util
import json

import numpy as np
import pytest

from assessment import judge as judging
from assessment.assess import answer_digest, assess
from assessment.compare import EnvelopeError, compare, normalise, read_results, tolerance
from assessment.execute import Local, valid_argv
from assessment.judge import validate_verdict
from assessment.outcomes import FAIL, PASS, UNRESOLVED, blocked, combine, headline, outcome
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
    with pytest.raises(ValueError):
        outcome(UNRESOLVED, "a broken submission is a failure, not an open question", reason="not_assessed")


def test_a_check_blocked_by_the_submissions_own_fault_fails_and_names_it():
    row = blocked("envelope", "Fails with the envelope: regional_change_mm is unusable.")
    assert row["state"] == FAIL and row["blocked_by"] == "envelope" and "reason" not in row
    result = headline({"checks": {"envelope": outcome(FAIL, "one result is missing"), "variant": row, "probe.replay": outcome(PASS),
                                  "interpretation.generalization": {**outcome(UNRESOLVED, reason="judge_not_run"), "decided_by": "judge"}}})
    assert (result["outcome"], result["computed_outcome"], result["judged_outcome"]) == (FAIL, FAIL, UNRESOLVED)


# ---- comparison is by coordinate label ------------------------------------------

def test_arrays_are_compared_by_coordinate_not_storage_order():
    reference = {"latitude": np.array([3.0, 1.5, 0.0]), "field": np.array([[1.0, 2.0, 3.0]])}
    flipped = normalise(RESULTS, {"latitude": [0.0, 1.5, 3.0], "field": [[3.0, 2.0, 1.0]]})
    assert compare(RESULTS, flipped, reference)[0]
    mislabelled = normalise(RESULTS, {"latitude": [0.0, 1.5, 3.0], "field": [[1.0, 2.0, 3.0]]})
    assert not compare(RESULTS, mislabelled, reference)[0]
    other_cells = normalise(RESULTS, {"latitude": [3.0, 1.5], "field": [[1.0, 2.0]]})
    assert not compare(RESULTS, other_cells, reference)[0]


def test_tolerance_is_an_error_bound_computed_from_what_the_spec_declares():
    """Two correct float32 means of 101 values below 200 mm cannot differ by more than this; a pitfall must."""
    bound = tolerance({"precision": "float32", "operations": 101, "magnitude": 200})
    assert 2.40e-3 < bound < 2.41e-3 and tolerance({"exact": True}) == 0
    assert tolerance({"precision": "float64", "operations": 101, "magnitude": 200}) < 1e-11
    for bad in ({"atol": 1e-3}, {"precision": "float16", "operations": 1, "magnitude": 1}, {"precision": "float32", "operations": 0, "magnitude": 1}):
        with pytest.raises(ValueError):
            tolerance(bad)
    values = np.float32(np.random.default_rng(0).uniform(0, 200, 101))
    forward, backward = np.float32(0), np.float32(0)
    for value in values:
        forward += value
    for value in values[::-1]:
        backward += value
    assert abs(float(forward) - float(backward)) / 101 <= bound         # two orders of summation stay inside the bound


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


# ---- the judge: narrow questions, exact quotations, a pinned identity ---------------

def _assessment_with_questions():
    question = judging.interpretation_question("generalization")
    absent = judging.report_question({"requirement": "The report states the uncertainty plainly.", "judge": "Does it?"})
    return headline({"checks": {"variant": outcome(PASS), "interpretation.generalization": judging.pending("generalization", question),
                                "process.plain": judging.pending("plain", absent, requirement="The report states the uncertainty plainly.", source="practice 7")}})


def test_without_a_judge_the_questions_stay_unresolved_and_carry_their_text():
    result = _assessment_with_questions()
    assert result["computed_outcome"] == PASS and result["outcome"] == UNRESOLVED and result["unresolved_reasons"] == ["judge_not_run"]
    assert judging.questions_for(result)["interpretation.generalization"]["silence"] == "passes"
    old_record = {"checks": {"interpretation.generalization": {**outcome(UNRESOLVED, reason="judge_not_run"), "decided_by": "judge"}}}
    assert judging.questions_for(old_record)["interpretation.generalization"] == judging.interpretation_question("generalization")


def test_inexact_quote_voids_the_verdict():
    files = {"report.md": "The newer forecast is wetter\n  in week one."}
    exact = {"verdict": "pass", "basis": "quoted", "reason": "bounded claim", "citations": [{"source": "report.md", "quote": "wetter in week one"}]}
    assert validate_verdict(exact, files)["state"] == PASS                       # exact up to white space
    inexact = {**exact, "citations": [{"source": "report.md", "quote": "wetter in week 1"}]}
    assert validate_verdict(inexact, files)["reason"] == "invalid_citation"
    assert validate_verdict({**exact, "citations": [{"source": "other.md", "quote": "wetter"}]}, files)["reason"] == "invalid_citation"


def test_a_verdict_without_a_quotation_counts_only_where_the_question_allows_it():
    files = {"report.md": "The rain total rose."}
    silent = {"verdict": "pass", "basis": "nothing_to_assess", "reason": "no such claim", "citations": []}
    absent = {"verdict": "fail", "basis": "required_statement_absent", "reason": "never stated", "citations": []}
    assert validate_verdict(silent, files, {"silence": "passes"})["state"] == PASS
    assert validate_verdict(silent, files, {"silence": "fails"})["reason"] == "invalid_citation"
    assert validate_verdict(absent, files, {"silence": "fails"})["state"] == FAIL
    assert validate_verdict(absent, files, {"silence": "passes"})["reason"] == "invalid_citation"
    assert validate_verdict({"verdict": "fail", "basis": "quoted", "reason": "overclaim", "citations": []}, files, {"silence": "passes"})["reason"] == "invalid_citation"


def test_judge_decides_every_question_in_one_request_and_retries_a_discarded_verdict_once():
    files, calls = {"report.md": "The newer forecast is wetter in week one."}, []

    def backend(questions, shown):
        calls.append(sorted(questions))
        quote = "wetter in week one" if len(calls) > 1 else "wetter in week 1"
        return ([{"id": name, "verdict": "pass", "basis": "quoted", "reason": "bounded", "citations": [{"source": "report.md", "quote": quote}]}
                 if name.startswith("interpretation") else {"id": name, "verdict": "fail", "basis": "required_statement_absent", "reason": "absent", "citations": []}
                 for name in questions], {"usage": {"output_tokens": 1}})
    result = _assessment_with_questions()
    judgement = judging.apply(result, files, backend)
    assert calls == [["interpretation.generalization", "process.plain"], ["interpretation.generalization"]]
    assert result["checks"]["interpretation.generalization"]["state"] == PASS and result["checks"]["process.plain"]["state"] == FAIL
    assert result["checks"]["process.plain"]["source"] == "practice 7" and result["checks"]["process.plain"]["decided_by"] == "judge"
    assert (result["outcome"], result["computed_outcome"], result["judged_outcome"]) == (FAIL, PASS, FAIL)
    assert result["judge"]["id"] == judging.judge_id() and result["judge"]["model"] == "claude-opus-5-5" and result["judge"]["requests"] == 2
    again = _assessment_with_questions()
    judging.apply(again, files, lambda *_: pytest.fail("a recorded judgement of the same questions and files is reused"), recorded=judgement)
    assert again["checks"] == result["checks"]


def test_an_unreachable_judge_is_infrastructure_not_a_verdict():
    def backend(questions, files):
        raise judging.JudgeUnavailable("no network")
    result = _assessment_with_questions()
    judging.apply(result, {"report.md": "text"}, backend)
    assert result["outcome"] == UNRESOLVED and result["unresolved_reasons"] == ["infrastructure"] and result["judge"]["unavailable"]


def test_the_judge_is_shown_text_and_summaries_never_raw_arrays(tmp_path):
    (tmp_path / "results.zarr").mkdir()
    (tmp_path / "results.zarr/zarr.json").write_text("{}")
    (tmp_path / "report.md").write_text("A report.")
    (tmp_path / "answer.json").write_text(json.dumps({"results": {"field": [[float(i)] * 60 for i in range(80)]}, "claims": {"direction": ["wetter"]}}))
    shown = judging.views(tmp_path, "The brief.", {"controller/results-summary.txt": "field: mean 3"})
    assert set(shown) == {"task/brief.md", "report.md", "answer.json", "controller/results-summary.txt"}
    assert "<array of shape (80, 60): min 0, mean 39.5, max 79>" in shown["answer.json"] and "wetter" in shown["answer.json"]


def test_judge_calibration_record_is_for_the_pinned_judge():
    from assessment.calibration import CASES, RECORD
    record = json.loads(RECORD.read_text())
    assert record["judge"]["id"] == judging.judge_id(), "Rerun `python -m assessment judge-calibration`"
    assert record["cases"] == len(CASES) == record["agreeing"] and record["passed"]
    assert {row["expected"] for row in record["rows"]} == {"pass", "fail"} and {row["kind"] for row in record["rows"]} == {"interpretation", "method_statement", "report_statement"}


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
        assert len(kenya.brief(params).split()) <= 200
    assert "changed_instance" not in kenya.spec["probes"]  # a second instance is a second episode, not a rerun


def test_conventions_sheet_is_an_optional_condition_not_part_of_the_brief(kenya):
    params = kenya.development_instances()[0]
    plain, supplied = kenya.brief(params), kenya.brief(params, supplied=["conventions"])
    assert "conventions.md" not in plain and supplied.startswith(plain) and "/task/conventions.md" in supplied
    sheet = (kenya.folder / kenya.spec["supplements"]["conventions"]).read_text()
    assert "cosine of its latitude" in sheet and not any(name.replace("_", " ") in sheet.lower() for name in kenya.spec["pitfalls"])
    with pytest.raises(ValueError):
        kenya.brief(params, supplied=["answers"])


@needs_data
def test_two_reference_implementations_agree(kenya, tmp_path):
    params = kenya.instance("service-area--weeks-1-2")
    kenya.hooks.stage_inputs(kenya.private, params, tmp_path / "inputs")
    for combination in kenya.combinations():
        a, b = (f(tmp_path / "inputs", params, combination) for f in (kenya.hooks.reference, kenya.hooks.independent))
        assert list(a["period"]) == list(b["period"]) == params["period_start"]
        assert all(a[name].shape == b[name].shape and np.max(np.abs(a[name] - b[name])) < 1e-9 for name in a if name != "period")
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
def test_arrays_are_read_by_dimension_name_and_label(kenya, controls, tmp_path):
    """The same answer with its dimensions and labels in another order is the same answer."""
    params = kenya.instance("service-area--weeks-1-2")
    kenya.hooks.stage_inputs(kenya.private, params, tmp_path / "inputs")
    plain, _ = read_results(kenya.spec["results"], controls.build("correct", tmp_path / "inputs", params, tmp_path / "a"))
    moved, problems = read_results(kenya.spec["results"], controls.build("accepted_rearranged_arrays", tmp_path / "inputs", params, tmp_path / "b"))
    assert not problems and list(moved["period"]) == params["period_start"][::-1] and moved["change_mm"].shape == plain["change_mm"].shape
    assert not np.array_equal(moved["change_mm"], plain["change_mm"]) and compare(kenya.spec["results"], moved, plain)[0]
    assert assess(kenya, params, tmp_path / "b", Local(), tmp_path / "work")["computed_outcome"] == PASS


@needs_data
def test_an_array_on_other_dimensions_is_unusable_and_says_why(kenya, controls, tmp_path):
    import shutil
    import xarray as xr
    params = kenya.instance("service-area--weeks-1-2")
    kenya.hooks.stage_inputs(kenya.private, params, tmp_path / "inputs")
    submission = controls.build("correct", tmp_path / "inputs", params, tmp_path / "submission")
    arrays = xr.open_zarr(submission / "results.zarr", chunks=None, consolidated=False).load().rename(period="week")
    shutil.rmtree(submission / "results.zarr")
    arrays.to_zarr(submission / "results.zarr", zarr_format=3, consolidated=False)
    results, problems = read_results(kenya.spec["results"], submission)
    assert set(results) == {"latitude", "longitude"} and "the brief asks for (period, latitude, longitude)" in problems["change_mm"]
    assert problems["period"] == "results.zarr has no coordinate array period"


@needs_data
def test_pitfall_is_named(kenya, controls, tmp_path):
    result = _assess(kenya, controls, "pitfall_same_lead", "service-area--weeks-1-2", tmp_path)
    assert result["checks"]["variant"]["state"] == FAIL and result["checks"]["variant"]["pitfalls_certain"] == ["same_lead"]
    assert all(result["checks"][f"probe.{name}"]["state"] == PASS for name in ("replay", "changed_data"))


@needs_data
def test_coinciding_pitfall_is_separated_by_a_chosen_data_change(kenya, controls, tmp_path):
    """Near the equator weighted and unweighted means agree within rounding, so the submitted numbers alone cannot tell."""
    params = kenya.instance("service-area--weeks-1-2")
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
        assert result["checks"]["probe.changed_data"]["data_change_chosen_to_separate_accepted_from_pitfall"]
    assert result["matched_conventions"]["area_weighting"] == ["cos_latitude"]


@needs_data
def test_results_right_for_the_instance_pass_when_no_data_change_separates_the_readings(kenya, controls, tmp_path):
    """On two rows next to the equator the area weights are equal within rounding. The product is right either way."""
    result = _assess(kenya, controls, "pitfall_unweighted", "central--weeks-2-3", tmp_path)
    variant = result["checks"]["variant"]
    assert variant["state"] == PASS and variant["reason"] == "ambiguous_variant" and variant["pitfalls_possible"] == ["unweighted"]
    assert result["computed_outcome"] == PASS and "ambiguous_variant" not in result["unresolved_reasons"]


@needs_data
def test_task_parameters_may_be_written_into_the_code(kenya, controls, tmp_path):
    result = _assess(kenya, controls, "accepted_hardcoded_parameters", "service-area--weeks-1-2", tmp_path)
    assert result["computed_outcome"] == PASS and not [name for name in result["checks"] if "changed_instance" in name]


@needs_data
def test_cached_answer_passes_replay_and_fails_changed_data(kenya, controls, tmp_path):
    result = _assess(kenya, controls, "cached_output", "service-area--weeks-1-2", tmp_path)
    states = {name: row["state"] for name, row in result["checks"].items()}
    assert states["probe.replay"] == PASS and states["probe.changed_data"] == FAIL and result["computed_outcome"] == FAIL


@needs_data
def test_missing_answer_fails_the_envelope_and_every_check_that_rests_on_it(kenya, controls, tmp_path):
    result = _assess(kenya, controls, "no_answer", "service-area--weeks-1-2", tmp_path)
    computed = {name: row for name, row in result["checks"].items() if row.get("decided_by") != "judge"}
    assert result["checks"]["envelope"]["state"] == FAIL and result["computed_outcome"] == FAIL
    assert all(row["state"] == FAIL for row in computed.values())
    assert all(row["blocked_by"] == "envelope" for name, row in computed.items() if name != "envelope")
    assert result["unresolved_reasons"] == ["judge_not_run"]                     # the report can still be judged


@needs_data
def test_one_broken_part_fails_what_rests_on_it_and_the_rest_is_assessed_on_its_merits(kenya, controls, tmp_path):
    result = _assess(kenya, controls, "missing_result", "service-area--weeks-1-2", tmp_path / "a")
    assert result["checks"]["envelope"]["state"] == FAIL and result["checks"]["envelope"]["unusable_parts"] == ["regional_change_mm"]
    for check in ("variant", "claim.direction", "invariant.regional_change_within_cell_range"):
        assert result["checks"][check]["state"] == FAIL and result["checks"][check]["blocked_by"] == "envelope", check
    assert result["checks"]["invariant.change_equals_current_minus_previous"]["state"] == PASS
    assert result["checks"]["probe.changed_data"]["state"] == PASS                # the maps still follow the data
    assert result["matched_conventions"]["rainfall_semantics"] == ["differenced_cumulative"]
    no_command = _assess(kenya, controls, "no_run_command", "service-area--weeks-1-2", tmp_path / "b")
    assert no_command["checks"]["probe.replay"]["blocked_by"] == "envelope" and no_command["checks"]["claim.direction"]["state"] == PASS


# ---- string coordinates and coverage (outcome mode has no reference answer) ---------

FORECAST = {"issue": {"kind": "coordinate", "dtype": "date"}, "cell": {"kind": "coordinate", "tolerance": {"atol": 0}},
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
    import xarray as xr
    from assessment.feedback import DevelopmentFeedback
    submission = tmp_path / "work/submission"
    submission.mkdir(parents=True)
    for name, value in (("good.zarr", 2.0), ("bad.zarr", 3.0)):
        xr.Dataset({"value": ("cell", [value])}, coords={"cell": [0]}).to_zarr(submission / name, zarr_format=3, consolidated=False)
    (submission / "linked.zarr").mkdir()
    (submission / "linked.zarr/zarr.json").symlink_to(tmp_path / "work/submission/good.zarr/zarr.json")

    def score(store):
        with xr.open_zarr(store, chunks=None, consolidated=False) as arrays:
            if float(arrays.value[0]) != 2:
                raise ValueError("withheld target is 17.5 mm")
        return {"rmse_mm": 1.5}
    feedback = DevelopmentFeedback(tmp_path / "work", tmp_path / "controller", score, max_submissions=4)
    assert json.loads(feedback.query("good.zarr")["stdout"]) == {"rmse_mm": 1.5}
    for name in ("bad.zarr", "../escape.zarr", "linked.zarr"):
        reply = feedback.query(name)
        assert reply["exit_code"] == 1 and "17.5" not in reply["stderr"]
    denied = feedback.query("good.zarr")
    assert denied["exit_code"] == 1 and denied["feedback_remaining"] == 0
    summary = feedback.public_summary()
    assert [row["status"] for row in summary["requests"]] == ["scored", "failed", "failed", "failed"] and summary["limit_denials"] == 1
    assert "private_error" not in json.dumps(summary) and not summary["final_score_exposed"]
    assert (tmp_path / "controller/prediction-001.zarr/zarr.json").is_file()      # each scored store is frozen with the ledger


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
    assert len(weeks.brief(params).split()) <= 200
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
    assert short["checks"]["coverage"]["state"] == FAIL and short["checks"]["probe.replay"]["blocked_by"] == "coverage"
    assert short["checks"]["envelope"]["state"] == PASS and "skill" not in short


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
    assert len(seasonal.brief(seasonal.development_instances()[0]).split()) <= 200


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
def test_a_method_entry_the_brief_asks_for_fails_when_missing_or_pointing_nowhere(seasonal, seasonal_controls, tmp_path):
    missing = _assess_seasonal(seasonal, seasonal_controls, "no_method_statement", tmp_path / "a")
    false = _assess_seasonal(seasonal, seasonal_controls, "false_method_pointer", tmp_path / "b")
    for result in (missing, false):
        row = result["checks"]["process.documented_calibration"]
        assert row["state"] == FAIL and row.get("decided_by") != "judge" and result["computed_outcome"] == FAIL
    assert false["checks"]["process.documented_cross_validation"]["decided_by"] == "judge"     # the other entry is sound and goes to the judge
    assert "def leave_one_out" in false["checks"]["process.documented_cross_validation"]["question"]["requirement"]


# ---- substrate use: the original path monitor plus library imports ------------------

def test_library_imports_are_recorded_beside_the_original_monitor(tmp_path):
    from assessment.substrate import substrate_record
    from assessment.substrate_use import substrate_use
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
    catalog = substrate_record(run, {"substrate": {"image_paths": ["/substrate/skills", "/catalog"]}})["image_paths"]
    assert catalog["/substrate/skills"] == {"commands_naming": 2, "of_which_failed": 0, "first_step": 1, "used": True} and not catalog["/catalog"]["used"]
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


def test_dates_are_read_from_datetimes_or_text_and_scalars_from_either_place(tmp_path):
    """The first format let an agent write a date axis three ways. A labelled store leaves one reading."""
    import xarray as xr
    spec = {"issue": {"kind": "coordinate", "dtype": "date"}, "rain_mm": {"dims": ["issue"], "tolerance": {"atol": 0}}, "score": {"dims": [], "tolerance": {"atol": 0}}}
    for name, labels in (("a", np.array(["2026-10-11", "2026-10-04"], dtype="datetime64[ns]")), ("b", ["2026-10-11T00:00:00", "2026-10-04"])):
        (tmp_path / name).mkdir()
        xr.Dataset({"rain_mm": ("issue", [3.0, 1.0])}, coords={"issue": labels}).to_zarr(tmp_path / name / "results.zarr", zarr_format=3, consolidated=False)
        results, problems = read_results(spec, tmp_path / name, {"results": {"score": 0.25}})
        assert not problems and list(results["issue"]) == ["2026-10-11", "2026-10-04"] and float(results["score"]) == 0.25
    results, problems = read_results(spec, tmp_path / "a", {})
    assert "score" in problems and "rain_mm" in results
    with pytest.raises(EnvelopeError):
        read_results(spec, tmp_path / "nothing")


def test_an_answer_is_identified_by_its_json_and_its_store(tmp_path):
    (tmp_path / "answer.json").write_text("{}")
    before = answer_digest(tmp_path)
    (tmp_path / "results.zarr").mkdir()
    (tmp_path / "results.zarr/zarr.json").write_text("{}")
    with_store = answer_digest(tmp_path)
    (tmp_path / "results.zarr/zarr.json").write_text('{"a": 1}')
    assert len({before, with_store, answer_digest(tmp_path)}) == 3


@needs_data
def test_runtime_crash_is_not_blamed_on_the_method(kenya, controls, tmp_path):
    """Images from the pilot crashed inside a native library on exit. Three runs were first marked as failing every probe."""
    params = kenya.instance("service-area--weeks-1-2")
    kenya.hooks.stage_inputs(kenya.private, params, tmp_path / "inputs")
    for name, ending, expected in (("after", "os._exit(3)", PASS), ("before", "os.kill(os.getpid(), signal.SIGSEGV)", UNRESOLVED)):
        submission = controls.build("correct", tmp_path / "inputs", params, tmp_path / name / "submission")
        source = (submission / "solve.py").read_text()
        write = '    arrays.to_zarr(output / "results.zarr", mode="w", zarr_format=3, consolidated=False)\n'
        last = '    (output / "answer.json").write_text(json.dumps(answer, allow_nan=False) + "\\n")\n'
        assert write in source and source.endswith(last)
        crash = f"    import os, signal\n    {ending}\n"
        (submission / "solve.py").write_text(source + crash if name == "after" else source.replace(write, crash + write))
        result = assess(kenya, params, submission, Local(), tmp_path / name / "work")
        replay = result["checks"]["probe.replay"]
        assert replay["state"] == expected
        if name == "after":
            assert "exited abnormally" in replay["run"]["note"] and result["computed_outcome"] == PASS
        else:
            assert replay["reason"] == "infrastructure" and not [n for n, r in result["checks"].items() if r["state"] == FAIL]


def test_rulings_are_keyed_by_answer_and_marked_as_proposed(seasonal):
    import yaml
    rulings = yaml.safe_load((seasonal.folder / "rulings.yaml").read_text())["rulings"]
    assert len({row["answer_sha256"] for row in rulings}) == len(rulings) == 3
    assert all(row["ruling"] == "incorrect" and row["status"] == "proposed" and row["reason"] and row["evidence"] for row in rulings)


@needs_weeks
@needs_seasonal
def test_agents_are_told_only_what_the_brief_explains(weeks, seasonal, tmp_path):
    """Version 1 put an internal cell-selection field in instance.json; three agent scripts guessed its meaning and broke."""
    for template, instance, internal in ((weeks, "final-2012-2014--western-six", "longitude_limit"),
                                         (seasonal, "train-1993-2000--new-2001-2002--southern-rows", "latitude_limit")):
        params = template.instance(instance)
        assert params[internal] is not None and template.spec["spec_version"] == 3
        template.hooks.stage_inputs(template.private, params, tmp_path / template.name)
        told = json.loads((tmp_path / template.name / "instance.json").read_text())
        assert internal not in told and told["id"] == instance
        assert not hasattr(template.hooks, "UNDOCUMENTED_PARAMS")
    assert told["training_years"] == list(range(1993, 2001)) and told["new_years"] == [2001, 2002]


@needs_seasonal
def test_a_reading_that_cannot_change_any_result_on_this_task_is_not_failed_here(seasonal, seasonal_controls, tmp_path):
    """With eight training years the held-out and full-sample category boundaries give the same categories for any data.
    An earlier format failed this by rerunning the code on other years. Other years are now another episode."""
    instance = "train-1993-2000--new-2001-2002--southern-rows"
    result = _assess_seasonal(seasonal, seasonal_controls, "pitfall_full_sample_thresholds", tmp_path / "a", instance)
    assert result["first_match_conventions"]["category_thresholds"] == ["full_sample", "leave_one_out"]     # the numbers fit both
    assert result["checks"]["probe.changed_data"]["data_change_chosen_to_separate_accepted_from_pitfall"] is False
    assert result["checks"]["variant"]["state"] == PASS and result["checks"]["variant"]["reason"] == "ambiguous_variant"
    for check in ("process.verification_categories", "process.historical_performance"):
        assert result["checks"][check]["state"] == PASS, check
    assert "category_thresholds" not in result["checks"]["process.verification_categories"]["conventions_that_matter"]
    assert result["checks"]["probe.held_out_year_isolation"]["state"] == PASS     # the forecast itself does hold the year out
    assert _assess_seasonal(seasonal, seasonal_controls, "correct", tmp_path / "b", instance)["computed_outcome"] == PASS
    twelve = _assess_seasonal(seasonal, seasonal_controls, "pitfall_full_sample_thresholds", tmp_path / "c", "train-1993-2004--new-2005-2006--all-cells")
    assert twelve["checks"]["process.verification_categories"]["state"] == FAIL    # where the reading changes a result, it fails
