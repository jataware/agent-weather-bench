import json
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from pilot.checks import compare, weighted, kenya_reference, seasonal_scores, iod_reference
from pilot.common import CRITERIA, inventory
from pilot.judge import validate, completion


def test_numeric_checks_reject_shape_broadcasting_nan_and_wrong_units():
    assert compare([1.,2.],[1.,2.0000001])
    assert not compare([1.],[[1.]])
    assert not compare([float('nan')],[float('nan')])
    assert not compare({'units':'K'},{'units':'degree_Celsius'})
    assert not compare(True,1)
    assert weighted(np.array([[2.,np.nan],[8.,8.]]),np.array([0.,60.])) == pytest.approx(5)


def test_kenya_reference_uses_members_before_spread_and_rejects_missing_days(tmp_path):
    members=np.arange(1,5)
    values=members[:,None,None,None]*np.arange(43)[None,:,None,None]*np.ones((1,1,2,2))
    ds=xr.Dataset({'tp':(('number','step','latitude','longitude'),values)},
                  coords={'number':members,'step':np.arange(43)*np.timedelta64(1,'D'),'latitude':[0.,5.],'longitude':[34.,42.]})
    ds.tp.attrs['units']='kg m**-2'
    ds.to_zarr(tmp_path/'raw.zarr')
    answer=kenya_reference(tmp_path/'raw.zarr','2026-09-27','raw-url')
    np.testing.assert_allclose(answer['regional_median_mm'],17.5)
    np.testing.assert_allclose(answer['regional_spread_mm'],7*np.sqrt(5/3))
    np.testing.assert_allclose(answer['ensemble_mean_mm'],17.5)
    ds.isel(step=slice(1,None)).to_zarr(tmp_path/'missing.zarr')
    with pytest.raises(ValueError,match='leads'): kenya_reference(tmp_path/'missing.zarr','2026-09-27','raw-url')


def test_seasonal_perfect_forecast_and_probability_coverage_gates(tmp_path):
    train=xr.Dataset({'observed':(('year','lat','lon'),np.array([0.,10.,20.])[:,None,None]),
                      'forecast':(('year','member','lat','lon'),np.array([0.,10.,20.])[:,None,None,None])},
                     coords={'year':[2000,2001,2002],'member':[0],'lat':[0.],'lon':[36.]})
    target=train.sel(year=[2002]).assign_coords(year=[2003])
    for ds in [train,target]:
        for v in ds.data_vars: ds[v].attrs['units']='mm'
    pred=xr.Dataset({'probability':(('year','tercile','lat','lon'),np.array([0.,0.,1.])[None,:,None,None]),
                     'rainfall_mm':(('year','lat','lon'),np.array([[[20.]]]))},
                    coords={'year':[2003],'tercile':['below','near','above'],'lat':[0.],'lon':[36.]})
    pred.rainfall_mm.attrs['units']='mm'
    scores=seasonal_scores(pred,target,train)
    assert scores['RPS']['submitted']==0 and scores['RMSE_mm']['submitted']==0
    assert scores['RPS']['climatology']==pytest.approx(5/9)
    assert scores['reliability']['submitted']['gap']==0
    # Additional diagnostic fields must not invalidate correct required arrays.
    from pilot.checks import evaluate
    submission=tmp_path/'submission'; reference=tmp_path/'reference'
    submission.mkdir(); reference.mkdir()
    train.assign(valid_fraction_min=(('lat','lon'),[[1.]])).to_netcdf(submission/'training.nc')
    train.to_netcdf(reference/'training.nc'); target.to_netcdf(reference/'verification.nc')
    pred.to_netcdf(submission/'predictions.nc')
    (reference/'reference.json').write_text(json.dumps({'task':'seasonal','status':'test','sources':[]}))
    checked=evaluate('seasonal',submission,reference)
    assert next(c for c in checked['checks'] if c['id']=='training_aggregation')['passed']
    with pytest.raises(ValueError,match='coverage'): seasonal_scores(pred.assign_coords(year=[2004]),target,train)
    pred.probability.values[:]=.5
    with pytest.raises(ValueError,match='probabilities'): seasonal_scores(pred,target,train)


def test_iod_uses_real_dates_and_fixed_climatology(tmp_path):
    dates=np.concatenate([np.arange(f'{y}-09-24',f'{y}-10-09',dtype='datetime64[D]') for y in range(2013,2024)])
    o=np.zeros((len(dates),1,2)); o[dates>=np.datetime64('2023-01-01'),0,0]=1
    obs=xr.Dataset({'sst':(('time','lat','lon'),o)},coords={'time':dates,'lat':[0.],'lon':[60.,100.]})
    obs.sst.attrs['units']='degree_Celsius'; obs.to_netcdf(tmp_path/'obs.nc')
    valid=np.arange('2023-09-25','2023-10-09',dtype='datetime64[D]')
    f=np.zeros((101,14,1,2)); f[:,:,:,0]=(2+np.arange(101)/100)[:,None,None]
    fc=xr.Dataset({'sst':(('member','valid_date','lat','lon'),f)},coords={'member':np.arange(101),'valid_date':valid,'lat':[0.],'lon':[60.,100.]})
    fc.sst.attrs['units']='degree_Celsius'; fc.to_netcdf(tmp_path/'fc.nc')
    windows=[['2023-09-25','2023-10-01'],['2023-10-02','2023-10-08']]
    answer=iod_reference(tmp_path/'fc.nc',tmp_path/'obs.nc',windows,['source'])
    np.testing.assert_allclose(answer['forecast_dmi_c'],2.5)
    np.testing.assert_allclose(answer['observed_dmi_c'],1)
    np.testing.assert_allclose(answer['error_dmi_c'],1.5)
    fc.assign_coords(valid_date=valid+np.timedelta64(1,'D')).to_netcdf(tmp_path/'shifted.nc')
    with pytest.raises(KeyError): iod_reference(tmp_path/'shifted.nc',tmp_path/'obs.nc',windows,['source'])


def test_judge_cannot_override_numeric_failure_or_cite_invented_evidence():
    judgment={'ratings':{k:{'score':2,'reason':'verified','evidence':['checks'],'uncertainty':''} for k in CRITERIA},'concerns':[],'summary':'ok'}
    validate(judgment,{'checks'})
    checks={'all_mandatory_pass':False,'checks':[{'id':'value:mean','passed':True},{'id':'value:spread','passed':False}]}
    assert completion(checks,judgment,'passed')=='partial'
    assert completion(checks,judgment,'failed')=='failed'
    assert completion(checks,judgment,'unreviewed')=='pending'
    judgment['ratings'][CRITERIA[0]]['evidence']=['invented']
    with pytest.raises(ValueError,match='evidence'): validate(judgment,{'checks'})


def test_submission_symlink_cannot_expose_host_files(tmp_path):
    (tmp_path/'outside-link').symlink_to('/etc/passwd')
    with pytest.raises(ValueError,match='Symlink'): inventory(tmp_path)


def test_launch_pause_precedes_model_or_task_execution(tmp_path, monkeypatch):
    import pilot.runner as runner
    original_read = runner.read
    monkeypatch.setattr(runner, 'read', lambda p: {'status':'paused'} if Path(p).name == 'launch-review.yaml' else original_read(p))
    from pilot.runner import run_attempt
    with pytest.raises(ValueError,match='paused'):
        run_attempt('kenya','scratch','initial','controlled',tmp_path/'run','missing-reference','missing-policy')
    assert not (tmp_path/'run').exists()


def test_truncated_tool_calls_never_execute_and_request_small_chunks():
    from pilot.runner import tool_command
    call={'name':'execute','input':{'command':'echo incomplete > important.py'}}
    command,error=tool_command(call,'max_tokens')
    assert command is None and 'NOT executed' in error and '80 lines' in error
    assert tool_command(call,'tool_use')==('echo incomplete > important.py',None)
    assert tool_command({'name':'execute','input':{}},'tool_use')[0] is None


def test_replay_checks_required_science_not_optional_session_notes():
    from pilot.runner import replay_answer_matches
    original={'method':'regression','development_validation':{'rps':.2},'limitations':'12 years','source_url':['raw'],'reuse_validation':'Reviewed for the next batch'}
    replay={k:v for k,v in original.items() if k!='reuse_validation'}
    assert replay_answer_matches(replay,original,'seasonal')
    replay['development_validation']={'rps':.3}
    assert not replay_answer_matches(replay,original,'seasonal')
