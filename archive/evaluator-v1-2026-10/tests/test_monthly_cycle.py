"""Scientific calendar, cyclic regularization and fit-boundary invariants."""
from pathlib import Path
import importlib.util,sys,shutil
import numpy as np
import xarray as xr
import pytest
ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'weatherbench/task_tools/monthly_cycle'
spec=importlib.util.spec_from_file_location('monthly_cycle',MODULE/'__init__.py',submodule_search_locations=[str(MODULE)])
pkg=importlib.util.module_from_spec(spec);sys.modules['monthly_cycle']=pkg;spec.loader.exec_module(pkg)
from monthly_cycle.reference import smooth,build,from_state,load,fit,predict,LAMBDAS
from monthly_cycle.checks import submission_checks
PRIVATE=ROOT/'var/private/tasks/monthly-cycle-calibration'
pytestmark=pytest.mark.skipif(not (PRIVATE/'agent-inputs/predictors.nc').exists(),reason='Internal real source bundle absent')

def test_cyclic_january_december_and_independent_fft():
    raw=np.zeros((12,2));raw[0]=[1,2]
    a=smooth(raw,4);b=smooth(raw,4,'fft')
    np.testing.assert_allclose(a,b,atol=1e-12)
    assert a[-1,0]>0;assert a[-1,0]==pytest.approx(a[1,0])
    np.testing.assert_allclose(smooth(raw,0),raw,atol=1e-12)
    np.testing.assert_allclose(smooth(raw,'constant'),np.broadcast_to(raw.mean(0),raw.shape))
    np.testing.assert_allclose(a.sum(0),raw.sum(0),atol=1e-12)

def test_independent_selection_and_forecasts():
    a=build(PRIVATE/'agent-inputs');b=build(PRIVATE/'agent-inputs',backend='fft')
    for one,two in zip(a[:2],b[:2]):xr.testing.assert_allclose(one,two,rtol=2e-10,atol=2e-8)

def test_all_months_of_held_year_excluded(tmp_path):
    inputs=tmp_path/'inputs';shutil.copytree(PRIVATE/'agent-inputs',inputs)
    original,_,state=build(inputs)
    with xr.open_dataset(inputs/'targets.nc') as ds:y=ds.load()
    y.rainfall.values[y.year.values>=2011]*=1.7;y.to_netcdf(inputs/'targets.nc',mode='w')
    changed,_,_=build(inputs)
    for k in ['prediction','coefficient','standardized_coefficient','selected_candidate','inner_loss','ymean','ystd']:
        xr.testing.assert_allclose(original[k].sel(year=slice(None,2011)),changed[k].sel(year=slice(None,2011)),atol=1e-12,rtol=1e-12)
    bad,_,_=build(inputs,defect='month-only-year-leak')
    assert float(abs(bad.prediction.sel(year=2011,system='constant-slope')-original.prediction.sel(year=2011,system='constant-slope')).max())>1e-4

def test_unit_change_and_saved_state_without_targets(tmp_path):
    x,y=load(PRIVATE/'agent-inputs');tx=x.iod.values[:15];ty=y.rainfall.values[:15]
    a=fit(tx,ty,4);b=fit(tx*2+7,ty*1000+3,4)
    np.testing.assert_allclose(predict(b,x.iod.values[15:]*2+7),predict(a,x.iod.values[15:])*1000+3,atol=1e-6,rtol=1e-11)
    _,forecast,state=build(PRIVATE/'agent-inputs');inputs=tmp_path/'inputs';shutil.copytree(PRIVATE/'agent-inputs',inputs);(inputs/'targets.nc').unlink()
    with xr.open_dataset(inputs/'predictors.nc') as ds:changed=ds.load()
    changed.iod.values[changed.year.values>=2020]+=np.linspace(.8,-.6,12);changed.to_netcdf(inputs/'predictors.nc',mode='w')
    result=from_state(state,inputs)
    assert float(abs(result.prediction-forecast.prediction).max())>1
    np.testing.assert_allclose(result.coefficient,forecast.coefficient,atol=1e-12)


def test_january_source_month_is_previous_december():
    x,y=load(PRIVATE/'agent-inputs')
    assert int(x.source_month.sel(month=1))==12
    np.testing.assert_array_equal(x.source_year.sel(month=1),x.year-1)
    np.testing.assert_array_equal(x.source_month.sel(month=slice(2,12)),np.arange(1,12))
    assert list(x.month.values)==list(range(1,13))
    assert list(y.month.values)==list(range(1,13))
