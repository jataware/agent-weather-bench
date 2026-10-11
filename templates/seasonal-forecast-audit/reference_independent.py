"""Independent scalar-loop metric and cumulative-sum climatology implementation."""
import math
from pathlib import Path
import xarray as xr


def score(results,params,private,split='hindcast'):
    with xr.open_dataset(Path(private)/'agent-inputs/targets.nc') as ds:
        years=ds.year.values.tolist(); observed=ds.rainfall.values.tolist()
    errors=[];climate_errors=[]
    for k,year in enumerate(range(2005,2020)):
        idx=years.index(year)
        for cell in range(len(observed[0])):
            mean=math.fsum(observed[j][cell] for j in range(idx))/idx
            errors.append((float(results['hindcast_mm'][k,cell])-observed[idx][cell])**2)
            climate_errors.append((mean-observed[idx][cell])**2)
    rmse=math.sqrt(math.fsum(errors)/len(errors));baseline=math.sqrt(math.fsum(climate_errors)/len(errors))
    return {'split':split,'rmse_mm':rmse,'climatology_rmse_mm':baseline,'skill_vs_climatology':1-rmse/baseline,'years':15,'cells':len(observed[0])}


def original(inputs):
    """Independent primal normal-equation reconstruction, including all candidate defects."""
    import json
    import numpy as np
    root=Path(inputs)
    with xr.open_dataset(root/'predictors.nc') as ds: x=ds.sst.sel(year=np.arange(1993,2020)).values
    with xr.open_dataset(root/'targets.nc') as ds: y=ds.rainfall.values
    cfg=json.loads((root/'candidate-config.json').read_text())
    if cfg['select_scope']=='whole_record':
        strengths=[]
        for j in range(x.shape[1]):
            a=x[:,j]-np.mean(x[:,j]); values=[]
            for k in range(y.shape[1]):
                b=y[:,k]-np.mean(y[:,k]); values.append(float(np.dot(a,b)**2/(np.dot(a,a)*np.dot(b,b))))
            strengths.append(math.fsum(values)/len(values))
        best=max(range(len(strengths)),key=strengths.__getitem__);x=x[:,best:best+1]
    out=[]
    for n in range(12,27):
        mean=np.mean(x[:n],axis=0);scale=np.std(x[:n],axis=0);scale=np.where(scale<1e-10,1,scale)
        train=(x[:n]-mean)/scale;new=(x[n]-mean)/scale
        center=np.mean(y if cfg['centering_scope']=='whole_record' else y[:n],axis=0)
        beta=np.linalg.solve(train.T@train+np.eye(train.shape[1]),train.T@(y[:n]-center))
        out.append(np.maximum(center+new@beta,0))
    return np.asarray(out)
