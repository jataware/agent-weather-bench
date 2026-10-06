"""Numeric scientific checks for cycle-sharing adaptation."""
from pathlib import Path
import json
import numpy as np
import xarray as xr
GROUPS={'fold_moments':('hindcasts.nc',['xmean','xstd','ymean','ystd']),'cyclic_coefficients':('hindcasts.nc',['coefficient','standardized_coefficient']),'nested_selection':('hindcasts.nc',['selected_candidate','inner_loss']),'outer_prediction':('hindcasts.nc',['prediction']),'production_prediction':('forecast.nc',['prediction','coefficient','standardized_coefficient','selected_candidate','inner_loss']),'verification_arithmetic':('hindcasts.nc',['squared_error','monthly_msss','msss'])}

def comparison(actual,expected,names):
    detail=[]
    for k in names:
        if k not in actual:return False,f'Missing variable{k}'
        a,b=actual[k],expected[k]
        if a.dims!=b.dims or any(d not in a.coords or not np.array_equal(a[d],b[d]) for d in b.dims):return False,f'{k}: dimensions, coordinate values/order differ'
        if not np.isfinite(a).all():return False,f'{k}: nonfinite values'
        if b.attrs.get('units') and a.attrs.get('units')!=b.attrs['units']:return False,f'{k}: incorrect units'
        delta=float(abs(a-b).max());tol=2e-5 if k=='squared_error' else 2e-7
        ok=np.array_equal(a,b) if k=='selected_candidate' else np.allclose(a,b,rtol=2e-8,atol=tol)
        detail.append(f'{k}: maximum difference {delta:.6g}, absolute tolerance {tol:g}')
        if not ok:return False,'; '.join(detail)
    return True,'; '.join(detail)

def submission_checks(submission,private):
    submission,private=Path(submission),Path(private);controller=private/'controller' if (private/'controller').is_dir() else private;result={}
    for name,(file,fields) in GROUPS.items():
        try:
            with xr.open_dataset(submission/file) as a,xr.open_dataset(controller/file) as b:p,d=comparison(a,b,fields)
        except (OSError,ValueError,TypeError,KeyError) as e:p,d=False,str(e)
        result[name]={'state':'pass' if p else 'fail','detail':d,'evidence':['independent cyclic solve/FFT references']}
    try:
        answer=json.loads((submission/'answer.json').read_text())
        def period(v,a,b):return isinstance(v,list) and all(type(y) is int for y in v) and v in ([a,b],list(range(a,b+1)))
        p=answer['task']=='monthly-cycle-calibration' and period(answer['training_years'],1993,2019) and period(answer['verification_years'],2005,2019) and period(answer['prediction_years'],2020,2023) and answer['rainfall_units']=='mm' and answer['dynamical_hindcasts_used'] is False and answer['full_paper_reproduction'] is False and isinstance(answer['limitations'],list)
        with xr.open_dataset(controller/'hindcasts.nc') as gold:
            for system in gold.system.values:p&=bool(np.isclose(answer['msss'][str(system)],float(gold.msss.sel(system=system)),atol=2e-8,rtol=2e-8))
        d='Declared experiment periods, statistical predictor/method boundaries and pooled MSSS'
    except (OSError,ValueError,TypeError,KeyError) as e:p,d=False,str(e)
    result['answer_schema']={'state':'pass' if p else 'fail','detail':d,'evidence':['answer.json','controller/hindcasts.nc']};return result
