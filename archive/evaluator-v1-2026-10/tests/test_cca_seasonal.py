"""Independent scientific invariants and consequential wrong-route controls."""
import json,shutil
from pathlib import Path
import numpy as np
import pytest
import xarray as xr
from weatherbench.task_tools.cca_seasonal.reference import fit,deterministic,build,from_state,load,CANDIDATES
from weatherbench.task_tools.cca_seasonal.checks import submission_checks

ROOT=Path(__file__).resolve().parents[1]
PRIVATE=ROOT/'var/private/tasks/cca-seasonal-reproduction'
pytestmark=pytest.mark.skipif(not (PRIVATE/'agent-inputs/predictors.nc').exists(),reason='Internal real source bundle not installed')

def test_independent_decompositions_all_candidates():
    x,y=load(PRIVATE/'agent-inputs');xx=x.sst.values[:15];yy=y.rainfall.values[:15]
    for modes in CANDIDATES:
        a=fit(xx,yy,x.predictor_lat.values,y.target_lat.values,modes)
        b=fit(xx,yy,x.predictor_lat.values,y.target_lat.values,modes,backend='eigen')
        np.testing.assert_allclose(deterministic(a,x.sst.values[15:]),deterministic(b,x.sst.values[15:]),rtol=2e-10,atol=2e-7)
        np.testing.assert_allclose(a['leverage_matrix'],b['leverage_matrix'],rtol=2e-8,atol=2e-9)

def test_basis_permutation_and_target_unit_invariance():
    x,y=load(PRIVATE/'agent-inputs');xx=x.sst.values[:18];yy=y.rainfall.values[:18];new=x.sst.values[18:]
    modes=(3,3,2);a=fit(xx,yy,x.predictor_lat.values,y.target_lat.values,modes)
    ix=np.arange(xx.shape[1])[::-1]
    b=fit(xx[:,ix],yy*1000+7,x.predictor_lat.values[ix],y.target_lat.values,modes)
    np.testing.assert_allclose(deterministic(b,new[:,ix]),deterministic(a,new)*1000+7,rtol=1e-10,atol=1e-5)

def test_future_target_isolation_and_real_inference(tmp_path):
    inputs=tmp_path/'inputs';shutil.copytree(PRIVATE/'agent-inputs',inputs)
    original,forecast,state=build(inputs)
    with xr.open_dataset(inputs/'targets.nc') as ds:y=ds.load()
    y.rainfall.values[y.year.values>=2011]*=1.7;y.to_netcdf(inputs/'targets.nc',mode='w')
    altered,_,_=build(inputs)
    for name in ['prediction','probability','threshold','selected_candidate','inner_loss']:
        xr.testing.assert_allclose(original[name].sel(year=slice(None,2011)),altered[name].sel(year=slice(None,2011)),rtol=1e-12,atol=1e-12)
    (inputs/'targets.nc').unlink()
    with xr.open_dataset(inputs/'predictors.nc') as ds:x=ds.load()
    x.sst.values[x.year.values>=2020]+=np.linspace(.8,-.6,x.sizes['predictor']);x.to_netcdf(inputs/'predictors.nc',mode='w')
    inferred=from_state(state,inputs)
    assert float(abs(inferred.probability-forecast.probability).max())>.01
    assert np.isfinite(inferred.probability).all()
    np.testing.assert_allclose(inferred.probability.sum('category'),1,atol=1e-12)

def test_full_training_route_is_not_outer_cross_validation(tmp_path):
    gold,_,_=build(PRIVATE/'agent-inputs');bad,_,_=build(PRIVATE/'agent-inputs',defect='full-training')
    assert float(abs(gold.probability-bad.probability).max())>.05
    assert float(abs(gold.prediction-bad.prediction).max())>1
    assert float(abs(gold.prediction.sel(system='cca-nested')-gold.full_fit_prediction).max())>1

def test_correct_controls_and_wrong_route_rejection():
    root=ROOT/'var/calibration/cca-seasonal-reproduction/controls'
    if not root.exists():pytest.skip('Constructed controls not installed')
    good=submission_checks(root/'baseline/frozen',PRIVATE);assert all(c['state']=='pass' for c in good.values())
    bad=submission_checks(root/'full-training-leak/frozen',PRIVATE)
    assert bad['hindcast_predictions']['state']=='fail'
    assert bad['hindcast_probabilities']['state']=='fail'
    cached=submission_checks(root/'cached-inference/frozen',PRIVATE);assert all(c['state']=='pass' for c in cached.values())
