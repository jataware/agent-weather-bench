"""Controller reference: literal bilinear weights and explicit station/time loops.

Station observations are NOAA ISD, never reanalysis. Forecast fields remain real;
availability masks and fault variants are explicitly constructed test conditions.
"""
from pathlib import Path
import csv
import json
import numpy as np
import xarray as xr
from scipy.interpolate import RegularGridInterpolator

METHODS = ["bilinear", "nearest"]
VARIANTS = ["correct", "init-time-truth", "celsius-as-kelvin", "own-support", "all-three"]
FIELDS = ["forecast_temperature", "observed_temperature", "common_support", "support_count", "station_count", "rmse", "station_rmse", "equal_station_rmse", "diagnostic_rmse"]
REPORT_PRIORITY = {"FM-12": 0, "FM-15": 1, "FM-16": 2}


def observations(inputs, times, station_ids):
    """Select an actual instantaneous report at exact UTC, with deterministic ties.

    Accept only TMP flags 1 or 5, reject +9999; prioritize FM-12 then FM-15,
    then FM-16 then others, and original retained source row order. No rounding,
    interpolation, daily averaging, temporal tolerance, or QC fabrication.
    """
    lookup = {}
    with (Path(inputs)/"observations.csv").open() as f:
        for row_index, r in enumerate(csv.DictReader(f)):
            value, flag = r["TMP"].split(",")
            if flag not in ("1", "5") or int(value) == 9999:
                continue
            key = (r["STATION"], np.datetime64(r["DATE"], "ns"))
            rank = (REPORT_PRIORITY.get(r["REPORT_TYPE"], 9), row_index)
            if key not in lookup or rank < lookup[key][0]:
                lookup[key] = (rank, int(value)/10.0 + 273.15)
    result = np.full(np.shape(times) + (len(station_ids),), np.nan)
    for ix in np.ndindex(np.shape(times)):
        for s, sid in enumerate(station_ids):
            if (sid, times[ix]) in lookup:
                result[ix+(s,)] = lookup[sid,times[ix]][1]
    return result


def load(inputs):
    inputs = Path(inputs)
    with xr.open_dataset(inputs/"hres.nc") as src:
        forecast = src.load()
    with xr.open_dataset(inputs/"availability.nc") as src:
        availability = src.load()
    stations = json.loads((inputs/"stations.json").read_text())
    init, lead, lat, lon = [forecast[k].values for k in ("init_time", "lead_time", "latitude", "longitude")]
    if forecast.temperature.attrs.get("units") != "K":
        raise ValueError("Forecast temperature must be K")
    valid = init[:,None] + lead[None,:]
    if not np.array_equal(valid,forecast.valid_time):
        raise ValueError("valid_time must equal init_time + lead_time")
    if not np.all(np.diff(lat)>0) or not np.all(np.diff(lon)>0):
        raise ValueError("Grid coordinates must increase")
    ids = [r["id"] for r in stations]
    available = availability.available.sel({"method":METHODS,"init_time":init,"lead_time":lead,"station":ids}).values
    if not np.isin(available,[0,1]).all():
        raise ValueError("Availability values must be 0 or 1")
    return forecast, stations, available.astype(bool), (init,lead,lat,lon,valid)


def interpolate(grid,lat,lon,stations):
    output = np.empty((len(METHODS),)+grid.shape[:2]+(len(stations),))
    for s, r in enumerate(stations):
        y,x = r["latitude"], r["longitude"] % 360
        if not lat[0] <= y <= lat[-1]:
            raise ValueError("Station outside bounded latitude domain")
        j = min(max(np.searchsorted(lat,y,side="right")-1,0),len(lat)-2)
        k = np.searchsorted(lon,x,side="right")-1
        k = k % len(lon); nextk = (k+1)%len(lon)
        left = lon[k]; right = lon[nextk] if nextk else lon[0]+360
        if x < left: x += 360
        wy,wx = (y-lat[j])/(lat[j+1]-lat[j]), (x-left)/(right-left)
        output[0,...,s] = ((1-wy)*(1-wx)*grid[...,j,k] + (1-wy)*wx*grid[...,j,nextk]
                          + wy*(1-wx)*grid[...,j+1,k] + wy*wx*grid[...,j+1,nextk])
        ny = int(np.argmin(abs(lat-y)))
        nx = int(np.argmin(abs((lon-x+180)%360-180)))
        output[1,...,s] = grid[...,ny,nx]
    return output


def build(inputs):
    forecast, stations, available, coords = load(inputs)
    init,lead,lat,lon,valid = coords
    ids = [r["id"] for r in stations]
    pred = interpolate(forecast.temperature.values.astype(float),lat,lon,stations)
    truth = observations(inputs,valid,ids)
    inittruth = np.broadcast_to(observations(inputs,init,ids)[:,None,:],truth.shape)
    own = available & np.isfinite(pred) & np.isfinite(truth)[None]
    common = own.all(axis=0)
    support_count = common.sum(axis=-1)
    station_count = common.sum(axis=0)
    rmse = np.full((2,len(lead)),np.nan)
    station_rmse = np.full((2,len(lead),len(ids)),np.nan)
    diagnostics = np.full((len(VARIANTS),2,len(lead)),np.nan)
    for m in range(2):
        for l in range(len(lead)):
            mask = common[:,l,:]
            e = (pred[m,:,l,:]-truth[:,l,:])**2
            if mask.any(): rmse[m,l] = np.sqrt(e[mask].mean())
            for s in range(len(ids)):
                ms = mask[:,s]
                if ms.any(): station_rmse[m,l,s] = np.sqrt(e[:,s][ms].mean())
            for vi,variant in enumerate(VARIANTS):
                target = inittruth[:,l,:] if variant in ("init-time-truth","all-three") else truth[:,l,:]
                if variant in ("celsius-as-kelvin","all-three"): target = target-273.15
                ms = own[m,:,l,:] if variant in ("own-support","all-three") else mask
                ms = ms & np.isfinite(target)
                if ms.any(): diagnostics[vi,m,l] = np.sqrt(((pred[m,:,l,:]-target)**2)[ms].mean())
    finite = np.isfinite(station_rmse)
    equal = np.sqrt(np.divide(np.where(finite,station_rmse**2,0).sum(axis=-1),finite.sum(axis=-1),
                              out=np.full(rmse.shape,np.nan),where=finite.sum(axis=-1)>0))
    return dataset(pred,truth,common,support_count,station_count,rmse,station_rmse,equal,diagnostics,coords,ids)


def dataset(pred,truth,common,count,station_count,rmse,station_rmse,equal,diagnostics,coords,ids):
    init,lead,lat,lon,valid = coords
    ds = xr.Dataset({
        "forecast_temperature":(("method","init_time","lead_time","station"),pred),
        "observed_temperature":(("init_time","lead_time","station"),truth),
        "common_support":(("init_time","lead_time","station"),common.astype(np.int8)),
        "support_count":(("init_time","lead_time"),count),
        "station_count":(("lead_time","station"),station_count),
        "rmse":(("method","lead_time"),rmse),
        "station_rmse":(("method","lead_time","station"),station_rmse),
        "equal_station_rmse":(("method","lead_time"),equal),
        "diagnostic_rmse":(("variant","method","lead_time"),diagnostics),
    },coords={"method":METHODS,"variant":VARIANTS,"init_time":init,"lead_time":lead,"station":ids,
              "valid_time":(("init_time","lead_time"),valid)})
    for k in FIELDS:
        ds[k].attrs["units"] = "1" if k=="common_support" else "station_samples" if k in ("support_count","station_count") else "K"
    ds.attrs.update(truth="NOAA ISD instantaneous air temperature",method_adaptation="WeatherReal station-verification concept; January 2020 adaptation",constructed_faults="true",published_rank_reproduction="false")
    return ds


def independent(inputs):
    """Independent parser, SciPy interpolation and labeled xarray reductions.

    Deliberately does not call observations(), interpolate(), or build().
    """
    forecast, stations, available, coords = load(inputs)
    init,lead,lat,lon,valid = coords
    ids = [r["id"] for r in stations]
    raw = list(csv.DictReader((Path(inputs)/"observations.csv").open()))
    accepted = {}
    for sid in ids:
        for time in np.unique(np.r_[valid.flatten(),init]):
            candidates = [(i,r) for i,r in enumerate(raw) if r["STATION"]==sid and np.datetime64(r["DATE"],"ns")==time
                          and r["TMP"].split(",")[1] in {"1","5"} and r["TMP"].split(",")[0] != "+9999"]
            if candidates:
                i,row = min(candidates,key=lambda ir:({"FM-12":0,"FM-15":1,"FM-16":2}.get(ir[1]["REPORT_TYPE"],9),ir[0]))
                accepted[sid,time] = float(row["TMP"].split(",")[0])*0.1+273.15
    truth = np.array([[[accepted.get((s,t),np.nan) for s in ids] for t in row] for row in valid])
    issue = np.array([[accepted.get((s,t),np.nan) for s in ids] for t in init])
    points = np.array([[s["latitude"],s["longitude"]%360] for s in stations])
    grid = forecast.temperature.values.astype(float)
    extended = np.concatenate([grid,grid[...,:1]],axis=-1)
    xlon = np.r_[lon,lon[0]+360]
    pred = np.empty((2,len(init),len(lead),len(ids)))
    for i in range(len(init)):
        for l in range(len(lead)):
            pred[0,i,l] = RegularGridInterpolator((lat,xlon),extended[i,l],method="linear")(points)
            pred[1,i,l] = RegularGridInterpolator((lat,xlon),extended[i,l],method="nearest")(points)
    dims = ("method","init_time","lead_time","station")
    crd = dict(method=METHODS,init_time=init,lead_time=lead,station=ids)
    p = xr.DataArray(pred,dims=dims,coords=crd)
    t = xr.DataArray(truth,dims=dims[1:],coords={k:v for k,v in crd.items() if k!="method"})
    own = xr.DataArray(available,dims=dims,coords=crd)&p.notnull()&t.notnull()
    common = own.all("method")
    e = (p-t)**2
    rmse = np.sqrt(e.where(common).mean(("init_time","station"))).values
    station = np.sqrt(e.where(common).mean("init_time")).values
    equal = np.sqrt((e.where(common).mean("init_time")).mean("station")).values
    diagnostics = []
    for variant in VARIANTS:
        target = xr.DataArray(np.broadcast_to(issue[:,None,:],truth.shape),dims=t.dims,coords=t.coords) if variant in ("init-time-truth","all-three") else t
        if variant in ("celsius-as-kelvin","all-three"): target=target-273.15
        mask = own if variant in ("own-support","all-three") else common
        diagnostics.append(np.sqrt(((p-target)**2).where(mask & target.notnull()).mean(("init_time","station"))).values)
    return dataset(pred,truth,common.values,common.sum("station").values,common.sum("init_time").values,
                   rmse,station,equal,np.array(diagnostics),coords,ids)
