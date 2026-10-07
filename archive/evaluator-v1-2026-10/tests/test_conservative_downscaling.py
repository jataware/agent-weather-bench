"""Staged tests: do not modify imported framework fingerprints during pilot runs."""
from pathlib import Path
import sys,json,shutil,importlib.util,importlib
import numpy as np,xarray as xr,pytest

STAGE=Path(__file__).resolve().parents[1]
MODULE=STAGE/'weatherbench/task_tools/conservative_downscaling'
spec=importlib.util.spec_from_file_location('conservative_downscaling_staged',MODULE/'__init__.py',submodule_search_locations=[str(MODULE)])
package=importlib.util.module_from_spec(spec);sys.modules[spec.name]=package;spec.loader.exec_module(package)
reference=importlib.import_module('conservative_downscaling_staged.reference')
geometry,aggregate,fit,infer,map_value,build=(getattr(reference,n) for n in ('geometry','aggregate','fit','infer','map_value','build'))
audit=importlib.import_module('conservative_downscaling_staged.audit').audit
submission_checks=importlib.import_module('conservative_downscaling_staged.checks').submission_checks
preparation=importlib.import_module('conservative_downscaling_staged.prepare');prepare,digest=preparation.prepare,preparation.digest
PRIVATE=STAGE/'var/private/tasks/conservative-downscaling'


def test_real_independent_geometry_rank_and_affine_invariance():
    assert audit(PRIVATE)['all_passed']


def test_rank_ties_clamped_tails_and_positive_scaling():
    raw=[1.,1.,3.,7.];obs=[10.,20.,30.,40.]
    assert map_value(1,raw,obs)==15
    assert map_value(-5,raw,obs)==15
    assert map_value(99,raw,obs)==40
    assert map_value(2,raw,obs)==pytest.approx(22.5)
    assert map_value(2*92+7,np.array(raw)*92+7,obs)==pytest.approx(22.5)


def test_positive_ratio_conserves_each_cell_of_realdata():
    forecast,_,_=build(PRIVATE/'agent-inputs')
    means=aggregate(forecast.rainfall_mm.values,forecast.area_m2.values,forecast.coarse_cell_id.values)
    assert np.all(forecast.rainfall_mm.values>=0)
    np.testing.assert_allclose(means,forecast.mapped_coarse_mm.values,rtol=1e-12,atol=1e-9)


def test_entire_heldout_year_is_excluded_from_all_statistics(tmp_path):
    inputs=tmp_path/'inputs';shutil.copytree(PRIVATE/'agent-inputs',inputs)
    original,hindcasts,_=build(inputs)
    with xr.open_dataset(inputs/'fine-training.nc') as f:changed=f.load()
    changed.seasonal_total.values[changed.year.values==2001]*=2
    changed.to_netcdf(inputs/'fine-training.nc',mode='w')
    new,new_hindcasts,_=build(inputs)
    np.testing.assert_allclose(new_hindcasts.sel(year=2001).rainfall_mm,hindcasts.sel(year=2001).rainfall_mm,rtol=0,atol=0)
    assert np.max(abs(new.rainfall_mm.values-original.rainfall_mm.values))>1


def test_mass_creation_detected_on_real_output(tmp_path):
    forecast,hindcasts,_=build(PRIVATE/'agent-inputs')
    forecast.rainfall_mm.values*=1.05
    forecast.to_netcdf(tmp_path/'forecast.nc');hindcasts.to_netcdf(tmp_path/'hindcasts.nc')
    assert submission_checks(tmp_path,PRIVATE)['conservation_and_positivity']['state']=='fail'


def test_controller_uses_trusted_areas_not_claimed_untrusted_weights(tmp_path):
    forecast,hindcasts,_=build(PRIVATE/'agent-inputs')
    forecast.area_m2.values[:]=1
    forecast.to_netcdf(tmp_path/'forecast.nc');hindcasts.to_netcdf(tmp_path/'hindcasts.nc')
    checks=submission_checks(tmp_path,PRIVATE)
    assert checks['geometry']['state']=='fail'
    assert checks['conservation_and_positivity']['state']=='pass'


def test_read_only_prepare_preserves_frozen_weather_and_manifest():
    files=[STAGE/'tasks/conservative-downscaling/input-manifest.json',*[p for p in PRIVATE.rglob('*') if p.is_file()]]
    before={str(p):(digest(p),p.stat().st_mtime_ns) for p in files}
    result=prepare(STAGE)
    assert result['references_recomputed'] and not result['preparation_writes']
    assert before=={str(p):(digest(p),p.stat().st_mtime_ns) for p in files}
