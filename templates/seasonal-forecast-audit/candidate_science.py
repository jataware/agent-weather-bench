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

