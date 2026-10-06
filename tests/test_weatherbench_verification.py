"""Consequential scientific contrasts on actual frozen WeatherBench2 fields."""
from pathlib import Path
import json
import shutil
import numpy as np
import pytest
import xarray as xr

from weatherbench.task_tools.weatherbench_verification.reference import build,independent,area_weights
from weatherbench.task_tools.weatherbench_verification.checks import comparison,answer_from,submission_checks
from weatherbench.task_tools.weatherbench_verification.evaluation import change_inputs

ROOT=Path(__file__).resolve().parents[1]
PRIVATE=ROOT/"var/private/tasks/weatherbench-verification"


@pytest.fixture
def actual():
    if not (PRIVATE/"agent-inputs/hres.nc").exists():pytest.skip("Frozen public WB2 subset not installed")
    return build(PRIVATE/"agent-inputs")


@pytest.fixture
def submitted(actual,tmp_path):
    actual.to_netcdf(tmp_path/"scores.nc")
    (tmp_path/"answer.json").write_text(json.dumps(answer_from(actual),allow_nan=False))
    return tmp_path


def test_independent_real_reference(actual):
    independent_result=independent(PRIVATE/"agent-inputs")
    for field in independent_result:
        np.testing.assert_allclose(actual[field].values,independent_result[field].transpose(*actual[field].dims).values,rtol=1e-10,atol=1e-10,equal_nan=True)
    assert np.isnan(actual.acc.sel(system="climatology")).all()
    assert np.array_equal(actual.valid_time,actual.init_time.values[:,None]+actual.lead_time.values[None,:])


def test_correct_submission_and_undefined_acc(submitted):
    assert all(c["state"]=="pass" for c in submission_checks(submitted,PRIVATE).values())
    answer=json.loads((submitted/"answer.json").read_text())
    assert answer["metrics"]["global"]["climatology"]["acc"]==[None]*4


@pytest.mark.parametrize("variant",["init-time-truth","uniform-weight","own-support"])
def test_each_comparison_fault_is_consequential(actual,submitted,variant):
    changed=actual.copy(deep=True)
    changed.rmse.values[:]=actual.diagnostic_rmse.sel(variant=variant).values
    assert np.nanmax(abs(changed.rmse-actual.rmse))>1e-3
    changed.to_netcdf(submitted/"scores.nc",mode="w")
    assert submission_checks(submitted,PRIVATE)["metric_values"]["state"]=="fail"


def test_climatology_acc_zero_is_a_false_scientific_claim(actual):
    changed=actual.copy(deep=True);changed.acc.loc[{"system":"climatology"}]=0
    assert not comparison(changed,actual)[0]


def test_case_rmse_averaging_differs_from_sqrt_average_mse(actual):
    wrong=np.sqrt(actual.case_mse).mean("init_time")
    assert float(abs(wrong-actual.rmse).max())>1e-3


def test_cell_area_cosine_equivalence_and_common_support(actual):
    with xr.open_dataset(PRIVATE/"agent-inputs/hres.nc") as f:
        exact=area_weights(f.latitude.values);cosine=np.cos(np.deg2rad(f.latitude.values))
    np.testing.assert_allclose(exact/exact.sum(),cosine/cosine.sum(),rtol=1e-12,atol=1e-12)
    assert int(actual.support_count.sel(region="global").min())<64*32
    assert float(actual.support_area_fraction.max())<=1+1e-12


def test_counterfactual_changes_metrics_and_catches_cached_output(actual,tmp_path):
    probe=tmp_path/"inputs";shutil.copytree(PRIVATE/"agent-inputs",probe)
    change_inputs(probe);changed=build(probe)
    assert float(abs(changed.rmse-actual.rmse).max())>.005
    assert not comparison(actual,changed)[0]
    assert (changed.support_count!=actual.support_count).any()


def test_answer_metrics_are_independently_checked(submitted):
    path=submitted/"answer.json";answer=json.loads(path.read_text())
    answer["metrics"]["global"]["hres"]["rmse"][0]+=1
    path.write_text(json.dumps(answer))
    assert submission_checks(submitted,PRIVATE)["answer_metrics"]["state"]=="fail"


def test_supplied_broken_script_matches_combined_fault_reference(actual):
    import importlib.util
    spec=importlib.util.spec_from_file_location("broken",ROOT/"tasks/weatherbench-verification/source-material/broken-comparison.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    buggy=module.score(PRIVATE/"agent-inputs")
    for region in actual.region.values:
        for system in actual.system.values:
            np.testing.assert_allclose(buggy[str(region)][str(system)],actual.diagnostic_rmse.sel(variant="all-three",region=region,system=system).values,rtol=1e-10,atol=1e-10)
