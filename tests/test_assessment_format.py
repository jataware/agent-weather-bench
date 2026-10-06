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


def test_fixture_system_runs_the_certified_control_solution(kenya):
    assert (ROOT / "systems/kenya-revision-fixture/solve.py").read_bytes() == (kenya.folder / "controls/solve.py").read_bytes()


def test_certification_record_matches_the_current_spec_and_code(kenya):
    record = json.loads((kenya.folder / "certification.json").read_text())
    assert record["fingerprint"] == kenya.fingerprint(), "Spec, reference or assessment code changed: rerun `python -m assessment certify kenya-forecast-revision`"
    assert record["automatic_tests_passed"] and record["certified"] is False
    assert record["tests"]["5_model_attempts"]["status"] == "not_run"


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
