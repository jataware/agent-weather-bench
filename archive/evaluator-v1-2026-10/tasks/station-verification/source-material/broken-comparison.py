"""Deliberately constructed faults, not upstream WeatherReal or NOAA code.

This fragment compares at issue time, forgets Celsius-to-Kelvin conversion,
and uses method-specific support. Repair independently; don't import controller.
The supplied prompt specifies station report ties and grid interpolation.
"""
import csv
import json
from pathlib import Path
import numpy as np
import xarray as xr


def score(input_dir, interpolated):
    input_dir=Path(input_dir)
    stations=json.loads((input_dir/"stations.json").read_text())
    with xr.open_dataset(input_dir/"hres.nc") as f:
        init=f.init_time.values;lead=f.lead_time.values
    reports={}
    priority={"FM-12":0,"FM-15":1,"FM-16":2}
    with (input_dir/"observations.csv").open() as f:
        for i,r in enumerate(csv.DictReader(f)):
            v,q=r["TMP"].split(",")
            if q not in ("1","5") or int(v)==9999:continue
            key=(r["STATION"],np.datetime64(r["DATE"],"ns"));rank=(priority.get(r["REPORT_TYPE"],9),i)
            if key not in reports or rank<reports[key][0]:reports[key]=(rank,int(v)/10)
    target=np.array([[reports.get((s["id"],t),(None,np.nan))[1] for s in stations] for t in init])
    with xr.open_dataset(input_dir/"availability.nc") as a:own=a.available.values.astype(bool)
    valid_times=init[:,None]+lead[None,:]
    valid_exists=np.array([[[ (s["id"],t) in reports for s in stations] for t in row] for row in valid_times])
    result=np.full((2,len(lead)),np.nan)
    for method in range(2):
        for l in range(len(lead)):
            mask=own[method,:,l]&valid_exists[:,l]&np.isfinite(target)&np.isfinite(interpolated[method,:,l])
            if mask.any():result[method,l]=np.sqrt(((interpolated[method,:,l]-target)**2)[mask].mean())
    return result
