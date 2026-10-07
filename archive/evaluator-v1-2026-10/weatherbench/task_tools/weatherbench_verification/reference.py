"""Independent NumPy controller scorer for compact real WeatherBench2 fields."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import xarray as xr

SYSTEMS = ["hres", "persistence", "climatology"]
REGIONS = ["global", "northern-extratropics", "tropics"]
VARIANTS = ["correct", "init-time-truth", "uniform-weight", "own-support", "all-three"]


def load_fields(inputs):
    inputs = Path(inputs)
    with xr.open_dataset(inputs / "hres.nc") as f:
        f = f.load()
    with xr.open_dataset(inputs / "era5.nc") as obs:
        obs = obs.load()
    with xr.open_dataset(inputs / "climatology.nc") as clim:
        clim = clim.load()
    with xr.open_dataset(inputs / "availability.nc") as av:
        av = av.load()
    init, lead, lat, lon = [f[x].values for x in ("init_time", "lead_time", "latitude", "longitude")]
    valid = init[:, None] + lead[None, :]
    if not np.array_equal(valid, f.valid_time.values):
        raise ValueError("Source valid time does not equal init plus lead")
    truth = obs.temperature.sel(time=xr.DataArray(valid, dims=("init_time", "lead_time"))).values.astype(float)
    persistence = obs.temperature.sel(time=xr.DataArray(init, dims="init_time")).values.astype(float)
    persistence = np.broadcast_to(persistence[:, None], truth.shape)
    stamp = xr.DataArray(valid, dims=("init_time", "lead_time"))
    climatology = clim.temperature.sel(hour=stamp.dt.hour, dayofyear=stamp.dt.dayofyear).values.astype(float)
    forecasts = np.stack([f.temperature.values.astype(float), persistence, climatology])
    availability = av.available.sel(system=SYSTEMS, init_time=init, lead_time=lead, latitude=lat, longitude=lon).values.astype(bool)
    return forecasts, truth, persistence, climatology, availability, (init, lead, lat, lon, valid)


def area_weights(lat):
    rad = np.deg2rad(lat)
    if not np.all(np.diff(rad) > 0):
        raise ValueError("Latitude must increase")
    bounds = np.r_[-np.pi/2, (rad[:-1] + rad[1:])/2, np.pi/2]
    return np.diff(np.sin(bounds))


def build(inputs):
    forecasts, truth, persistence, clim, availability, coords = load_fields(inputs)
    init, lead, lat, lon, valid = coords
    finite = np.isfinite(forecasts) & np.isfinite(truth)[None] & np.isfinite(clim)[None]
    availability &= finite
    common = availability.all(axis=0)
    areas = np.broadcast_to(area_weights(lat)[:, None], (len(lat), len(lon)))
    region_masks = [np.ones_like(areas, dtype=bool), np.broadcast_to((lat >= 30)[:, None], areas.shape), np.broadcast_to((abs(lat) <= 20)[:, None], areas.shape)]
    shape = (len(SYSTEMS), len(REGIONS), len(init), len(lead))
    mse, acc = np.empty(shape), np.full(shape, np.nan)
    support = np.empty((len(REGIONS), len(init), len(lead)), dtype=int)
    fraction = np.empty_like(support, dtype=float)
    diagnostics = np.empty((len(VARIANTS), len(SYSTEMS), len(REGIONS), len(lead)))
    for ri, region in enumerate(region_masks):
        mask = common & region
        weights = mask * areas
        denom = weights.sum(axis=(-2, -1))
        support[ri] = mask.sum(axis=(-2, -1))
        fraction[ri] = denom / areas[region].sum()
        for si, pred in enumerate(forecasts):
            errors = (pred - truth)**2
            mse[si, ri] = np.where(mask, errors * areas, 0).sum(axis=(-2,-1)) / denom
            fa, ta = pred-clim, truth-clim
            numerator = np.where(mask, fa*ta*areas, 0).sum(axis=(-2,-1))
            norm = np.sqrt(np.where(mask, fa*fa*areas, 0).sum(axis=(-2,-1)) * np.where(mask, ta*ta*areas, 0).sum(axis=(-2,-1)))
            acc[si, ri] = np.divide(numerator, norm, out=np.full_like(norm,np.nan), where=norm>0)
            for vi, variant in enumerate(VARIANTS):
                own = variant in ("own-support", "all-three")
                uniform = variant in ("uniform-weight", "all-three")
                wrong_time = variant in ("init-time-truth", "all-three")
                m = (availability[si] if own else common) & region
                w = np.ones_like(areas) if uniform else areas
                target = persistence if wrong_time else truth
                per_case = np.where(m, (pred-target)**2*w, 0).sum(axis=(-2,-1)) / (m*w).sum(axis=(-2,-1))
                diagnostics[vi,si,ri] = np.sqrt(per_case.mean(axis=0))
    # Climatology's anomaly is exactly zero, so ACC is undefined, never 0 or 1.
    mean_acc = np.full((len(SYSTEMS),len(REGIONS),len(lead)),np.nan)
    mean_acc[:2] = acc[:2].mean(axis=2)
    result = xr.Dataset({
        "case_mse": (("system","region","init_time","lead_time"), mse),
        "case_acc": (("system","region","init_time","lead_time"), acc),
        "rmse": (("system","region","lead_time"), np.sqrt(mse.mean(axis=2))),
        "acc": (("system","region","lead_time"), mean_acc),
        "support_count": (("region","init_time","lead_time"), support),
        "support_area_fraction": (("region","init_time","lead_time"), fraction),
        "diagnostic_rmse": (("variant","system","region","lead_time"), diagnostics),
    },coords={"system":SYSTEMS,"region":REGIONS,"init_time":init,"lead_time":lead,"variant":VARIANTS,
              "valid_time":(("init_time","lead_time"),valid)})
    for k in ("rmse","diagnostic_rmse"):
        result[k].attrs["units"] = "K"
    result.case_mse.attrs["units"] = "K2"
    for k in ("acc","case_acc","support_area_fraction"):
        result[k].attrs["units"] = "1"
    result.support_count.attrs["units"] = "grid_cells"
    return result


def independent(inputs):
    """Separate xarray labeled selection/reduction crosscheck.

    Uses cos(latitude), proportional to exact area on this equal-spacing,
    no-pole grid. It independently builds valid-time indexes and support.
    """
    inputs = Path(inputs)
    f = xr.load_dataset(inputs/"hres.nc")
    o = xr.load_dataset(inputs/"era5.nc").temperature.astype(float)
    c = xr.load_dataset(inputs/"climatology.nc").temperature.astype(float)
    a = xr.load_dataset(inputs/"availability.nc").available.astype(bool)
    valid = f.init_time + f.lead_time
    y = o.sel(time=valid).drop_vars("time")
    p = o.sel(time=f.init_time).drop_vars("time").broadcast_like(y)
    cl = c.sel(dayofyear=valid.dt.dayofyear,hour=valid.dt.hour).drop_vars(["dayofyear","hour"])
    predictions = xr.concat([f.temperature.astype(float).drop_vars("valid_time"),p,cl],dim=xr.IndexVariable("system",SYSTEMS))
    common = (a & predictions.notnull() & y.notnull() & cl.notnull()).all("system")
    weights = np.cos(np.deg2rad(f.latitude))
    result=[]
    masks=[xr.ones_like(f.latitude,dtype=bool),f.latitude>=30,abs(f.latitude)<=20]
    for region,mask in zip(REGIONS,masks):
        use=common & mask
        err=(predictions-y)**2
        ms=err.where(use).weighted(weights).mean(("latitude","longitude"))
        fa,ta=(predictions-cl).where(use),(y-cl).where(use)
        cov=(fa*ta).weighted(weights).mean(("latitude","longitude"))
        norm=np.sqrt((fa**2).weighted(weights).mean(("latitude","longitude"))*(ta**2).weighted(weights).mean(("latitude","longitude")))
        ac=xr.where(norm>0,cov/norm,np.nan)
        part=xr.Dataset({"case_mse":ms,"case_acc":ac,"rmse":np.sqrt(ms.mean("init_time")),"acc":ac.mean("init_time",skipna=False)})
        result.append(part.expand_dims(region=[region]))
    return xr.concat(result,dim="region")
