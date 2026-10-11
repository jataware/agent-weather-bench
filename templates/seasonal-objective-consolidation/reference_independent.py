"""Separate scalar complete-vector selection, summation and normalisation."""
from math import fsum,isfinite
from pathlib import Path
import numpy as np
import xarray as xr


def compute(provider,options=None):
    options=options or {}; rows=[]; previous=None
    for name in ['observed-sst.nc','forecast-sst.nc','forecast-precip.nc']:
        with xr.open_dataset(Path(provider)/name,engine='h5netcdf') as ds:
            current=(np.asarray(ds.lat),np.asarray(ds.lon))
            if previous is not None and any(not np.array_equal(a,b) for a,b in zip(previous,current)):
                raise ValueError('Scalar source grids differ')
            previous=current
            rows.append(np.stack([np.asarray(ds[c].transpose('lat','lon')) for c in ['below','normal','above']],axis=-1).reshape(-1,3))
            lat,lon=ds.lat.values,ds.lon.values
    # Positional scalar loops avoid vectorized masking/reductions in implementation A.
    shape=(3,len(lat),len(lon)); objective=np.full(shape,np.nan); weighted=objective.copy(); disagree=objective.copy(); count=np.zeros(shape[1:],dtype='int64')
    for j,y in enumerate(lat):
        for k,x in enumerate(lon):
            flat=j*len(lon)+k
            good=[(i,[float(v)/100 for v in row[flat]]) for i,row in enumerate(rows) if all(isfinite(v) for v in row[flat])]
            count[j,k]=len(good)
            vectors=good
            if options.get('missing_support')=='climatology_fill':
                present={i for i,_ in good}
                vectors=good+[(i,[1/3]*3) for i in range(3) if i not in present]
            if vectors:
                a=[fsum(v[c] for _,v in vectors)/len(vectors) for c in range(3)]
                b=[fsum([2,8,8][i]*v[c] for i,v in vectors) for c in range(3)]
                a=[v/fsum(a) for v in a]; b=[v/fsum(b) for v in b]
                objective[:,j,k]=b if options.get('weighting')=='nominal' else a
                weighted[:,j,k]=b
            if good:
                for c in range(3):
                    values=[v[c] for _,v in vectors]
                    disagree[c,j,k]=(max(values)-min(values))*100
    objective=np.nan_to_num(objective,nan=0.);weighted=np.nan_to_num(weighted,nan=0.);disagree=np.nan_to_num(disagree,nan=0.)
    return xr.Dataset({'probability':(('tercile','lat','lon'),objective),
        'nominal_weighted_probability':(('tercile','lat','lon'),weighted),
        'available_components':(('lat','lon'),count),
        'disagreement_pp':(('tercile','lat','lon'),disagree)},coords={'tercile':[0,1,2],'lat':lat,'lon':lon})
