"""Archived candidate experiment. Read alongside candidate-config.json and candidate-report.md."""
import argparse
from pathlib import Path
import numpy as np
import xarray as xr
from candidate_science import original, read

if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--inputs',required=True); parser.add_argument('--output',required=True)
    args=parser.parse_args(); p,t=read(args.inputs); values=original(args.inputs)
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    xr.Dataset({'rainfall':(('year','target'),values)},coords={'year':np.arange(2005,2020),'target':t.target.values}).to_netcdf(out/'candidate-hindcasts.nc')
    rmse=float(np.sqrt(np.mean((values-t.rainfall.sel(year=np.arange(2005,2020)).values)**2)))
    print(f'Candidate pooled RMSE: {rmse:.10f} mm')
