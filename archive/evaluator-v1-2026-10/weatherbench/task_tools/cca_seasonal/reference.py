"""Controller-only CCA reference; no original forecast library is imported."""
from pathlib import Path
import json
import numpy as np
import xarray as xr
from scipy import linalg
from scipy.stats import t

CANDIDATES=tuple((a,b,c) for a in range(1,4) for b in range(1,4) for c in range(1,min(a,b)+1))
SYSTEMS=['climatology','cca-fixed','cca-nested']

def fit(x,y,xlat,ylat,modes,backend='svd'):
    xm,ym=x.mean(0),y.mean(0)
    xs,ys=x.std(0,ddof=1),y.std(0,ddof=1)
    xw,yw=np.sqrt(np.cos(np.deg2rad(xlat))),np.sqrt(np.cos(np.deg2rad(ylat)))
    a,b=(x-xm)*xw/xs,(y-ym)*yw/ys
    def eof(z,k):
        if backend=='svd':
            u,s,v=np.linalg.svd(z,full_matrices=False)
            return u[:,:k],s[:k],v[:k].T
        values,vectors=linalg.eigh(z.T@z)
        ix=np.argsort(values)[::-1][:k]
        s=np.sqrt(values[ix]);v=vectors[:,ix]
        return z@v/s,s,v
    ux,sx,vx=eof(a,modes[0]);uy,sy,vy=eof(b,modes[1])
    if backend=='svd':q,rho,rt=np.linalg.svd(ux.T@uy,full_matrices=False)
    else:q,rho,rt=linalg.svd(ux.T@uy,full_matrices=False,lapack_driver='gesvd')
    c=modes[2]
    z=(xw/xs)[:,None]*(vx/sx)@q[:,:c]
    coefficient=(z*rho[:c])@rt[:c]@np.diag(sy)@vy.T*(ys/yw)
    return {'xmean':xm,'ymean':ym,'coefficient':coefficient,'leverage_matrix':z@z.T,'n':len(x),'modes':modes,'canonical_correlation':rho[:c]}

def deterministic(model,new):return (new-model['xmean'])@model['coefficient']+model['ymean']

def quantiles(y):
    yy=np.sort(y,axis=0);r=len(y)*np.array([1/3,2/3])+.5
    j=np.floor(r).astype(int);f=r-j
    return np.stack([(1-ff)*yy[jj-1]+ff*yy[jj] for jj,ff in zip(j,f)])

def distribution(x,y,new,xlat,ylat,modes,backend='svd'):
    model=fit(x,y,xlat,ylat,modes,backend)
    # Fixed selected configuration, leave-one-out fits inside this training set.
    residual=[]
    for i in range(len(x)):
        keep=np.arange(len(x))!=i
        m=fit(x[keep],y[keep],xlat,ylat,modes,backend)
        residual.append(y[i]-deterministic(m,x[i:i+1])[0])
    df=len(x)-modes[0]-1
    variance=np.sum(np.square(residual),axis=0)/df
    threshold=quantiles(y)
    model.update(variance=variance,threshold=threshold,df=df)
    pp,mu=predict(model,new)
    return pp,mu,model

def predict(model,new):
    mu=deterministic(model,new);dx=new-model['xmean']
    h=1/model['n']+np.einsum('ni,ij,nj->n',dx,model['leverage_matrix'],dx)
    scale=np.sqrt(model['variance'][None,:]*(1+h[:,None]))
    cdf=t.cdf((model['threshold'][None,:,:]-mu[:,None,:])/scale[:,None,:],model['df'])
    return np.stack([cdf[:,0],cdf[:,1]-cdf[:,0],1-cdf[:,1]],axis=-1),mu

def select(x,y,years,xlat,ylat,backend='svd'):
    scores=[];weights=np.cos(np.deg2rad(ylat));weights/=weights.sum()
    for modes in CANDIDATES:
        losses=[]
        for held in np.where(years>=2001)[0]:
            keep=years<years[held]
            m=fit(x[keep],y[keep],xlat,ylat,modes,backend)
            delta=(deterministic(m,x[held:held+1])[0]-y[held])/y[keep].std(0,ddof=1)
            losses.append(np.sum(weights*delta**2))
        scores.append(np.mean(losses))
    return int(np.argmin(scores)),np.array(scores)

def load(inputs):
    with xr.open_dataset(Path(inputs)/'predictors.nc') as d:xd=d.load()
    with xr.open_dataset(Path(inputs)/'targets.nc') as d:yd=d.load()
    return xd,yd

def build(inputs,backend='svd',defect=None):
    xd,yd=load(inputs);x=xd.sst.values;y=yd.rainfall.values;years=yd.year.values
    xlat=xd.predictor_lat.values;ylat=yd.target_lat.values
    rows=[];thresholds=[];probs=[];choices=[];inners=[];losses=[]
    for year in range(2005,2020):
        train=years<year;held=np.where(xd.year.values==year)[0];iy=np.where(years==year)[0][0]
        tx=x[:len(years)][train];ty=y[train];tyears=years[train]
        if defect=='full-training':tx=x[:len(years)];ty=y;tyears=years
        winner,scores=select(tx,ty,tyears,xlat,ylat,backend)
        spec=[(1,1,1),CANDIDATES[winner]]
        pp=[np.full((len(ylat),3),1/3)];mu=[ty.mean(0)];bb=quantiles(ty)
        for modes in spec:
            prob,pred,m=distribution(tx,ty,x[held],xlat,ylat,modes,backend)
            pp.append(prob[0]);mu.append(pred[0])
        pp=np.stack(pp);target=(y[iy][None,:]<bb).T
        rps=np.mean((np.cumsum(pp,axis=-1)[...,:2]-target[None,:,:])**2,axis=-1)
        rows.append(mu);thresholds.append(bb);probs.append(pp);choices.append(winner);inners.append(scores);losses.append(rps)
    trainx=x[:len(years)];winner,score=select(trainx,y,years,xlat,ylat,backend)
    production=[];prediction=[];states=[]
    for modes in [(1,1,1),CANDIDATES[winner]]:
        pp,mu,m=distribution(trainx,y,x[len(years):],xlat,ylat,modes,backend)
        production.append(pp);prediction.append(mu);states.append(m)
    fullprob,fullmean=predict(states[1],x[np.isin(xd.year.values,np.arange(2005,2020))])
    coords={'year':np.arange(2005,2020),'target':yd.target.values,'category':['below','near','above'],'system':SYSTEMS,'boundary':[1/3,2/3],'candidate':np.arange(len(CANDIDATES))}
    hc=xr.Dataset({'prediction':(('year','system','target'),np.array(rows)), 'probability':(('year','system','target','category'),np.array(probs)), 'threshold':(('year','boundary','target'),np.array(thresholds)), 'selected_candidate':('year',choices),'inner_loss':(('year','candidate'),np.array(inners)), 'rps':(('year','system','target'),np.array(losses)), 'full_fit_prediction':(('year','target'),fullmean), 'full_fit_probability':(('year','target','category'),fullprob)},coords=coords)
    weights=np.cos(np.deg2rad(ylat));loss=np.array(losses);pooled=np.einsum('yst,t->s',loss,weights)
    hc['rpss']=('system',1-pooled/pooled[0])
    fc=xr.Dataset({'probability':(('system','year','target','category'),np.concatenate([np.full((1,4,len(ylat),3),1/3),np.array(production)],axis=0)), 'prediction':(('system','year','target'),np.concatenate([np.broadcast_to(y.mean(0),(1,4,len(ylat))),np.array(prediction)],axis=0)), 'threshold':(('boundary','target'),quantiles(y)), 'selected_candidate':xr.DataArray(winner), 'inner_loss':('candidate',score)},coords={'system':SYSTEMS,'year':np.arange(2020,2024),'target':yd.target.values,'category':['below','near','above'],'boundary':[1/3,2/3],'candidate':np.arange(len(CANDIDATES))})
    for ds in (hc,fc):
        ds.prediction.attrs['units']='mm';ds.threshold.attrs['units']='mm'
        if 'full_fit_prediction' in ds:ds.full_fit_prediction.attrs['units']='mm'
        ds=ds.assign_coords(target_lat=('target',ylat),target_lon=('target',yd.target_lon.values))
    state={'schema_version':1,'models':[{k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in m.items()} for m in states], 'climatology':y.mean(0).tolist(),'selected_candidate':winner,'inner_loss':score.tolist(),'targets':yd.target.values.tolist()}
    return hc,fc,state

def from_state(state,inputs):
    with xr.open_dataset(Path(inputs)/'predictors.nc') as d:xd=d.load()
    years=np.arange(2020,2024);new=xd.sst.sel(year=years).values
    pp=[np.full((4,len(state['targets']),3),1/3)];mu=[np.broadcast_to(state['climatology'],(4,len(state['targets'])))]
    for raw in state['models']:
        m={k:np.asarray(v) if isinstance(v,list) and k!='modes' else v for k,v in raw.items()}
        p,pred=predict(m,new);pp.append(p);mu.append(pred)
    fc=xr.Dataset({'probability':(('system','year','target','category'),pp),'prediction':(('system','year','target'),mu),'threshold':(('boundary','target'),state['models'][0]['threshold']),'selected_candidate':xr.DataArray(state['selected_candidate']),'inner_loss':('candidate',state['inner_loss'])},coords={'system':SYSTEMS,'year':years,'target':state['targets'],'category':['below','near','above'],'boundary':[1/3,2/3],'candidate':np.arange(len(CANDIDATES))})
    fc.prediction.attrs['units']='mm';fc.threshold.attrs['units']='mm';return fc
