"""Source adaptation checks separate fit/reference agreement and physical conservation."""
from pathlib import Path
import json
import numpy as np
import xarray as xr
try:from .reference import aggregate
except ImportError:from reference import aggregate


def submission_checks(submission,private):
    submission,private=Path(submission),Path(private);controller=private/'controller' if (private/'controller').is_dir() else private
    result={}
    for label,file,variables in [('geometry','forecast.nc',['area_m2','coarse_cell_id']),('mapped_prediction','forecast.nc',['mapped_coarse_mm']),('spatial_detail','forecast.nc',['rainfall_mm']),('leave_one_out','hindcasts.nc',['rainfall_mm','mapped_coarse_mm'])]:
        try:
            with xr.open_dataset(submission/file) as a,xr.open_dataset(controller/file) as expected:
                passed=True;errors=[]
                for name in variables:
                    x,y=a[name],expected[name]
                    if x.dims!=y.dims or x.attrs.get('units')!=y.attrs.get('units') or any(not np.array_equal(x[d],y[d]) for d in y.dims):raise ValueError('Wrong dimensions,units or coordinate order')
                    if not np.isfinite(x).all():raise ValueError('Nonfinite scientific output')
                    passed=passed and np.allclose(x,y,rtol=1e-9,atol=1e-7);errors.append(f'{name}max_error_mm={float(np.max(abs(x.values-y.values)))}')
            result[label]={'state':'pass' if passed else 'fail','detail':'; '.join(errors),'evidence':[file,'controller prescribed reference']}
        except (OSError,ValueError,KeyError,TypeError) as error:result[label]={'state':'fail','detail':str(error),'evidence':[file]}
    try:
        with xr.open_dataset(submission/'forecast.nc') as ds,xr.open_dataset(controller/'forecast.nc') as target:
            valid=(ds.rainfall_mm.dims==('year','lat','lon') and ds.rainfall_mm.shape==target.rainfall_mm.shape and all(np.array_equal(ds[c],target[c]) for c in ('year','lat','lon')) and ds.rainfall_mm.attrs.get('units')=='mm')
            if not valid:raise ValueError('Wrong forecast schema')
            positive=bool(np.isfinite(ds.rainfall_mm).all() and (ds.rainfall_mm>=0).all())
            a=target.area_m2.values;cell=target.coarse_cell_id.values;coarse=aggregate(ds.rainfall_mm.values,a,cell)
            expected=ds.mapped_coarse_mm.values
            conserve=bool(np.allclose(coarse,expected,rtol=1e-10,atol=1e-7))
            detail=f'maximum area-mean mismatch_mm={float(np.max(abs(coarse-expected)))}; negative_fine_cells={int((ds.rainfall_mm<0).sum())}'
        result['conservation_and_positivity']={'state':'pass' if conserve and positive else 'fail','detail':detail,'evidence':['forecast.nc','independent trusted spherical area weights']}
    except (OSError,ValueError,KeyError,TypeError) as error:result['conservation_and_positivity']={'state':'fail','detail':str(error),'evidence':['forecast.nc']}
    try:
        answer=json.loads((submission/'answer.json').read_text());valid=all(k in answer for k in ['task','raw_unit_status','training_years','prediction_years','conservation_definition','limitations']) and answer['task']=='conservative-downscaling' and answer['raw_unit_status']=='unresolved_source_scale'
        result['answer_schema']={'state':'pass' if valid else 'fail','detail':'Experiment and unresolved raw-scale fields','evidence':['answer.json']}
    except (OSError,ValueError,KeyError,TypeError) as error:result['answer_schema']={'state':'fail','detail':str(error),'evidence':['answer.json']}
    return result
