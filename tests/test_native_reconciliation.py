"""Verify source transformations against original provider weather, independently of graders."""
import json,hashlib
from pathlib import Path
import numpy as np
import pytest
import xarray as xr
from assessment.spec import ROOT,Template

DATA=ROOT/'var/private/templates/native-rainfall-reconciliation/agent-inputs'
OLD=ROOT/'var/private/templates/kenya-forecast-revision/stores/ECMWF_s2s_precip_2026-09-20.zarr'
pytestmark=pytest.mark.skipif(not DATA.exists() or not OLD.exists(),reason='Frozen real source snapshots unavailable')


def test_derived_interval_delivery_preserves_real_source_endpoint_amounts():
    with xr.open_dataset(DATA/'previous-interval-rates.nc',engine='h5netcdf') as d:
        with xr.open_zarr(OLD,chunks=None,consolidated=False) as raw:
            r=raw.sel(latitude=d.lat.values,longitude=d.lon.values)
            dates=(r.time.values+r.step.values).astype('datetime64[D]')
            for interval,(start,end) in enumerate(d.time_bounds.values.astype('datetime64[D]')):
                i=int(np.flatnonzero(dates==start)[0]);j=int(np.flatnonzero(dates==end)[0]);days=int((end-start)/np.timedelta64(1,'D'))
                expected=(r.tp.isel(step=j)-r.tp.isel(step=i)).transpose('number','latitude','longitude').values.astype(float)
                actual=d.rain_rate.isel(interval=interval).transpose('member','lat','lon').values*days
                assert np.array_equal(actual,expected)
            assert d.rain_rate.attrs['units']=='mm day-1'
            assert set(np.diff(d.time_bounds.values,axis=1).ravel()/np.timedelta64(1,'D'))=={1,2}


def test_current_delivery_retains_provider_objects_and_both_pitfalls_are_separated(tmp_path):
    original=json.loads((ROOT/'templates/kenya-forecast-revision/sources.json').read_text())['stores']['ECMWF_s2s_precip_2026-09-27.zarr']
    for row in original['objects']:
        p=DATA/'ECMWF_s2s_precip_2026-09-27.zarr'/row['path']
        assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
    template=Template('native-rainfall-reconciliation');params=template.instance('service-area--weeks-1-2');inputs=tmp_path/'inputs';template.hooks.stage_inputs(template.private,params,inputs)
    correct=template.hooks.reference(inputs,params,{'integration':'duration_weighted','alignment':'valid_time'})
    for conventions in ({'integration':'sum_rates','alignment':'valid_time'},{'integration':'duration_weighted','alignment':'same_lead'}):
        wrong=template.hooks.reference(inputs,params,conventions)
        assert np.max(np.abs(wrong['previous_mean_mm']-correct['previous_mean_mm']))>template.spec['results']['previous_mean_mm']['tolerance']['atol']*100
