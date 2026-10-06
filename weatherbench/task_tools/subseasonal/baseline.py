"""Small reproducible train-only seasonal climatology and affine bias correction.

Standalone supplied baseline: python baseline.py --inputs inputs --outputs outputs
Saved inference: python baseline.py --inputs inputs --outputs outputs --model model.json
"""
import argparse,json
from pathlib import Path
import numpy as np
import xarray as xr


def design(ds):
    day=ds.issue_time.dt.dayofyear.values
    angle=2*np.pi*(day+14)/365.25
    return np.column_stack([np.ones(len(day)),np.sin(angle),np.cos(angle),np.sin(2*angle),np.cos(2*angle)])


def fit(train):
    x=design(train); y=train.precipitation.values
    climate=np.linalg.lstsq(x,y,rcond=None)[0]
    # Six parameters/location: intercept + annual/semiannual terms + raw CFSv2.
    bias=np.stack([np.linalg.lstsq(np.column_stack([x,train.raw_cfsv2.values[:,i]]),y[:,i],rcond=None)[0] for i in range(y.shape[1])])
    return {'schema_version':1,'climatology':climate.tolist(),'bias':bias.tolist(),'locations':train.location.values.tolist(),'latitude':train.latitude.values.tolist(),'longitude':train.longitude.values.tolist()}


def predict(ds,state,method='bias'):
    if ds.location.values.tolist()!=state['locations'] or ds.latitude.values.tolist()!=state['latitude'] or ds.longitude.values.tolist()!=state['longitude']:
        raise ValueError('Fitted grid differs')
    x=design(ds)
    if method=='climatology':values=x@np.asarray(state['climatology'])
    elif method=='raw_cfsv2':values=ds.raw_cfsv2.values
    else:
        coefficient=np.asarray(state['bias']);values=x@coefficient[:,:5].T+ds.raw_cfsv2.values*coefficient[:,5][None,:]
    out=xr.Dataset({'precipitation':(('issue_time','location'),np.maximum(values,0))},coords=ds.coords)
    out.precipitation.attrs['units']='mm'
    return out


def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--outputs',type=Path,required=True);p.add_argument('--model',type=Path);p.add_argument('--method',choices=['bias','climatology','raw_cfsv2'],default='bias');a=p.parse_args()
    a.outputs.mkdir(parents=True,exist_ok=True)
    if a.model:state=json.loads(a.model.read_text())
    else:
        with xr.open_dataset(a.inputs/'training.nc') as ds:state=fit(ds.load())
    (a.outputs/'model.json').write_text(json.dumps(state,indent=2)+'\n')
    for split in ('development','final'):
        with xr.open_dataset(a.inputs/f'{split}-features.nc') as ds:out=predict(ds.load(),state,a.method)
        out.to_netcdf(a.outputs/f'{split}-predictions.nc')
    if not a.model:
        with xr.open_dataset(a.inputs/'training.nc') as ds:
            truth=ds.precipitation.values;guess=predict(ds.load(),state,a.method).precipitation.values
        answer={'task':'subseasonal-optimization','method':a.method,'training_rmse_mm':float(np.sqrt(np.mean((truth-guess)**2))), 'development_skill_claim':'Not measured: request score_development; local training score is resubstitution.', 'final_skill_claim':'Not measured: controller-only outcomes.'}
        (a.outputs/'answer.json').write_text(json.dumps(answer,indent=2)+'\n')

if __name__=='__main__':main()
