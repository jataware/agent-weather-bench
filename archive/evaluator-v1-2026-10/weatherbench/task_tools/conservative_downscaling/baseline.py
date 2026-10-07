"""Executable correct mechanical control; prescribed scientific reference."""
import argparse,json
from pathlib import Path
import numpy as np,xarray as xr
try:from .reference import build,geometry,infer
except ImportError:from reference import build,geometry,infer


def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--outputs',type=Path,required=True);p.add_argument('--model',type=Path);a=p.parse_args();a.outputs.mkdir(parents=True,exist_ok=True)
    if a.model:
        state=json.loads(a.model.read_text())
        with xr.open_dataset(a.inputs/'coarse-forecast.nc') as f:raw=f.load()
        with xr.open_dataset(a.inputs/'geometry.nc') as f:grid=f.load()
        area,cell=geometry(grid.lat,grid.lon);co,fine=infer(raw.raw_predictor.sel(year=slice(2009,None)).values,state,cell)
        forecast=xr.Dataset({'rainfall_mm':(('year','lat','lon'),fine),'mapped_coarse_mm':(('year','coarse_cell'),co),'area_m2':(('lat','lon'),area),'coarse_cell_id':(('lat','lon'),cell)},coords={'year':raw.year.sel(year=slice(2009,None)),'lat':grid.lat,'lon':grid.lon,'coarse_cell':range(4)})
        for v in ('rainfall_mm','mapped_coarse_mm'):forecast[v].attrs['units']='mm'
        forecast.area_m2.attrs['units']='m2'
    else:
        forecast,hindcasts,state=build(a.inputs);hindcasts.to_netcdf(a.outputs/'hindcasts.nc');(a.outputs/'model.json').write_text(json.dumps(state)+'\n')
    forecast.to_netcdf(a.outputs/'forecast.nc')

if __name__=='__main__':main()
