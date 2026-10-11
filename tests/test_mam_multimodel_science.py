"""Scientific contract tests, independent of acquisition and model attempts."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest
import xarray as xr

HERE = Path(__file__).resolve().parents[1] / "templates/mam-multimodel-outlook"


def module(name):
    spec = importlib.util.spec_from_file_location("mam_" + name, HERE / (name + ".py"))
    out = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(out)
    return out


@pytest.fixture
def fixture():
    rng = np.random.default_rng(1493)
    years = list(range(1993, 2001))
    y = rng.uniform(100, 700, size=(len(years), 2, 2))
    h, f = {}, {}
    for i, members in enumerate((2, 7, 3, 5)):
        mean = 100 + (0.3 + i / 4) * y + rng.normal(0, 80 + 20 * i, size=y.shape)
        h[str(i)] = mean[:, None] + rng.normal(0, 20, size=(len(years), members, 2, 2))
        f[str(i)] = rng.uniform(100, 800, size=(1, members, 2, 2))
    return h, y, f, years, [2001], [-2.0, 0.0], [35.0, 37.0]


def test_independent_scalar_reference_matches_all_arrays_and_rps(fixture):
    a, b = module("science").evaluate(*fixture), module("reference_independent").evaluate(*fixture)
    for name in a.data_vars:
        np.testing.assert_allclose(a[name], b[name], rtol=2e-13, atol=2e-12, err_msg=name)
    assert a.cv_rps_climatology.item() > 0
    assert a.cv_rpss.item() == pytest.approx(1 - a.cv_rps.item() / a.cv_rps_climatology.item())


@pytest.mark.parametrize("thresholds", ["fold_only", "full_record_thresholds"])
@pytest.mark.parametrize("weighting", ["equal_models", "member_weighted"])
@pytest.mark.parametrize("integration,scale", [("calendar", 1.0), ("thirty_days", 90 / 92), ("missing_seconds", 1 / 86400), ("missing_millimetres", 1 / 1000)])
def test_independent_reference_reconstructs_joint_pitfall_readings(fixture, thresholds, weighting, integration, scale):
    axes = {"integration": integration, "thresholds": thresholds, "weighting": weighting}
    h, y, f, *tail = fixture
    args = ({name: value * scale for name, value in h.items()}, y, {name: value * scale for name, value in f.items()}, *tail)
    a = module("science").evaluate(*args, defect=axes)
    b = module("reference_independent").evaluate(*args, defect=axes)
    for name in a.data_vars:
        np.testing.assert_allclose(a[name], b[name], rtol=2e-13, atol=2e-12, err_msg=name)


def test_equal_model_weighting_is_invariant_to_member_replication(fixture):
    s = module("science")
    a = s.evaluate(*fixture)
    h, y, f, *tail = fixture
    enlarged_h = {**h, "0": np.repeat(h["0"], 9, axis=1)}
    enlarged_f = {**f, "0": np.repeat(f["0"], 9, axis=1)}
    b = s.evaluate(enlarged_h, y, enlarged_f, *tail)
    np.testing.assert_allclose(a.forecast_probability, b.forecast_probability, rtol=0, atol=2e-15)
    wrong = s.evaluate(*fixture, defect="member_weighted")
    assert np.max(np.abs(a.forecast_probability.values - wrong.forecast_probability.values)) > 0.01


def test_heldout_target_never_enters_its_fit_or_thresholds(fixture):
    s = module("science")
    h, y, f, *tail = fixture
    changed = y.copy()
    changed[3] += 10000
    a, b = s.evaluate(*fixture), s.evaluate(h, changed, f, *tail)
    np.testing.assert_array_equal(a.model_hindcast_probability.isel(year=3), b.model_hindcast_probability.isel(year=3))
    assert np.max(np.abs(a.model_hindcast_probability.isel(year=0).values - b.model_hindcast_probability.isel(year=0).values)) > 0.01
    wrong_a = s.evaluate(*fixture, defect="full_record_thresholds")
    wrong_b = s.evaluate(h, changed, f, *tail, defect="full_record_thresholds")
    assert np.max(np.abs(wrong_a.model_hindcast_probability.isel(year=3).values - wrong_b.model_hindcast_probability.isel(year=3).values)) > 0.01


@pytest.mark.parametrize("time_name", ["forecast_reference_time", "indexing_time"])
def test_native_monthly_rates_use_valid_month_actual_days_and_physical_units(time_name):
    s, independent = module("science"), module("reference_independent")
    values = np.array([1, 4, 9], dtype=float)[None, :, None, None, None] * np.ones((1, 3, 2, 2, 2)) * 1e-8
    ds = xr.Dataset({"tprate": ((time_name, "forecastMonth", "number", "latitude", "longitude"), values, {"units": "m s**-1"})}, coords={time_name: [np.datetime64("2000-02-01")], "forecastMonth": [2, 3, 4], "number": [0, 1], "latitude": [1.0, -1.0], "longitude": [34.0, 38.0]})
    a = s.seasonal_model(ds, [2000], [-0.5, 0.5], [35.0, 37.0])
    expected = (31 * 1 + 30 * 4 + 31 * 9) * 1e-8 * 86400 * 1000
    np.testing.assert_allclose(a, expected, rtol=0, atol=1e-12)
    np.testing.assert_allclose(a, independent.seasonal_model(ds, [2000], [-0.5, 0.5], [35.0, 37.0]), rtol=0, atol=1e-12)
    for defect in ("thirty_days", "missing_seconds", "missing_millimetres"):
        np.testing.assert_allclose(s.seasonal_model(ds, [2000], [-0.5, 0.5], [35.0, 37.0], defect=defect), independent.seasonal_model(ds, [2000], [-0.5, 0.5], [35.0, 37.0], defect=defect), rtol=2e-15, atol=1e-12)
    assert s.seasonal_model(ds, [2000], defect="thirty_days").mean().item() != pytest.approx(expected)
    assert s.seasonal_model(ds, [2000], defect="missing_seconds").mean().item() == pytest.approx(expected / 86400)
    assert s.seasonal_model(ds, [2000], defect="missing_millimetres").mean().item() == pytest.approx(expected / 1000)
    bad_units = ds.copy(deep=True)
    bad_units.tprate.attrs["units"] = "mm/day"
    with pytest.raises(ValueError, match="m/s"):
        s.seasonal_model(bad_units, [2000])
    with pytest.raises(ValueError, match="valid"):
        s.seasonal_model(ds.assign_coords(forecastMonth=[1, 2, 3]), [2000])


def test_observed_monthly_totals_and_bilinear_interpolation_are_independent():
    s, b = module("science"), module("reference_independent")
    lat, lon = np.array([-1.0, 1.0]), np.array([34.0, 38.0])
    rain = np.stack([month + 3 * lat[:, None] + 2 * lon[None, :] for month in (3, 4, 5)])
    ds = xr.Dataset({"precip": (("time", "latitude", "longitude"), rain, {"units": "mm/month"})}, coords={"time": np.array(["2000-03-01", "2000-04-01", "2000-05-01"], dtype="datetime64[D]"), "latitude": lat, "longitude": lon})
    a = s.seasonal_observed(ds, [2000], [-0.5, 0.5], [35.0, 37.0])
    np.testing.assert_allclose(a, b.seasonal_observed(ds, [2000], [-0.5, 0.5], [35.0, 37.0]), atol=1e-12)
    np.testing.assert_allclose(a[0], 12 + 9 * np.array([-0.5, 0.5])[:, None] + 6 * np.array([35.0, 37.0])[None, :])
    with pytest.raises(ValueError, match="finite"):
        s.seasonal_observed(ds, [2000], [-2.0, 0.0], [35.0, 37.0])


def test_category_ties_and_zero_residual_variance_have_defined_behavior():
    s = module("science")
    np.testing.assert_array_equal(s.category(np.array([9, 10, 20, 21]), np.array([10, 20])[:, None]), [0, 1, 1, 2])
    p, _ = s.gaussian_terciles(np.arange(5.0)[:, None, None], (2 + 3 * np.arange(5.0))[:, None, None], np.array([[2.0]]))
    np.testing.assert_allclose(p.sum(axis=0), 1)
    assert p[1, 0, 0] > 0.999999
    with pytest.raises(ValueError, match="Constant"):
        s.gaussian_terciles(np.ones((5, 1, 1)), np.arange(5.0)[:, None, None], np.ones((1, 1)))
