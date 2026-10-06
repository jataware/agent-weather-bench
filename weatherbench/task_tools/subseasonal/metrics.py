"""Controller metric: pooled cosine-latitude-weighted RMSE on fixed support."""
from pathlib import Path
import numpy as np
import xarray as xr


def weighted_rmse(prediction, observed, latitude):
    prediction=np.asarray(prediction,dtype=np.float64);observed=np.asarray(observed,dtype=np.float64)
    weights=np.cos(np.deg2rad(np.asarray(latitude,dtype=np.float64)))
    if prediction.shape!=observed.shape or prediction.ndim!=2 or prediction.shape[1]!=len(weights):
        raise ValueError('Expected complete issue by location arrays')
    if not np.isfinite(prediction).all() or not np.isfinite(observed).all() or not np.isfinite(weights).all() or np.any(weights<=0):
        raise ValueError('Nonfinite values or invalid spatial weights')
    return float(np.sqrt(np.sum((prediction-observed)**2*weights[None,:])/(prediction.shape[0]*np.sum(weights))))


def validate_prediction(path, expected):
    """Validate public schema and bounded shape before loading untrusted values."""
    with xr.open_dataset(path,create_default_indexes=False) as ds:
        if 'precipitation' not in ds or ds.precipitation.dims!=('issue_time','location'):
            raise ValueError('precipitation must have issue_time,location dimensions')
        if dict(ds.sizes)!=dict(expected.sizes) or ds.precipitation.attrs.get('units')!='mm':
            raise ValueError('Wrong shape or units')
        for name in ('issue_time','location','latitude','longitude','target_start'):
            if name not in ds.coords or ds[name].dims!=expected[name].dims or ds[name].shape!=expected[name].shape:
                raise ValueError('Wrong public coordinates')
            if not np.array_equal(ds[name].values,expected[name].values):
                raise ValueError('Public coordinate values or order differ')
        values=ds.precipitation.values.astype(np.float64)
        if not np.isfinite(values).all() or np.any(values<0) or np.any(values>10000):
            raise ValueError('Predictions must be finite nonnegative totals at most10000mm')
    return values


def score_file(path, private_task_root, split):
    if split not in ('development','final'):raise ValueError('Unknown split')
    root=Path(private_task_root)
    c=root/'controller' if (root/'controller').is_dir() else root
    with xr.open_dataset(c/f'{split}-targets.nc') as ds:
        expected=ds.load()
    prediction=validate_prediction(path,expected)
    rmse=weighted_rmse(prediction,expected.precipitation,expected.latitude)
    with xr.open_dataset(c/f'{split}-baselines.nc') as ds:
        raw=weighted_rmse(ds.raw_cfsv2,expected.precipitation,expected.latitude)
        clim=weighted_rmse(ds.climatology,expected.precipitation,expected.latitude)
    if raw<=0 or clim<=0:raise ValueError('Baseline denominator is zero')
    return {'rmse_mm':rmse,'raw_cfsv2_rmse_mm':raw,'climatology_rmse_mm':clim,
            'rmse_skill_vs_raw_cfsv2':float(1-rmse/raw),'rmse_skill_vs_climatology':float(1-rmse/clim),
            'issues':int(expected.sizes['issue_time']),'locations':int(expected.sizes['location'])}


def score_development(prediction_path, private_task_root):
    """Trusted callback returns aggregate development score only, never final targets."""
    return score_file(prediction_path,private_task_root,'development')
