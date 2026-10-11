"""Vectorized physical integration; no controller imports, used by trusted controls."""
from pathlib import Path
import json
import numpy as np
import xarray as xr


def compute(inputs, params=None, conventions=None):
    inputs=Path(inputs)
    params=params or json.loads((inputs/'instance.json').read_text())
    conventions=conventions or {'integration':'duration_weighted','alignment':'valid_time'}
    with xr.open_zarr(inputs/'ECMWF_s2s_precip_2026-09-27.zarr',chunks=None,consolidated=False) as source:
        d=source.load()
    with xr.open_dataset(inputs/'previous-interval-rates.nc',engine='h5netcdf') as source:
        r=source.load()
    if d.tp.attrs['units']!='kg m**-2' or r.rain_rate.attrs['units']!='mm day-1':
        raise ValueError('Unexpected physical units')
    box=params['rectangle']; lat=np.sort(d.latitude.values[(d.latitude>=box['south'])&(d.latitude<=box['north'])]); lon=np.sort(d.longitude.values[(d.longitude>=box['west'])&(d.longitude<=box['east'])])
    d=d.sel(latitude=lat,longitude=lon);r=r.sel(lat=lat,lon=lon)
    valid=d.time.values+d.step.values
    bounds=r.time_bounds.values.astype('datetime64[ns]');day=np.timedelta64(1,'D')
    new=[];old=[]
    for label in params['period_start']:
        start=np.datetime64(label);end=start+7*day
        low=np.flatnonzero(valid==start);high=np.flatnonzero(valid==end)
        if len(low)!=1 or len(high)!=1:raise ValueError('Current endpoint absent')
        if conventions.get('negative_increments')=='clip_quantization':
            a=d.tp.diff('step').isel(step=slice(low[0],high[0])).clip(min=0).sum('step').mean('number').transpose('latitude','longitude').values
        else:
            a=(d.tp.isel(step=high[0])-d.tp.isel(step=low[0])).mean('number').transpose('latitude','longitude').values
        previous_start=start-7*day if conventions['alignment']=='same_lead' else start
        previous_end=previous_start+7*day
        selected=(bounds[:,0]>=previous_start)&(bounds[:,1]<=previous_end)
        if not selected.any() or bounds[selected,0].min()!=previous_start or bounds[selected,1].max()!=previous_end:raise ValueError('Previous period not fully covered')
        duration=((bounds[selected,1]-bounds[selected,0])/day).astype(float)
        if conventions['integration']=='sum_rates':duration=np.ones_like(duration)
        b=(r.rain_rate.isel(interval=np.flatnonzero(selected))*xr.DataArray(duration,dims='interval',coords={'interval':r.interval.values[selected]})).sum('interval').mean('member').transpose('lat','lon').values
        new.append(a);old.append(b)
    new=np.array(new);old=np.array(old);change=new-old;weights=np.cos(np.deg2rad(lat))[:,None]*np.ones((1,len(lon)))
    return {'period':np.array(params['period_start'],dtype=str),'latitude':lat,'longitude':lon,'current_mean_mm':new,'previous_mean_mm':old,'change_mm':change,'regional_change_mm':(change*weights).sum((1,2))/weights.sum()}
