import json
from pathlib import Path
import numpy as np
import pytest
import xarray as xr
from weatherbench.task_tools.subseasonal.metrics import weighted_rmse,validate_prediction,score_development
from weatherbench.task_tools.subseasonal.baseline import fit,predict


def data(n=40):
    time=np.datetime64('2010-01-07')+np.arange(n)*np.timedelta64(7,'D')
    ds=xr.Dataset({'raw_cfsv2':(('issue_time','location'),np.arange(n*2).reshape(n,2)/10+2)},coords={'issue_time':time,'location':[0,1],'latitude':('location',[33.,36.]),'longitude':('location',[246.,249.]),'target_start':('issue_time',time+np.timedelta64(14,'D'))})
    ds['precipitation']=ds.raw_cfsv2*.5+3
    ds.precipitation.attrs['units']='mm'
    return ds


def test_metric_independent_scalar_sum_and_not_mean_location_rmse():
    forecast=np.array([[0.,6.],[4.,8.]]);truth=np.array([[1.,2.],[4.,3.]]);latitude=[0.,60.]
    manual=sum(np.cos(np.deg2rad(latitude[j]))*(forecast[i,j]-truth[i,j])**2 for i in range(2) for j in range(2))
    expected=np.sqrt(manual/(2*sum(np.cos(np.deg2rad(latitude)))))
    assert weighted_rmse(forecast,truth,latitude)==pytest.approx(expected)
    assert weighted_rmse(forecast,truth,latitude)!=pytest.approx(np.sqrt(((forecast-truth)**2).mean(axis=0)).mean())


def test_invalid_support_does_not_drop_cases():
    with pytest.raises(ValueError):weighted_rmse([[np.nan,1]],[[2,3]],[30,40])
    with pytest.raises(ValueError):weighted_rmse([[1]],[[2,3]],[30,40])


@pytest.mark.parametrize('defect',['negative','nan','unit','grid','calendar','shape'])
def test_prediction_schema_rejects_meaningful_defects(tmp_path,defect):
    expected=data().drop_vars('raw_cfsv2');out=expected.copy(deep=True)
    if defect=='negative':out.precipitation.values[0,0]=-1
    if defect=='nan':out.precipitation.values[0,0]=np.nan
    if defect=='unit':out.precipitation.attrs['units']='mm/day'
    if defect=='grid':out=out.assign_coords(latitude=('location',[36.,33.]))
    if defect=='calendar':out=out.assign_coords(target_start=out.target_start+np.timedelta64(1,'D'))
    if defect=='shape':out=out.isel(issue_time=slice(1,None))
    path=tmp_path/'prediction.nc';out.to_netcdf(path)
    with pytest.raises(ValueError):validate_prediction(path,expected)


def test_saved_state_works_without_targets_and_changes_consistent_with_fit():
    train=data();state=fit(train);features=train.drop_vars('precipitation');before=predict(features,state)
    changed=features.copy(deep=True);changed.raw_cfsv2.values+=10
    after=predict(changed,state)
    assert np.max(abs(after.precipitation-before.precipitation))>1
    np.testing.assert_allclose(predict(train,state).precipitation,train.precipitation,atol=1e-10)
    # Legitimate climatology does not depend on raw forecast, so no mandatory response gate.
    np.testing.assert_array_equal(predict(features,state,'climatology').precipitation,predict(changed,state,'climatology').precipitation)


def test_development_callback_never_reads_final_labels(tmp_path):
    c=tmp_path/'controller';c.mkdir();ds=data();ds.drop_vars('raw_cfsv2').to_netcdf(c/'development-targets.nc')
    xr.Dataset({'raw_cfsv2':ds.raw_cfsv2,'climatology':ds.precipitation+1}).to_netcdf(c/'development-baselines.nc')
    path=tmp_path/'prediction.nc';ds.drop_vars('raw_cfsv2').to_netcdf(path)
    metrics=score_development(path,tmp_path)
    assert metrics['rmse_mm']==0 and metrics['rmse_skill_vs_climatology']==1
    assert not any('final' in k for k in metrics)
    assert all(np.isfinite(v) for v in metrics.values())


def test_real_frozen_boundaries_and_weekday_are_causally_separated():
    root=Path(__file__).resolve().parents[1]/'var/private/tasks/subseasonal-optimization/agent-inputs'
    if not root.exists():pytest.skip('Private real source snapshot is local-only')
    with xr.open_dataset(root/'training.nc') as f:train=f.load()
    with xr.open_dataset(root/'development-features.nc') as f:dev=f.load()
    with xr.open_dataset(root/'final-features.nc') as f:final=f.load()
    assert np.max(train.target_start.values+np.timedelta64(14,'D'))<np.min(dev.issue_time.values)
    assert np.max(dev.target_start.values+np.timedelta64(14,'D'))<np.min(final.issue_time.values)
    assert 'precipitation' not in dev and 'precipitation' not in final
    assert np.all(train.issue_time.values.astype('datetime64[D]').astype(int)%7==3)
    assert np.all(dev.issue_time.values.astype('datetime64[D]').astype(int)%7==3)
    assert np.all(final.issue_time.values.astype('datetime64[D]').astype(int)%7==3)


def test_default_prepare_verifies_without_rewriting_frozen_bytes():
    from weatherbench.task_tools.subseasonal.prepare import prepare,digest
    repo=Path(__file__).resolve().parents[1]
    private=repo/'var/private/tasks/subseasonal-optimization'
    manifest=repo/'tasks/subseasonal-optimization/input-manifest.json'
    if not private.exists():pytest.skip('Private real source snapshot is local-only')
    files=[manifest,*[p for p in private.rglob('*') if p.is_file()]]
    before={str(p):(digest(p),p.stat().st_mtime_ns) for p in files}
    result=prepare(repo)
    assert isinstance(result,dict) and result['references_recomputed']
    assert result['preparation_writes'] is False
    assert result['issues']=={'training':831,'development':147,'final':208}
    assert before=={str(p):(digest(p),p.stat().st_mtime_ns) for p in files}


def test_default_prepare_refuses_missing_file_without_repair(tmp_path):
    import shutil
    from weatherbench.task_tools.subseasonal.prepare import prepare
    repo=Path(__file__).resolve().parents[1]
    private=repo/'var/private/tasks/subseasonal-optimization'
    package=repo/'tasks/subseasonal-optimization'
    if not private.exists():pytest.skip('Private real source snapshot is local-only')
    shutil.copytree(private,tmp_path/'var/private/tasks/subseasonal-optimization')
    shutil.copytree(package,tmp_path/'tasks/subseasonal-optimization')
    missing=tmp_path/'var/private/tasks/subseasonal-optimization/agent-inputs/training.nc'
    missing.unlink()
    manifest=tmp_path/'tasks/subseasonal-optimization/input-manifest.json'
    before=manifest.read_bytes()
    with pytest.raises(ValueError,match='Frozen data bytes differ or are missing'):
        prepare(tmp_path)
    assert not missing.exists() and manifest.read_bytes()==before
