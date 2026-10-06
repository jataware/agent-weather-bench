"""Scientific boundary and evaluator tests, not agent attempts."""
import json

import numpy as np
import pytest
import xarray as xr

from weatherbench.task_tools.references import (seasonal_training, acmad_objective,
                                     wvg_audit, same_array)
from weatherbench.task_tools.checks import check


def test_metadata_validation_needs_no_private_data_or_sibling_checkouts(tmp_path, monkeypatch):
    import weatherbench.task_tools.checks as checks
    monkeypatch.setattr(checks, "PRIVATE", tmp_path / "absent-data")
    result = checks.validate_packages(metadata_only=True)
    assert result["validation"] == "metadata_passed"
    assert all(p["files_verified"] == 0 and p["private_data_validation"] == "not_checked"
               for p in result["packages"])
    with pytest.raises(ValueError, match="Internal task data bundle missing"):
        checks.validate_packages()


def test_source_validation_rejects_a_dependency_outside_the_checkout(tmp_path, monkeypatch):
    import shutil
    import weatherbench.task_tools.checks as checks
    shutil.copytree(checks.PACKAGES, tmp_path / "tasks")
    monkeypatch.setattr(checks, "PACKAGES", tmp_path / "tasks")
    monkeypatch.setattr(checks, "ROOT", tmp_path)
    path = tmp_path / "tasks/seasonal-calibration/input-manifest.json"
    manifest = json.loads(path.read_text())
    manifest["source_records"][0]["path"] = "../another-project/source.txt"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Source records must stay inside this repository"):
        checks.validate_packages(metadata_only=True)


def test_package_validation_catches_malformed_source_yaml_before_launch(tmp_path, monkeypatch):
    import shutil
    import weatherbench.task_tools.checks as checks
    shutil.copytree(checks.PACKAGES, tmp_path / "tasks")
    monkeypatch.setattr(checks, "PACKAGES", tmp_path / "tasks")
    (tmp_path / "tasks/seasonal-calibration/sources.yaml").write_text("title: invalid: nested\n")
    with pytest.raises(ValueError, match="Invalid source record"):
        checks.validate_packages(metadata_only=True)


def seasonal_inputs():
    f = xr.Dataset({"precip": (("init_time", "member", "lead_time", "lat", "lon"),
                               np.ones((2, 2, 3, 1, 1)))},
                   coords={"init_time": np.array(["2000-09-01", "2001-09-01"], dtype="datetime64[D]"),
                           "member": [0, 1], "lead_time": [2, 3, 4], "lat": [0.], "lon": [0.]})
    f.precip.attrs["units"] = "mm/day"
    dates = np.array([f"{y}-{m:02}-01" for y in (2000, 2001) for m in (10, 11, 12)], dtype="datetime64[D]")
    a = np.full((6, 3, 2), 20.)
    a[:, 2] = 10000  # latitude at the upper boundary must be excluded
    o = xr.Dataset({"precip": (("time", "lat", "lon"), a)},
                   coords={"time": dates, "lat": [-.25, .25, .5], "lon": [-.25, .25]})
    o.precip.attrs["units"] = "mm/month"
    return f, o


def test_seasonal_uses_month_lengths_and_half_open_native_cells():
    f, o = seasonal_inputs()
    d = seasonal_training(f, o)
    np.testing.assert_allclose(d.forecast, 92)
    np.testing.assert_allclose(d.observed, 60)
    o.precip.values[0, 0, 0] = np.nan
    with pytest.raises(ValueError, match="90 percent"):
        seasonal_training(f, o)


def test_seasonal_rejects_missing_months_and_wrong_rate_units():
    f, o = seasonal_inputs()
    with pytest.raises(ValueError, match="exactly cover"):
        seasonal_training(f, o.isel(time=slice(1, None)))
    f.precip.attrs["units"] = "m/s"
    with pytest.raises(ValueError, match="mm/day"):
        seasonal_training(f, o)


def component(probabilities):
    return xr.Dataset({name: (("lat", "lon"), np.asarray(a)[None])
                       for name, a in zip(("below", "normal", "above"), probabilities)},
                      coords={"lat": [0.], "lon": [0., 1., 2., 3.]})


def test_component_combine_preserves_support_and_renormalizes_available_weights():
    n = np.nan
    c1 = component([[10, 10, 10, n], [20, 20, 20, n], [70, 70, 70, n]])
    c2 = component([[40, 40, n, n], [20, 20, n, n], [40, 40, n, n]])
    c3 = component([[70, n, n, n], [20, n, n, n], [10, n, n, n]])
    d = acmad_objective([c1, c2, c3])
    np.testing.assert_array_equal(d.available_components, [[3, 2, 1, 0]])
    np.testing.assert_allclose(d.probability.sel(tercile="below").values[0, :3], [.4, .25, .1])
    assert np.isnan(d.probability.values[:, 0, 3]).all()
    np.testing.assert_allclose(d.nominal_weighted_probability.sel(tercile="below").values[0, :3],
                               [(2 * .1 + 8 * .4 + 8 * .7) / 18, .34, .1])
    np.testing.assert_allclose(d.disagreement_pp.sel(tercile="below").values[0, :3], [60, 30, 0])
    c2.below.values[0, 0] = n
    with pytest.raises(ValueError, match="all three"):
        acmad_objective([c1, c2, c3])


def test_component_combine_rejects_silently_aligned_grids():
    c = component([[10] * 4, [20] * 4, [70] * 4])
    with pytest.raises(ValueError, match="grids"):
        acmad_objective([c, c.assign_coords(lon=[1, 2, 3, 4]), c])


def sst_fixture():
    dates = np.arange("1981-01", "2012-01", dtype="datetime64[M]")
    lat = np.arange(-30., 36., 5.)
    lon = np.arange(110., 241., 5.)
    year = np.repeat(np.arange(31), 12)
    spatial = np.cos(np.deg2rad(lat))[:, None] + lon[None] / 100
    values = (20 + year[:, None, None] * spatial[None] / 100
              + np.sin(year[:, None, None] * .3) * np.cos(lon[None, None] / 30))
    return xr.Dataset({"sst": (("time", "lat", "lon"), values,
                                {"units": "degree_Celsius"})},
                      coords={"time": dates, "lat": lat, "lon": lon})


def test_wvg_standardizes_composite_separately_and_requires_complete_seasons():
    s = sst_fixture()
    d = wvg_audit(s)
    b = d.sel(year=slice(1981, 2010))
    np.testing.assert_allclose(b.nino34_z.mean(), 0, atol=1e-12)
    np.testing.assert_allclose(b.western_v_z.mean("year"), 0, atol=1e-12)
    np.testing.assert_allclose(b.western_v_z.std("year", ddof=1), 1, atol=1e-12)
    expected_wz = (d.western_v_c - b.western_v_c.mean("year")) / b.western_v_c.std("year", ddof=1)
    np.testing.assert_allclose(d.western_v_z, expected_wz, atol=1e-12)
    np.testing.assert_allclose(d.wvg, (d.nino34_z - d.western_v_z).transpose("variant", "year"), atol=1e-12)
    missing = s.isel(time=np.flatnonzero(s.time.values.astype("datetime64[M]") != np.datetime64("1990-04", "M")))
    with pytest.raises(ValueError, match="three MAM"):
        wvg_audit(missing)
    with pytest.raises(ValueError, match="baseline"):
        wvg_audit(s.sel(time=slice("1982", None)))


def test_comparator_rejects_hidden_missingness_wrong_dates_and_infinities():
    expected = xr.DataArray([.2, np.nan], dims="year", coords={"year": [2000, 2001]})
    assert same_array(expected.copy(), expected)
    assert not same_array(expected.fillna(0), expected)
    assert not same_array(expected.assign_coords(year=[2001, 2002]), expected)
    assert not same_array(xr.full_like(expected, np.inf), expected)


def test_static_check_cannot_declare_completion_and_does_not_execute_submission(tmp_path, monkeypatch):
    import weatherbench.task_tools.checks as checks
    private = tmp_path / "private"
    controller = private / "acmad-objective/controller"
    controller.mkdir(parents=True)
    inputs = private / "acmad-objective/agent-inputs"
    inputs.mkdir(parents=True)
    (inputs / "source-manifest.json").write_text(json.dumps({"sources": ["local-source:test"]}))
    c = component([[10] * 4, [20] * 4, [70] * 4])
    acmad_objective([c, c, c]).to_netcdf(controller / "objective.nc", engine="h5netcdf")
    monkeypatch.setattr(checks, "PRIVATE", private)
    (tmp_path / "solve.py").write_text("raise RuntimeError('submission must never execute')\n")
    (tmp_path / "answer.json").write_text(json.dumps({"supported_cells": True}))
    result = check("acmad-objective", tmp_path)
    assert not result["submitted_code_executed"]
    assert result["completion"] == "incomplete_required_checks_failed"
    assert result["basic_validity"]["answer_schema"]["state"] == "fail"
    assert result["leaves"]["reusable_workflow"]["state"] == "unresolved"
    assert result["integrity"]["state"] == "unresolved"


def complete_cli_fixture(tmp_path, monkeypatch):
    """Valid numerical artifacts and records, without trusted replay evidence."""
    import weatherbench.task_tools.checks as checks
    from weatherbench.task_tools.prepare import digest
    private = tmp_path / "private"
    controller = private / "acmad-objective/controller"
    controller.mkdir(parents=True)
    inputs = private / "acmad-objective/agent-inputs"
    inputs.mkdir(parents=True)
    (inputs / "source-manifest.json").write_text(json.dumps({"sources": ["local-source:test"]}))
    monkeypatch.setattr(checks, "PRIVATE", private)
    submission = tmp_path / "submission"
    submission.mkdir()
    c = component([[10] * 4, [20] * 4, [70] * 4])
    objective = acmad_objective([c, c, c])
    objective.to_netcdf(controller / "objective.nc", engine="h5netcdf")
    objective.to_netcdf(submission / "objective.nc", engine="h5netcdf")
    for name in ("report.txt", "outlook.png", "handoff.txt"):
        (submission / name).write_text("Presence alone is not scientific evidence.")
    (submission / "workflow.sh").write_text("exit 99 # this submitted command must never execute\n")
    (submission / "raw.bin").write_bytes(b"retained bytes")
    (submission / "answer.json").write_text(json.dumps({"supported_cells": 4,
        "fully_supported_cells": 4, "single_component_cells": 0, "maximum_weighting_difference_pp": 0.}))
    (submission / "execution.json").write_text(json.dumps({"schema_version": 1,
        "replay": {"argv": ["sh", "workflow.sh", "{output_dir}"]},
        "retained_files": ["workflow.sh", "raw.bin"], "dependencies": ["POSIX shell in assigned runtime"]}))
    record = {"schema_version": 1, "sources": [{"id": "local-source:test", "product_version": "test case",
        "access": "supplied", "request": {"identifier": "local-source:test"}, "retrieved_at": None}],
        "files": [{"path": name, "sha256": digest(submission / name), "source_ids": ["local-source:test"] if name == "raw.bin" else []}
                  for name in ("raw.bin", "objective.nc")],
        "transformations": [{"operation": "test combination", "inputs": ["raw.bin"], "outputs": ["objective.nc"], "parameters": {}}]}
    (submission / "provenance.json").write_text(json.dumps(record))
    return submission


def test_cli_manifest_and_correct_numbers_still_need_expert_execution_and_integrity(tmp_path, monkeypatch):
    submission = complete_cli_fixture(tmp_path, monkeypatch)
    result = check("acmad-objective", submission)
    assert result["all_deterministic_checks_pass"]
    assert result["completion"] == "pending_execution_and_expert_review"
    assert result["leaves"]["objective_product"]["state"] == "pass"
    assert result["leaves"]["scientific_report"]["state"] == "unresolved"
    assert result["leaves"]["reusable_workflow"]["state"] == "unresolved"
    assert result["integrity"]["state"] == "unresolved"
    assert result["weighted_score_bounds"] == pytest.approx([70, 100])
    assert not result["submitted_code_executed"]
    assert not (submission / "solve.py").exists()


@pytest.mark.parametrize("damage", ["hash", "source", "lineage", "timestamp"])
def test_evidence_record_failures_cannot_be_compensated_by_correct_numeric_outcomes(tmp_path, monkeypatch, damage):
    submission = complete_cli_fixture(tmp_path, monkeypatch)
    path = submission / "provenance.json"
    record = json.loads(path.read_text())
    if damage == "hash":
        (submission / "raw.bin").write_bytes(b"changed bytes")
    elif damage == "source":
        record["sources"][0]["id"] = "local-source:wrong"
        record["files"][0]["source_ids"] = ["local-source:wrong"]
    elif damage == "lineage":
        record["transformations"][0]["inputs"] = ["unrecorded.nc"]
    else:
        record["sources"][0].update(access="downloaded", retrieved_at="2026-10-02T10:00:00")
    path.write_text(json.dumps(record))
    result = check("acmad-objective", submission)
    assert result["completion"] == "incomplete_required_checks_failed"
    assert result["leaves"]["objective_product"]["state"] == "pass"
    assert result["leaves"]["combination_audit"]["state"] == "pass"
    failed = "source_coverage" if damage == "source" else "provenance_fields"
    assert result["basic_validity"][failed]["state"] == "fail"
    if damage != "source":
        assert result["basic_validity"]["source_coverage"]["state"] == "pass"
