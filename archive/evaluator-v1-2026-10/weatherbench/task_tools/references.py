"""Small independent references; no competing workflow-library imports."""
from pathlib import Path

import numpy as np
import xarray as xr

TERCILES = ["below", "near", "above"]
REGIONS = ["nino34", "west_equatorial", "west_north", "west_south"]
VARIANTS = ["paper_geometry", "existing_geometry"]
# south, north, west, east; longitudes use 0..360.
PAPER_BOXES = [(-5, 5, 190, 240), (-15, 15, 110, 140),
               (20, 35, 160, 200), (-30, -15, 155, 200)]
EXISTING_BOXES = [(-5, 5, 190, 240), (-15, 20, 120, 160),
                  (20, 35, 160, 210), (-30, -15, 155, 210)]


def load(path):
    path = Path(path)
    with path.open("rb") as stream:
        engine = "scipy" if stream.read(3) == b"CDF" else "h5netcdf"
    return xr.load_dataset(path, engine=engine)


def seasonal_training(forecast, observations):
    """Monthly inputs -> OND totals and native-cell CHIRPS means."""
    f = forecast.precip.transpose("init_time", "member", "lead_time", "lat", "lon")
    o = observations.precip.transpose("time", "lat", "lon")
    if f.attrs.get("units") not in ("mm/day", "mm day-1"):
        raise ValueError("Forecast rates must be in mm/day")
    if o.attrs.get("units") not in ("mm/month", "mm month-1"):
        raise ValueError("Observed monthly totals must be in mm/month")
    years = f.init_time.dt.year.values
    if len(np.unique(years)) != len(years) or not (f.init_time.dt.month == 9).all():
        raise ValueError("Need one September initialization per year")
    if not np.array_equal(f.lead_time, [2, 3, 4]):
        raise ValueError("Need ordered OND lead months 2,3,4")
    if not np.isfinite(f).all() or (f < 0).any():
        raise ValueError("Invalid forecast rates")
    dates = o.time.values.astype("datetime64[M]")
    expected_dates = np.array([f"{y}-{m:02}" for y in years for m in (10, 11, 12)],
                              dtype="datetime64[M]")
    if not np.array_equal(dates, expected_dates):
        raise ValueError("Observed months must exactly cover each OND")
    totals = (f.values * np.array([31., 30., 31.])[None, None, :, None, None]).sum(2)
    coarse = np.empty((len(dates), f.sizes["lat"], f.sizes["lon"]))
    for i, lat in enumerate(f.lat.values):
        for j, lon in enumerate(f.lon.values):
            iy = (o.lat.values >= lat - .5) & (o.lat.values < lat + .5)
            ix = (o.lon.values >= lon - .5) & (o.lon.values < lon + .5)
            if not iy.any() or not ix.any():
                raise ValueError("Empty observation cell")
            a = o.values[:, iy][:, :, ix]
            w = np.broadcast_to(np.cos(np.deg2rad(o.lat.values[iy]))[:, None], a.shape[1:])
            good = np.isfinite(a)
            mass = (w * good).sum((1, 2))
            if (mass / w.sum() < .9).any():
                raise ValueError("Observation valid area below 90 percent")
            coarse[:, i, j] = (np.where(good, a, 0) * w).sum((1, 2)) / mass
    ds = xr.Dataset({
        "forecast": (("year", "member", "lat", "lon"), totals),
        "observed": (("year", "lat", "lon"), coarse.reshape(len(years), 3, *coarse.shape[1:]).sum(1)),
    }, coords={"year": years, "member": f.member.values,
               "lat": f.lat.values, "lon": f.lon.values})
    for v in ds.data_vars:
        ds[v].attrs["units"] = "mm"
    return ds


def acmad_objective(components):
    """Combine available component distributions, retaining missing support."""
    first = components[0]
    arrays = []
    for ds in components:
        for coord in ("lat", "lon"):
            if not np.array_equal(ds[coord], first[coord]):
                raise ValueError("Component grids must agree exactly")
        # Promote native float32 products before unit conversion. Cancellation
        # after percent-to-fraction rounding otherwise fails valid pp differences.
        a = np.stack([ds[v].transpose("lat", "lon").values for v in ("below", "normal", "above")]).astype(np.float64)
        if np.isinf(a).any():
            raise ValueError("Infinite probabilities")
        partial = np.isfinite(a).any(0) & ~np.isfinite(a).all(0)
        if partial.any():
            raise ValueError("A component must provide all three categories or none")
        valid = np.isfinite(a).all(0)
        if ((a[:, valid] < 0) | (a[:, valid] > 100)).any():
            raise ValueError("Probabilities must be in percent")
        if not np.allclose(a[:, valid].sum(0), 100, atol=5e-5, rtol=0):
            raise ValueError("Component probabilities must sum to 100")
        arrays.append(a / 100)
    a = np.stack(arrays)
    valid = np.isfinite(a).all(1)
    count = valid.sum(0)
    numerator = np.where(valid[:, None], a, 0).sum(0)
    equal = np.divide(numerator, count[None], out=np.full_like(numerator, np.nan), where=count[None] > 0)
    equal /= equal.sum(0)[None]
    nominal = np.array([2., 8., 8.])[:, None, None] * valid
    numerator = np.where(valid[:, None], a, 0) * nominal[:, None]
    weighted = np.divide(numerator.sum(0), nominal.sum(0)[None],
                         out=np.full_like(equal, np.nan), where=nominal.sum(0)[None] > 0)
    weighted /= weighted.sum(0)[None]
    hi = np.where(valid[:, None], a, -np.inf).max(0)
    lo = np.where(valid[:, None], a, np.inf).min(0)
    disagreement = np.where(count[None] > 0, 100 * (hi - lo), np.nan)
    return xr.Dataset({
        "probability": (("tercile", "lat", "lon"), equal),
        "nominal_weighted_probability": (("tercile", "lat", "lon"), weighted),
        "available_components": (("lat", "lon"), count.astype(np.int32)),
        "disagreement_pp": (("tercile", "lat", "lon"), disagreement),
    }, coords={"tercile": TERCILES, "lat": first.lat.values, "lon": first.lon.values})


def wvg_audit(sst, baseline=(1981, 2010)):
    """Declared definition audit, not reproduction of the paper's forecast skill."""
    a = sst.sst.transpose("time", "lat", "lon")
    if a.attrs.get("units") != "degree_Celsius":
        raise ValueError("SST must have explicit Celsius metadata")
    dates = a.time.values.astype("datetime64[M]")
    if len(np.unique(dates)) != len(dates):
        raise ValueError("Duplicate months")
    years = np.unique(a.time.dt.year.values)
    if not np.array_equal(years, np.arange(years[0], years[-1] + 1)):
        raise ValueError("Missing years")
    means = np.empty((len(VARIANTS), len(years), len(REGIONS)))
    for v, boxes in enumerate((PAPER_BOXES, EXISTING_BOXES)):
        for r, (south, north, west, east) in enumerate(boxes):
            iy = (a.lat.values >= south) & (a.lat.values <= north)
            ix = (a.lon.values >= west) & (a.lon.values <= east)
            if not iy.any() or not ix.any():
                raise ValueError("Empty index box")
            field = a.values[:, iy][:, :, ix]
            weights = np.broadcast_to(np.cos(np.deg2rad(a.lat.values[iy]))[:, None], field.shape[1:])
            good = np.isfinite(field)
            mass = (weights * good).sum((1, 2))
            if np.isinf(field).any() or (mass <= 0).any():
                raise ValueError("Invalid SST support")
            monthly = (np.where(good, field, 0) * weights).sum((1, 2)) / mass
            for y, year in enumerate(years):
                required = np.array([f"{year}-{m:02}" for m in (3, 4, 5)], dtype="datetime64[M]")
                selected = np.isin(dates, required)
                if selected.sum() != 3:
                    raise ValueError("Need all three MAM months")
                means[v, y, r] = monthly[selected].mean()
    base = (years >= baseline[0]) & (years <= baseline[1])
    if base.sum() != baseline[1] - baseline[0] + 1 or base.sum() < 2:
        raise ValueError("Incomplete standardization baseline")
    western = means[:, :, 1:].mean(2)
    nino = means[0, :, 0]
    ns = nino[base].std(ddof=1)
    ws = western[:, base].std(1, ddof=1)
    if ns <= 0 or (ws <= 0).any():
        raise ValueError("Degenerate standardization")
    nz = (nino - nino[base].mean()) / ns
    wz = (western - western[:, base].mean(1)[:, None]) / ws[:, None]
    return xr.Dataset({
        "box_temperature_c": (("variant", "year", "region"), means),
        "western_v_c": (("variant", "year"), western),
        "nino34_z": (("year",), nz),
        "western_v_z": (("variant", "year"), wz),
        "wvg": (("variant", "year"), nz[None] - wz),
    }, coords={"variant": VARIANTS, "year": years, "region": REGIONS})


def same_array(actual, expected, atol=1e-6):
    """Exact coordinates, dimensions and missing mask; tolerant finite values."""
    if actual.dims != expected.dims or actual.shape != expected.shape:
        return False
    for dim in expected.dims:
        if dim not in actual.coords or not np.array_equal(actual[dim], expected[dim]):
            return False
    a, b = actual.values, expected.values
    if a.dtype.kind not in "iuf" or b.dtype.kind not in "iuf":
        return False
    if b.dtype.kind in "iu" and a.dtype.kind not in "iu":
        return False
    if np.isinf(a).any() or np.isinf(b).any() or not np.array_equal(np.isnan(a), np.isnan(b)):
        return False
    return bool(np.allclose(a, b, atol=atol, rtol=1e-6, equal_nan=True))
