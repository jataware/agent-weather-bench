"""Independent arithmetic contrasts for the ACMAD disagreement check."""
import json

import numpy as np
import pytest
import xarray as xr

from weatherbench.task_tools.checks import check, disagreement_comparison
from weatherbench.task_tools.references import same_array


def independent_disagreement():
    """Pairwise implementations in native percent and float32 fractions."""
    percent = np.empty((3, 3, 1, 4), dtype=np.float32)
    for i, below in enumerate((33.333333, 33.333340, 33.333350)):
        percent[i, :, :, :] = np.array([below, 30, 70 - below], dtype=np.float32)[:, None, None]
    percent[2, :, :, 1] = np.nan
    percent[1:, :, :, 2] = np.nan
    percent[:, :, :, 3] = np.nan
    present = np.isfinite(percent).all(axis=1)
    fraction = percent / np.float32(100)
    native_result = np.full(percent.shape[1:], np.nan, dtype=np.float64)
    fraction_result = np.full(percent.shape[1:], np.nan, dtype=np.float32)
    for row in range(1):
        for col in range(4):
            available = np.flatnonzero(present[:, row, col])
            if not len(available):
                continue
            for category in range(3):
                native_result[category, row, col] = max(
                    abs(float(percent[i, category, row, col]) - float(percent[j, category, row, col]))
                    for i in available for j in available)
                fraction_result[category, row, col] = max(
                    abs(fraction[i, category, row, col] - fraction[j, category, row, col])
                    for i in available for j in available) * np.float32(100)
    coords = {"tercile": ["below", "near", "above"], "lat": [0.], "lon": [0., 1., 2., 3.]}
    def field(values):
        return xr.DataArray(values, dims=("tercile", "lat", "lon"), coords=coords,
                            attrs={"units": "percentage_points"})
    return field(fraction_result), field(native_result)


def test_correct_independent_float32_unit_conversion_is_accepted():
    actual, expected = independent_disagreement()
    assert not same_array(actual, expected)  # reproduces the previous false rejection
    passed, detail = disagreement_comparison(actual, expected)
    assert passed
    assert "relative tolerance 0" in detail
    assert "0/9 finite entries outside tolerance" in detail
    assert actual.sel(lon=2).max() == 0  # single-component support
    assert actual.sel(lon=3).isnull().all()  # unsupported cells stay missing


@pytest.mark.parametrize("damage", ["scientific_difference", "fraction_units", "missingness", "grid", "units", "infinity", "dimensions"])
def test_roundoff_allowance_does_not_accept_scientific_or_contract_defects(damage):
    actual, expected = independent_disagreement()
    if damage == "scientific_difference":
        actual.values[0, 0, 0] += .01
    elif damage == "fraction_units":
        actual.values[0, 0, 0] = expected.values[0, 0, 0] = 30
        actual.values[:] /= 100
    elif damage == "missingness":
        actual = actual.fillna(0)
    elif damage == "grid":
        actual = actual.assign_coords(lon=[1., 2., 3., 4.])
    elif damage == "units":
        actual.attrs["units"] = "1"
    elif damage == "infinity":
        actual.values[0, 0, 0] = np.inf
    else:
        actual = actual.rename({"lat": "latitude"})
    assert not disagreement_comparison(actual, expected)[0]


def test_absolute_policy_rejects_a_large_disagreement_error_previously_hidden_by_rtol():
    expected = xr.DataArray([100.], dims="cell", coords={"cell": [0]},
                            attrs={"units": "percentage_points"})
    actual = expected.copy(data=[100.00005])
    assert same_array(actual, expected)
    passed, detail = disagreement_comparison(actual, expected)
    assert not passed
    assert "1/1 finite entries outside tolerance" in detail


def test_static_check_applies_precision_policy_only_to_disagreement(tmp_path, monkeypatch):
    import weatherbench.task_tools.checks as checks
    actual, expected = independent_disagreement()
    private = tmp_path / "private/acmad-objective"
    (private / "controller").mkdir(parents=True)
    (private / "agent-inputs").mkdir()
    (private / "agent-inputs/source-manifest.json").write_text(json.dumps({"sources": []}))
    monkeypatch.setattr(checks, "PRIVATE", tmp_path / "private")
    probability = expected.copy(data=np.full(expected.shape, 1 / 3))
    probability.attrs["units"] = "1"
    reference = xr.Dataset({"disagreement_pp": expected, "probability": probability,
                            "nominal_weighted_probability": probability.copy(),
                            "available_components": (("lat", "lon"), np.array([[3, 2, 1, 0]], dtype=np.int32))})
    reference.to_netcdf(private / "controller/objective.nc", engine="h5netcdf")
    submitted = reference.copy(deep=True)
    submitted["disagreement_pp"] = actual
    submitted.probability.values[0, 0, 0] += .00001
    submission = tmp_path / "submission"
    submission.mkdir()
    submitted.to_netcdf(submission / "objective.nc", engine="h5netcdf")
    result = check("acmad-objective", submission)
    assert result["check_results"]["disagreement"]["state"] == "pass"
    assert result["check_results"]["objective"]["state"] == "fail"
    assert "Maximum finite absolute error" in result["check_results"]["disagreement"]["detail"]
    assert result["completion"] == "incomplete_required_checks_failed"
