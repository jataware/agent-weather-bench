"""Prescribed regional rank calibration and conservative spatial detail adaptation."""
import numpy as np
import xarray as xr

RADIUS=6371000.0


def geometry(lat,lon):
    lat=np.asarray(lat);lon=np.asarray(lon)
    area=RADIUS**2*np.deg2rad(.05)*(np.sin(np.deg2rad(lat+.025))-np.sin(np.deg2rad(lat-.025)))[:,None]*np.ones((1,len(lon)))
    cell=(np.floor(lat-.5).astype(int)[:,None]*2+np.floor(lon-36.5).astype(int)[None,:])
    if set(np.unique(cell))!={0,1,2,3}:raise ValueError('Expected exactly four complete nominal one-degree cells')
    return area,cell


def aggregate(fine,area,cell):
    fine=np.asarray(fine,dtype=float)
    return np.stack([np.sum(fine[...,cell==c]*area[cell==c],axis=-1)/np.sum(area[cell==c]) for c in range(4)],axis=-1)


def map_value(value,training_x,training_y):
    ordered=np.argsort(training_x,kind='stable');xs=np.asarray(training_x)[ordered];ys=np.sort(training_y)
    unique,first,count=np.unique(xs,return_index=True,return_counts=True)
    averages=np.array([ys[i:i+n].mean() for i,n in zip(first,count)])
    return np.interp(value,unique,averages,left=averages[0],right=averages[-1])


def fit(raw,observed,area,cell):
    coarse=aggregate(observed,area,cell)
    climate=np.mean(observed,axis=0)
    coarse_climate=aggregate(climate,area,cell)
    if np.any(coarse_climate<=0):raise ValueError('No positive observed coarse climatology')
    ratio=np.zeros_like(climate)
    for c in range(4):ratio[cell==c]=climate[cell==c]/coarse_climate[c]
    return {'training_raw':np.asarray(raw).tolist(),'training_coarse_mm':coarse.tolist(),'fine_ratio':ratio.tolist()}


def infer(raw,state,cell):
    x=np.asarray(state['training_raw']);y=np.asarray(state['training_coarse_mm']);ratio=np.asarray(state['fine_ratio'])
    mapped=np.stack([map_value(np.asarray(raw)[:,c],x[:,c],y[:,c]) for c in range(4)],axis=-1)
    fine=mapped[:,cell]*ratio[None,:,:]
    return mapped,fine


def build(inputs):
    from pathlib import Path
    inputs=Path(inputs)
    with xr.open_dataset(inputs/'fine-training.nc') as f:training=f.load()
    with xr.open_dataset(inputs/'coarse-forecast.nc') as f:raw=f.load()
    area,cell=geometry(training.lat,training.lon)
    obs=training.seasonal_total.values
    x=raw.raw_predictor.sel(year=training.year).values
    state=fit(x,obs,area,cell)
    mapped,fine=infer(raw.raw_predictor.sel(year=slice(2009,None)).values,state,cell)
    forecast=xr.Dataset({'rainfall_mm':(('year','lat','lon'),fine),'mapped_coarse_mm':(('year','coarse_cell'),mapped),'area_m2':(('lat','lon'),area),'coarse_cell_id':(('lat','lon'),cell)},coords={'year':raw.year.sel(year=slice(2009,None)),'lat':training.lat,'lon':training.lon,'coarse_cell':range(4)})
    pp=[];cc=[]
    for i in range(len(obs)):
        keep=np.arange(len(obs))!=i
        st=fit(x[keep],obs[keep],area,cell);co,f=infer(x[i:i+1],st,cell);pp.append(f[0]);cc.append(co[0])
    hindcasts=xr.Dataset({'rainfall_mm':(('year','lat','lon'),np.array(pp)),'mapped_coarse_mm':(('year','coarse_cell'),np.array(cc))},coords={'year':training.year,'lat':training.lat,'lon':training.lon,'coarse_cell':range(4)})
    for ds in (forecast,hindcasts):
        for name in ('rainfall_mm','mapped_coarse_mm'):ds[name].attrs['units']='mm'
    forecast.area_m2.attrs['units']='m2'
    return forecast,hindcasts,state
