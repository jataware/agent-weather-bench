"""Prediction-level checks tolerate mathematically equivalent mode signs/bases."""
from pathlib import Path
import json
import numpy as np
import xarray as xr

GROUPS={'nested_mode_selection':('hindcasts.nc',['selected_candidate','inner_loss']), 'hindcast_predictions':('hindcasts.nc',['prediction']), 'hindcast_probabilities':('hindcasts.nc',['probability','threshold']), 'production_forecast':('forecast.nc',['prediction','probability','threshold','selected_candidate','inner_loss']), 'full_fit_diagnostic':('hindcasts.nc',['full_fit_prediction','full_fit_probability']), 'verification_arithmetic':('hindcasts.nc',['rps','rpss'])}

def comparison(actual,expected,names):
    details=[]
    for k in names:
        if k not in actual:return False,f'Missing variable {k}'
        a,b=actual[k],expected[k]
        if a.dims!=b.dims or any(d not in a.coords or not np.array_equal(a[d],b[d]) for d in b.dims):return False,f'{k}: dimensions, coordinate values or order differ'
        if not np.isfinite(a).all():return False,f'{k}: nonfinite values'
        if k in ['prediction','threshold','full_fit_prediction'] and a.attrs.get('units')!='mm':return False,f'{k}: units must be mm'
        delta=float(np.max(np.abs(a.values-b.values)));tol=2e-6 if 'prediction' in k or k=='threshold' else 2e-8
        correct=np.array_equal(a,b) if k=='selected_candidate' else np.allclose(a,b,atol=tol,rtol=2e-8)
        details.append(f'{k}: max absolute difference{delta:.6g}, tolerance{tol:g}')
        if not correct:return False,'; '.join(details)
    if 'probability' in names:
        p=actual.probability.values
        if np.min(p)<-1e-10 or np.max(p)>1+1e-10 or not np.allclose(p.sum(-1),1,atol=1e-8):return False,'Invalid probability simplex'
    return True,'; '.join(details)

def submission_checks(submission,private):
    submission,private=Path(submission),Path(private)
    private=private/'controller' if (private/'controller').is_dir() else private
    checks={}
    for name,(filename,fields) in GROUPS.items():
        try:
            with xr.open_dataset(submission/filename) as a,xr.open_dataset(private/filename) as b:p,d=comparison(a,b,fields)
        except (OSError,ValueError,KeyError,TypeError) as e:p,d=False,str(e)
        checks[name]={'state':'pass' if p else 'fail','detail':d,'evidence':['independent CCA controller reference; outputs invariant to equivalent mode signs']}
    try:
        answer=json.loads((submission/'answer.json').read_text())
        def period(value,start,end):return isinstance(value,list) and all(type(y) is int for y in value) and value in ([start,end],list(range(start,end+1)))
        passed=(answer['task']=='cca-seasonal-reproduction' and period(answer['training_years'],1993,2019) and period(answer['verification_years'],2005,2019) and period(answer['prediction_years'],2020,2023) and answer['rainfall_units']=='mm' and answer['full_fit_is_cross_validated'] is False and answer['cpt_binary_executed'] is False and isinstance(answer['limitations'],list))
        with xr.open_dataset(private/'hindcasts.nc') as gold:
            for system in gold.system.values:passed&=bool(np.isclose(answer['rpss'][str(system)],float(gold.rpss.sel(system=system)),rtol=2e-8,atol=2e-8))
        detail='Declared periods, units, source-vs-adaptation boundary and pooled RPSS'
    except (OSError,ValueError,KeyError,TypeError) as e:passed,detail=False,str(e)
    checks['answer_schema']={'state':'pass' if passed else 'fail','detail':detail,'evidence':['answer.json','controller/hindcasts.nc']}
    return checks
