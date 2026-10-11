"""Independent scalar integration using labelled lookup and Python math.fsum.

Does not import science.py or reference.py. Uses cumulative daily increments for
current totals instead of endpoint subtraction; integrates rate intervals by loops.
"""
from pathlib import Path
from math import fsum,cos,pi
import numpy as np
import xarray as xr


def reference(inputs,params,conventions):
    p=Path(inputs)
    with xr.open_zarr(p/'ECMWF_s2s_precip_2026-09-27.zarr',chunks=None,consolidated=False) as source:c=source.load()
    with xr.open_dataset(p/'previous-interval-rates.nc',engine='h5netcdf') as source:r=source.load()
    box=params['rectangle'];latitude=sorted(float(x) for x in c.latitude.values if box['south']<=x<=box['north']);longitude=sorted(float(x) for x in c.longitude.values if box['west']<=x<=box['east'])
    times=(c.time.values+c.step.values).astype('datetime64[D]');bounds=r.time_bounds.values.astype('datetime64[D]');out={key:[] for key in ('current_mean_mm','previous_mean_mm','change_mm','regional_change_mm')}
    for label in params['period_start']:
        start=np.datetime64(label,'D');end=start+np.timedelta64(7,'D');a=[];b=[]
        previous_start=start-np.timedelta64(7,'D') if conventions['alignment']=='same_lead' else start; previous_end=previous_start+np.timedelta64(7,'D')
        for lat in latitude:
            row_a=[];row_b=[]
            for lon in longitude:
                cv=c.tp.sel(latitude=lat,longitude=lon).transpose('number','step').values.astype(float)
                rv=r.rain_rate.sel(lat=lat,lon=lon).transpose('member','interval').values.astype(float)
                chosen=[i for i in range(1,len(times)) if start<times[i]<=end]
                old_chosen=[i for i,(s,e) in enumerate(bounds) if previous_start<=s and e<=previous_end]
                row_a.append(fsum(fsum((max(float(v[i])-float(v[i-1]),0) if conventions.get('negative_increments')=='clip_quantization' else float(v[i])-float(v[i-1])) for i in chosen) for v in cv)/len(cv))
                row_b.append(fsum(fsum(float(v[i])*(1 if conventions['integration']=='sum_rates' else int((bounds[i,1]-bounds[i,0])/np.timedelta64(1,'D'))) for i in old_chosen) for v in rv)/len(rv))
            a.append(row_a);b.append(row_b)
        change=np.array(a)-np.array(b);denom=fsum(cos(lat*pi/180) for lat in latitude)*len(longitude)
        out['current_mean_mm'].append(a);out['previous_mean_mm'].append(b);out['change_mm'].append(change);out['regional_change_mm'].append(fsum(float(change[i,j])*cos(lat*pi/180) for i,lat in enumerate(latitude) for j in range(len(longitude)))/denom)
    return {'period':np.array(params['period_start'],dtype=str),'latitude':np.array(latitude),'longitude':np.array(longitude),**{k:np.array(v) for k,v in out.items()}}
