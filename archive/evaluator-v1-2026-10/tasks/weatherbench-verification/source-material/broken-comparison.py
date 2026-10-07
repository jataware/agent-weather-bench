"""Curator-created flawed comparison; not an upstream/historical WB2 bug.

Deliberately verifies at initialization, weights all grid cells equally, and
uses individual model availability. Real weather fields are never replaced.
"""
import argparse
from pathlib import Path
import json
import numpy as np
import xarray as xr


def score(inputs):
    inputs=Path(inputs)
    h=xr.load_dataset(inputs/"hres.nc")
    o=xr.load_dataset(inputs/"era5.nc").temperature.astype(float)
    c=xr.load_dataset(inputs/"climatology.nc").temperature.astype(float)
    a=xr.load_dataset(inputs/"availability.nc").available
    valid=h.init_time+h.lead_time
    truth=o.sel(time=h.init_time).drop_vars("time").broadcast_like(h.temperature)
    cl=c.sel(dayofyear=valid.dt.dayofyear,hour=valid.dt.hour).drop_vars(["dayofyear","hour"])
    predictions=xr.concat([h.temperature.astype(float).drop_vars("valid_time"),truth,cl],dim=xr.IndexVariable("system",["hres","persistence","climatology"]))
    errors=(predictions-truth)**2
    regions={"global":xr.ones_like(h.latitude,dtype=bool),"northern-extratropics":h.latitude>=30,"tropics":abs(h.latitude)<=20}
    result={}
    for region,mask in regions.items():
        per_case=errors.where((a==1)&mask).mean(("latitude","longitude"))
        rmse=np.sqrt(per_case.mean("init_time"))
        result[region]={str(s):rmse.sel(system=s).values.tolist() for s in rmse.system.values}
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--inputs",required=True)
    print(json.dumps(score(parser.parse_args().inputs),indent=2))
