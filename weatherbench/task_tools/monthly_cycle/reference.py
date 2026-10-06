"""Controller-only deterministic monthly regression with cyclic regularization."""
from pathlib import Path
import json
import numpy as np
import xarray as xr

LAMBDAS=(0.,.25,1.,4.,16.,64.)
SYSTEMS=['climatology','independent-month','constant-slope','nested-cyclic']

def smooth(raw,lam,backend='solve'):
    if lam=='constant':return np.broadcast_to(raw.mean(0),raw.shape).copy()
    if backend=='solve':
        lap=2*np.eye(12)-np.roll(np.eye(12),1,axis=0)-np.roll(np.eye(12),-1,axis=0)
        return np.linalg.solve(np.eye(12)+lam*lap,raw)
    frequency=2-2*np.cos(2*np.pi*np.arange(12)/12)
    return np.fft.ifft(np.fft.fft(raw,axis=0)/(1+lam*frequency[:,None]),axis=0).real

def fit(x,y,lam,backend='solve'):
    xm,ym=x.mean(0),y.mean(0);xs,ys=x.std(0,ddof=1),y.std(0,ddof=1)
    if np.min(xs)<=0 or np.min(ys)<=0:raise ValueError('Constant monthly support cannot be standardized')
    zx=(x-xm)/xs;zy=(y-ym)/ys
    if backend=='solve':raw=np.einsum('ym,ymt->mt',zx,zy)/(len(x)-1)
    else:
        # Separate scalar covariance implementation for each month and target.
        raw=np.array([[sum((x[i,m]-xm[m])*(y[i,m,j]-ym[m,j]) for i in range(len(x)))/((len(x)-1)*xs[m]*ys[m,j]) for j in range(y.shape[2])] for m in range(12)])
    beta=smooth(raw,lam,backend)
    return {'xmean':xm,'xstd':xs,'ymean':ym,'ystd':ys,'standardized_coefficient':beta,'physical_coefficient':beta*ys/xs[:,None],'lambda':lam,'n':len(x)}

def predict(state,new):return state['ymean'][None,:,:]+state['physical_coefficient'][None,:,:]*(new-state['xmean'])[...,None]

def select(x,y,years,weights,backend='solve'):
    losses=[]
    for lam in LAMBDAS:
        rows=[]
        for i in np.where(years>=2001)[0]:
            keep=years<years[i];s=fit(x[keep],y[keep],lam,backend)
            error=(predict(s,x[i:i+1])[0]-y[i])/s['ystd']
            rows.append(np.mean(np.sum(error**2*weights[None,:],axis=-1)))
        losses.append(np.mean(rows))
    return int(np.argmin(losses)),np.array(losses)

def load(inputs):
    with xr.open_dataset(Path(inputs)/'predictors.nc') as ds:x=ds.load()
    with xr.open_dataset(Path(inputs)/'targets.nc') as ds:y=ds.load()
    return x,y

def month_only_fit(x,y,heldx,heldy,lam,backend):
    # Plausible defect: exclude only the month being predicted, keeping all eleven
    # other target months of the held year in the cyclic smoother's other slopes.
    result=fit(x,y,lam,backend);betas=[];physical=[]
    for m in range(12):
        xx=np.concatenate([x,heldx[None]],axis=0);yy=np.concatenate([y,heldy[None]],axis=0)
        # Duplicate training means in the held month's row rather than including
        # its target; calculate moments for this month from genuine train alone.
        full=fit(xx,yy,0,backend);base=fit(x,y,0,backend)
        raw=full['standardized_coefficient'];raw[m]=base['standardized_coefficient'][m]
        beta=smooth(raw,lam,backend)[m];betas.append(beta)
        physical.append(beta*base['ystd'][m]/base['xstd'][m])
    result['standardized_coefficient']=np.array(betas);result['physical_coefficient']=np.array(physical);return result

def build(inputs,backend='solve',defect=None):
    xd,yd=load(inputs);x=xd.iod.values;y=yd.rainfall.values;years=yd.year.values
    weights=np.ones(yd.sizes['target'])/yd.sizes['target']
    preds=[];coefs=[];betas=[];choices=[];scores=[];xmeans=[];xstds=[];ymeans=[];ystds=[];errors=[]
    for year in range(2005,2020):
        train=years<year;held=np.where(xd.year.values==year)[0][0];target=np.where(years==year)[0][0]
        tx,ty=x[:len(years)][train],y[train]
        winner,loss=select(tx,ty,years[train],weights,backend)
        states=[]
        for lam in [0.,'constant',LAMBDAS[winner]]:
            state=month_only_fit(tx,ty,x[held],y[target],lam,backend) if defect=='month-only-year-leak' else fit(tx,ty,lam,backend)
            states.append(state)
        mu=[ty.mean(0),*[predict(s,x[held:held+1])[0] for s in states]]
        preds.append(mu);coefs.append([np.zeros_like(ty.mean(0)),*[s['physical_coefficient'] for s in states]])
        betas.append([np.zeros_like(ty.mean(0)),*[s['standardized_coefficient'] for s in states]])
        choices.append(winner);scores.append(loss);xmeans.append(states[0]['xmean']);xstds.append(states[0]['xstd']);ymeans.append(states[0]['ymean']);ystds.append(states[0]['ystd']);errors.append((np.array(mu)-y[target])**2)
    trainx=x[:len(years)];winner,score=select(trainx,y,years,weights,backend)
    final=[fit(trainx,y,lam,backend) for lam in [0.,'constant',LAMBDAS[winner]]]
    fcmean=np.array([np.broadcast_to(y.mean(0),(4,12,len(weights))),*[predict(s,x[len(years):]) for s in final]])
    coords={'year':np.arange(2005,2020),'month':np.arange(1,13),'system':SYSTEMS,'target':yd.target.values,'candidate':np.arange(len(LAMBDAS))}
    hc=xr.Dataset({'prediction':(('year','system','month','target'),preds),'coefficient':(('year','system','month','target'),coefs),'standardized_coefficient':(('year','system','month','target'),betas),'selected_candidate':('year',choices),'inner_loss':(('year','candidate'),scores),'xmean':(('year','month'),xmeans),'xstd':(('year','month'),xstds),'ymean':(('year','month','target'),ymeans),'ystd':(('year','month','target'),ystds),'squared_error':(('year','system','month','target'),errors)},coords=coords)
    loss=np.array(errors);monthly=np.einsum('ysmt,t->sm',loss,weights)
    hc['monthly_msss']=(('system','month'),1-monthly/monthly[0]);pool=monthly.sum(-1);hc['msss']=('system',1-pool/pool[0])
    fc=xr.Dataset({'prediction':(('system','year','month','target'),fcmean),'coefficient':(('system','month','target'),[np.zeros_like(y.mean(0)),*[s['physical_coefficient'] for s in final]]),'standardized_coefficient':(('system','month','target'),[np.zeros_like(y.mean(0)),*[s['standardized_coefficient'] for s in final]]),'selected_candidate':xr.DataArray(winner),'inner_loss':('candidate',score)},coords={'year':np.arange(2020,2024),'month':np.arange(1,13),'system':SYSTEMS,'target':yd.target.values,'candidate':np.arange(len(LAMBDAS))})
    for ds in [hc,fc]:ds.prediction.attrs['units']='mm';ds.coefficient.attrs['units']='mm/degree_Celsius'
    hc.ymean.attrs['units']='mm';hc.ystd.attrs['units']='mm';hc.xmean.attrs['units']='degree_Celsius';hc.xstd.attrs['units']='degree_Celsius';hc.squared_error.attrs['units']='mm2'
    state={'schema_version':1,'models':[{k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in s.items()} for s in final],'climatology':y.mean(0).tolist(),'targets':yd.target.values.tolist(),'selected_candidate':winner,'inner_loss':score.tolist()}
    return hc,fc,state

def from_state(state,inputs):
    with xr.open_dataset(Path(inputs)/'predictors.nc') as ds:xd=ds.load()
    new=xd.iod.sel(year=np.arange(2020,2024)).values
    models=[{k:(np.asarray(v) if isinstance(v,list) else v) for k,v in s.items()} for s in state['models']]
    ds=xr.Dataset({'prediction':(('system','year','month','target'),[np.broadcast_to(state['climatology'],(4,12,len(state['targets']))),*[predict(s,new) for s in models]]),'coefficient':(('system','month','target'),[np.zeros_like(models[0]['ymean']),*[s['physical_coefficient'] for s in models]]),'standardized_coefficient':(('system','month','target'),[np.zeros_like(models[0]['ymean']),*[s['standardized_coefficient'] for s in models]]),'selected_candidate':xr.DataArray(state['selected_candidate']),'inner_loss':('candidate',state['inner_loss'])},coords={'system':SYSTEMS,'year':np.arange(2020,2024),'month':np.arange(1,13),'target':state['targets'],'candidate':np.arange(len(LAMBDAS))})
    ds.prediction.attrs['units']='mm';ds.coefficient.attrs['units']='mm/degree_Celsius';return ds
