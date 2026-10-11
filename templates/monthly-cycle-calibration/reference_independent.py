"""Independent FFT/scalar-covariance route of the archived fixed experiment.

No imports of science.py or the primary hooks. The archived independent route
used spectral inversion of the cyclic Laplacian and scalar sample covariance;
this module implements that route in a separate driver.
"""
import math
from pathlib import Path
import numpy as np
import xarray as xr


def reference(inputs,params=None,conventions=None,target_path=None):
    with xr.open_dataset(Path(inputs)/"predictors.nc") as ds:
        x = np.asarray(ds.iod,dtype="float64")
        xy = np.asarray(ds.year)
    with xr.open_dataset(Path(target_path) if target_path is not None else Path(inputs)/"targets.nc") as ds:
        y = np.asarray(ds.rainfall,dtype="float64")
        years = np.asarray(ds.year)
    lambdas = (0.,.25,1.,4.,16.,64.)
    def fit(rows,penalty):
        xx,yy = x[rows],y[rows]
        centerx,centery = xx.mean(0),yy.mean(0)
        scalex,scaley = xx.std(0,ddof=1),yy.std(0,ddof=1)
        if np.min(scalex)<=0 or np.min(scaley)<=0:
            raise ValueError("Constant monthly support")
        covariance = np.array([[math.fsum((xx[i,m]-centerx[m])*(yy[i,m,t]-centery[m,t])
                         for i in range(len(rows)))/((len(rows)-1)*scalex[m]*scaley[m,t])
                         for t in range(3)] for m in range(12)])
        if penalty=="constant":
            slopes = np.tile(covariance.mean(0),(12,1))
        else:
            eigenvalues = np.array([2-2*math.cos(2*math.pi*k/12) for k in range(12)])
            slopes = np.fft.ifft(np.fft.fft(covariance,axis=0)/(1+penalty*eigenvalues[:,None]),axis=0).real
        return centerx,scalex,centery,scaley,slopes,slopes*scaley/scalex[:,None]
    def predict(model,features):
        return model[2][None]+model[5][None]*(features-model[0])[...,None]
    def select(rows):
        losses=[]
        for penalty in lambdas:
            annual=[]
            for held in rows:
                if years[held]<2001:
                    continue
                before=[i for i in rows if years[i]<years[held]]
                model=fit(before,penalty)
                error=(predict(model,x[held:held+1])[0]-y[held])/model[3]
                # Equal region, month and inner-year weights, as specified.
                annual.append(math.fsum(float(v)**2 for v in error.flat)/36)
            losses.append(math.fsum(annual)/len(annual))
        winner=min(range(6),key=lambda i:(losses[i],i))
        return winner,np.array(losses)
    output={"outer_year":np.arange(2005,2020),"forecast_year":np.arange(2020,2024),
            "month":np.arange(1,13),"system":np.arange(4),"target":np.arange(3),"candidate":np.arange(6)}
    collected={name:[] for name in ("hindcast_mm","hindcast_coefficient","hindcast_standardized_coefficient",
                    "selected_candidate","inner_loss","xmean","xstd","ymean","ystd","squared_error")}
    for year in range(2005,2020):
        rows=[i for i,yy in enumerate(years) if yy<year]
        held=int(np.flatnonzero(xy==year)[0])
        winner,loss=select(rows)
        models=[fit(rows,penalty) for penalty in (0.,"constant",lambdas[winner])]
        prediction=np.array([y[rows].mean(0),*[predict(model,x[held:held+1])[0] for model in models]])
        collected["hindcast_mm"].append(prediction)
        collected["hindcast_coefficient"].append([np.zeros((12,3)),*[model[5] for model in models]])
        collected["hindcast_standardized_coefficient"].append([np.zeros((12,3)),*[model[4] for model in models]])
        collected["selected_candidate"].append(winner)
        collected["inner_loss"].append(loss)
        for name,index in (("xmean",0),("xstd",1),("ymean",2),("ystd",3)):
            collected[name].append(models[0][index])
        collected["squared_error"].append((prediction-y[held])**2)
    output.update({name:np.asarray(value) for name,value in collected.items()})
    monthly=np.empty((4,12))
    for system in range(4):
        for month in range(12):
            monthly[system,month]=math.fsum(float(v) for v in output["squared_error"][:,system,month,:].flat)/3
    output["monthly_msss"]=1-monthly/monthly[0]
    pooled=monthly.sum(-1)
    output["msss"]=1-pooled/pooled[0]
    rows=list(range(len(years)))
    winner,loss=select(rows)
    models=[fit(rows,penalty) for penalty in (0.,"constant",lambdas[winner])]
    future=x[[int(np.flatnonzero(xy==year)[0]) for year in range(2020,2024)]]
    output.update(forecast_mm=np.array([np.broadcast_to(y.mean(0),(4,12,3)),*[predict(model,future) for model in models]]),
                  forecast_coefficient=np.array([np.zeros((12,3)),*[model[5] for model in models]]),
                  forecast_standardized_coefficient=np.array([np.zeros((12,3)),*[model[4] for model in models]]),
                  final_candidate=np.asarray(winner),final_inner_loss=loss)
    return output
