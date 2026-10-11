"""Candidate experiment and one attainable repair. Agent methods are not matched here."""
import json
from pathlib import Path
import numpy as np
import xarray as xr


def read(inputs):
    inputs = Path(inputs)
    with xr.open_dataset(inputs / 'predictors.nc') as ds:
        predictors = ds.load()
    with xr.open_dataset(inputs / 'targets.nc') as ds:
        targets = ds.load()
    return predictors, targets


def fit_predict(x, y, new, alpha=1.0, global_mean=None):
    mean, scale = x.mean(0), x.std(0)
    scale = np.where(scale < 1e-10, 1, scale)
    z, q = (x - mean) / scale, (new - mean) / scale
    ym = y.mean(0) if global_mean is None else global_mean
    # Dual ridge solve remains well defined with more predictors than years.
    return np.maximum(ym + q @ z.T @ np.linalg.solve(z @ z.T + alpha * np.eye(len(z)), y - ym), 0)


def original(inputs):
    p, t = read(inputs)
    cfg = json.loads((Path(inputs) / 'candidate-config.json').read_text())
    x, y = p.sst.sel(year=t.year).values, t.rainfall.values
    yrs, out = t.year.values, []
    cols = np.arange(x.shape[1])
    if cfg['select_scope'] == 'whole_record':
        xx, yy = x - x.mean(0), y - y.mean(0)
        corr = (xx.T @ yy) / np.sqrt((xx**2).sum(0)[:, None] * (yy**2).sum(0)[None, :])
        cols = np.array([np.argmax(np.mean(corr**2, axis=1))])
    global_mean = y.mean(0) if cfg['centering_scope'] == 'whole_record' else None
    for year in range(2005, 2020):
        past, row = yrs < year, yrs == year
        out.append(fit_predict(x[past][:, cols], y[past], x[row][:, cols], global_mean=global_mean)[0])
    return np.asarray(out)


def repaired(inputs, method='ridge', defect=None):
    p, t = read(inputs)
    yrs, x, y = t.year.values, p.sst.sel(year=t.year).values, t.rainfall.values
    hindcast, climate = [], []
    for year in range(2005, 2020):
        past, row = yrs < year, yrs == year
        climate.append(y[past].mean(0))
        if method == 'climatology':
            value = climate[-1]
        elif defect == 'uses_targets':
            value = y[row][0]
        elif defect == 'localized_lookahead' and year == 2006:
            value = y[yrs == 2007][0]
        elif defect == 'localized_future_features' and year == 2006:
            value = fit_predict(x[past],y[past],x[row])[0]+5*float(p.sst.sel(year=2007).mean())
        elif defect == 'global_future_features':
            scale=p.sst.values.std(0);scale=np.where(scale<1e-10,1,scale)
            z=(x[past]-x[past].mean(0))/scale;q=(x[row]-x[past].mean(0))/scale
            ym=y[past].mean(0)
            value=np.maximum(ym+q@z.T@np.linalg.solve(z@z.T+np.eye(past.sum()),y[past]-ym),0)[0]
        elif defect == 'global_preprocessing':
            value = fit_predict(x[past], y[past], x[row], global_mean=y.mean(0))[0]
        elif defect == 'global_selection':
            xx, yy = x-x.mean(0), y-y.mean(0)
            corr = (xx.T@yy) / np.sqrt((xx**2).sum(0)[:,None]*(yy**2).sum(0)[None,:])
            col = int(np.argmax(np.mean(corr**2,axis=1)))
            value = fit_predict(x[past,col:col+1],y[past],x[row,col:col+1])[0]
        else:
            value = fit_predict(x[past], y[past], x[row])[0]
        hindcast.append(value)
    new = p.sst.sel(year=np.arange(2020, 2024)).values
    forecast = np.broadcast_to(y.mean(0), (4, y.shape[1])).copy() if method == 'climatology' else fit_predict(x,y,new)
    if defect == 'localized_production_features':
        forecast[0]+=5*float(p.sst.sel(year=2021).mean())
    if defect == 'pooled_features':
        forecast += new.mean() - x.mean()
    observed = t.rainfall.sel(year=np.arange(2005,2020)).values
    old = original(inputs)
    return dict(hindcast_year=np.arange(2005,2020), forecast_year=np.arange(2020,2024), target=np.arange(y.shape[1]),
                original_hindcast_mm=old, hindcast_mm=np.asarray(hindcast), forecast_mm=forecast,
                original_rmse_mm=np.sqrt(np.mean((old-observed)**2)),
                hindcast_rmse_mm=np.sqrt(np.mean((np.asarray(hindcast)-observed)**2)),
                climatology_rmse_mm=np.sqrt(np.mean((np.asarray(climate)-observed)**2)))
