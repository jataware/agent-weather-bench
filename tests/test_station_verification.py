"""Real observation alignment, independent reference and consequential controls."""
from pathlib import Path
import csv
import json
import shutil
import importlib.util
import numpy as np
import pytest
import xarray as xr
from weatherbench.task_tools.station_verification.reference import build, independent, interpolate, observations
from weatherbench.task_tools.station_verification.checks import comparison, answer_from, submission_checks
from weatherbench.task_tools.station_verification.evaluation import change_inputs

ROOT=Path(__file__).resolve().parents[1]
PRIVATE=ROOT/"var/private/tasks/station-verification"

@pytest.fixture
def actual():
    if not (PRIVATE/"agent-inputs/hres.nc").exists():pytest.skip("Frozen actual station subset not installed")
    return build(PRIVATE/"agent-inputs")

@pytest.fixture
def submitted(actual,tmp_path):
    actual.to_netcdf(tmp_path/"scores.nc")
    (tmp_path/"answer.json").write_text(json.dumps(answer_from(actual),allow_nan=False))
    return tmp_path


def test_independent_real_reference(actual):
    other=independent(PRIVATE/"agent-inputs")
    for k in actual:np.testing.assert_allclose(actual[k],other[k],atol=1e-11,rtol=1e-11,equal_nan=True)
    assert np.array_equal(actual.valid_time,actual.init_time.values[:,None]+actual.lead_time.values[None,:])
    assert np.isnan(actual.station_rmse.sel(station="63602099999")).all()
    assert int(actual.station_count.sel(station="63602099999").sum())==0


def test_actual_noaa_units_quality_duplicate_and_exact_time(actual):
    # Nairobi's actual Jan 2 synoptic report has +0156,1; a conflicting FM-15
    # +0160,1 is deliberately not averaged. Jan 2 verifies Jan 1 +24h.
    with (PRIVATE/"agent-inputs/observations.csv").open() as f:
        rows=[r for r in csv.DictReader(f) if r['STATION']=='63740099999' and r['DATE']=='2020-01-02T00:00:00']
    assert any(r['TMP']=='+0156,1' and r['REPORT_TYPE']=='FM-12' for r in rows)
    assert float(actual.observed_temperature.sel(init_time="2020-01-01",lead_time=np.timedelta64(24,'h'),station="63740099999"))==pytest.approx(288.75)
    with (PRIVATE/"agent-inputs/observations.csv").open() as f:
        allrows=list(csv.DictReader(f))
    assert any(r['TMP'].split(',')[1] not in ('1','5') for r in allrows)
    assert any(r['TMP'].split(',')[0]=='+9999' for r in allrows)


def test_parser_rejects_nearby_and_invalid_and_falls_back_after_qc(tmp_path):
    rows=[{'STATION':'A','DATE':'2020-01-01T00:00:00','TMP':'+9999,1','REPORT_TYPE':'FM-12'},
          {'STATION':'A','DATE':'2020-01-01T00:00:00','TMP':'+1000,2','REPORT_TYPE':'FM-12'},
          {'STATION':'A','DATE':'2020-01-01T00:00:00','TMP':'+0010,5','REPORT_TYPE':'FM-15'},
          {'STATION':'A','DATE':'2020-01-02T00:01:00','TMP':'+0020,1','REPORT_TYPE':'FM-12'}]
    with (tmp_path/'observations.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result=observations(tmp_path,np.array(['2020-01-01','2020-01-02'],dtype='datetime64[ns]'),['A'])
    assert result[0,0]==274.15 and np.isnan(result[1,0])


def test_bilinear_known_linear_surface_and_periodic_nearest():
    # Independent analytic surface and explicit periodic seam weights.
    lat=np.array([-10.,10.]);lon=np.array([0.,90.,180.,270.])
    grid=(2*lat[:,None]+3*lon[None,:])[None,None,:,:]
    stations=[{'latitude':0.,'longitude':45.},{'latitude':5.,'longitude':359.}]
    result=interpolate(grid,lat,lon,stations)
    assert result[0,0,0,0]==135
    assert result[1,0,0,0]==-20 # independent nearest tie uses lower index
    assert result[1,0,0,1]==20 # nearest longitude wraps to zero
    assert result[0,0,0,1]==pytest.approx(10+810/90)


def test_correct_all_checks(submitted):
    assert all(v['state']=='pass' for v in submission_checks(submitted,PRIVATE).values())

@pytest.mark.parametrize('variant',['init-time-truth','celsius-as-kelvin','own-support'])
def test_constructed_fault_consequential_and_rejected(actual,submitted,variant):
    changed=actual.copy(deep=True);changed.rmse.values[:]=actual.diagnostic_rmse.sel(variant=variant).values
    assert float(abs(changed.rmse-actual.rmse).max())>.01
    changed.to_netcdf(submitted/'scores.nc',mode='w')
    assert submission_checks(submitted,PRIVATE)['metric_values']['state']=='fail'


def test_unequal_coverage_estimand_and_common_support(actual):
    assert float(abs(actual.equal_station_rmse-actual.rmse).max())>.01
    assert int(actual.support_count.min())<5
    assert np.array_equal(actual.common_support.sum('station'),actual.support_count)
    assert np.array_equal(actual.common_support.sum('init_time'),actual.station_count)


def test_source_broken_fragment_matches_combined_fault(actual):
    spec=importlib.util.spec_from_file_location('broken',ROOT/'tasks/station-verification/source-material/broken-comparison.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    result=module.score(PRIVATE/'agent-inputs',actual.forecast_temperature.values)
    np.testing.assert_allclose(result,actual.diagnostic_rmse.sel(variant='all-three'),atol=1e-11,rtol=1e-11)


def test_counterfactual_forecast_and_mask_probe(actual,tmp_path):
    probe=tmp_path/'probe';shutil.copytree(PRIVATE/'agent-inputs',probe);change_inputs(probe)
    changed=build(probe);other=independent(probe)
    for k in changed:np.testing.assert_allclose(changed[k],other[k],atol=1e-11,rtol=1e-11,equal_nan=True)
    assert float(abs(changed.rmse-actual.rmse).max())>.1
    assert (actual.common_support!=changed.common_support).any()
    assert not comparison(actual,changed)[0]


def test_nan_coordinate_units_and_answer_faults(actual,submitted):
    wrong=actual.copy(deep=True);wrong.station_rmse.loc[{'station':'63602099999'}]=0
    assert not comparison(wrong,actual)[0]
    wrong=actual.copy(deep=True);wrong.rmse.attrs['units']='C'
    assert not comparison(wrong,actual)[0]
    wrong=actual.assign_coords(valid_time=actual.valid_time+np.timedelta64(1,'h'))
    assert not comparison(wrong,actual)[0]
    answer=json.loads((submitted/'answer.json').read_text());answer['metrics']['bilinear']['rmse'][0]+=1
    (submitted/'answer.json').write_text(json.dumps(answer))
    assert submission_checks(submitted,PRIVATE)['answer_metrics']['state']=='fail'
