"""NumPy component consolidation, independent of weather-tool implementations."""
from pathlib import Path
import numpy as np
import xarray as xr
NAMES = ['observed-sst.nc','forecast-sst.nc','forecast-precip.nc']
CATEGORIES = ['below','normal','above']


def load(provider):
    rows=[]; lat=lon=None
    for name in NAMES:
        with xr.open_dataset(Path(provider)/name,engine='h5netcdf') as ds:
            if lat is not None:
                if not np.array_equal(lat,ds.lat) or not np.array_equal(lon,ds.lon):
                    raise ValueError('Component grids differ')
            lat,lon=ds.lat.values,ds.lon.values
            rows.append(np.stack([ds[c].transpose('lat','lon').values for c in CATEGORIES]))
    return np.asarray(rows,dtype='float64')/100,lat,lon


def compute(provider, options=None):
    options=options or {}; p,lat,lon=load(provider)
    valid=np.isfinite(p).all(axis=1)
    # A component is an indivisible distribution: reject partial category vectors.
    masked=p.copy() if options.get('categorywise_fault') else np.where(valid[:,None],p,np.nan)
    counts=valid.sum(axis=0)
    if options.get('missing_support')=='climatology_fill':
        masked=np.where(valid[:,None],p,1/3)
        denom=np.full_like(counts,3)
    else:
        denom=counts
    weights=np.asarray([2,8,8],dtype='float64')[:,None,None,None]
    sums=np.nansum(masked,axis=0)
    objective=np.divide(sums,denom[None],out=np.full_like(sums,np.nan),where=denom[None]>0)
    def normalize(a):
        den=a.sum(axis=0)
        return np.divide(a,den[None],out=np.full_like(a,np.nan),where=den[None]>0)
    if options.get('categorywise_fault'):
        per_category=np.isfinite(masked).sum(axis=0)
        objective=np.divide(sums,per_category,out=np.full_like(sums,np.nan),where=per_category>0)
    objective=normalize(objective)
    weighted=np.nansum(masked*weights,axis=0)
    if options.get('categorywise_fault'):
        per_category_weight=np.sum(np.isfinite(masked)*weights,axis=0)
        weighted=np.divide(weighted,per_category_weight,out=np.full_like(weighted,np.nan),where=per_category_weight>0)
    weighted=normalize(weighted)
    if options.get('weighting')=='nominal':
        objective=weighted.copy()
    maximum=np.max(np.where(np.isfinite(masked),masked,-np.inf),axis=0)
    minimum=np.min(np.where(np.isfinite(masked),masked,np.inf),axis=0)
    disagreement=np.where(counts[None]>0,(maximum-minimum)*100,np.nan)
    if options.get('unit_fault'):
        objective*=100; weighted*=100
    # Explicit finite storage fill: available_components==0 means no forecast.
    objective=np.nan_to_num(objective,nan=0.); weighted=np.nan_to_num(weighted,nan=0.); disagreement=np.nan_to_num(disagreement,nan=0.)
    return xr.Dataset({'probability':(('tercile','lat','lon'),objective),
        'nominal_weighted_probability':(('tercile','lat','lon'),weighted),
        'available_components':(('lat','lon'),counts),
        'disagreement_pp':(('tercile','lat','lon'),disagreement)},
        coords={'tercile':[0,1,2],'lat':lat,'lon':lon})
