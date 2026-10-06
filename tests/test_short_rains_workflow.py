"""Scientific contrast tests for the frozen short-rains task contract."""
import json
from pathlib import Path
import shutil

import numpy as np
import pytest
import xarray as xr

from weatherbench.task_tools.short_rains.checks import comparison, submission_checks
from weatherbench.task_tools.short_rains.reference import cpt_quantile, fit_probability

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "var/private/tasks/short-rains-workflow"


@pytest.fixture
def scientific_submission(tmp_path):
    if not PRIVATE.exists():
        pytest.skip("internal frozen short-rains data not installed")
    for name in ("seasonal.nc", "hindcasts.nc", "forecast.nc"):
        shutil.copy2(PRIVATE / "controller" / name, tmp_path / name)
    with xr.open_dataset(tmp_path / "hindcasts.nc") as d:
        metrics = {str(r):{str(s):{"mean_rps":float(d.rps.sel(region=r,system=s).mean()),"rpss":float(d.rpss.sel(region=r,system=s))} for s in d.system.values} for r in d.region.values}
    answer = {"task":"short-rains-workflow","training_years":[1993,2019],"verification_years":list(range(2005,2020)),"prediction_years":list(range(2020,2024)),"region_order":["somalia","kenya","eastern-horn"],"system_order":["climatology","antecedent-iod","forecast-iod","nested-search"],"rainfall_units":"mm","rainfall_recovery_factor":30,"issue_time":"September30","observed_sst_cutoff":"August31","metrics":metrics,"forecast_skill_claim":"withheld targets","limitations":["short retrospective record"]}
    (tmp_path / "answer.json").write_text(json.dumps(answer))
    return tmp_path


def test_independent_reference_and_valid_negative_skill(scientific_submission):
    checks = submission_checks(scientific_submission, PRIVATE)
    assert all(row["state"] == "pass" for row in checks.values())
    # The accepted reference search loses to the forecast IOD in every region;
    # a forecast improvement gate would reject this valid scientific result.
    with xr.open_dataset(scientific_submission / "hindcasts.nc") as d:
        assert (d.rpss.sel(system="nested-search") < d.rpss.sel(system="forecast-iod")).all()


def test_calendar_multiplier_does_not_undo_legacy_conversion(scientific_submission):
    monthly = xr.open_dataset(PRIVATE / "agent-inputs/rainfall.nc").monthly_rainfall_scaled
    seasonal = monthly.sel(time=monthly.time.dt.month.isin([10,11,12]))
    wrong = (seasonal * seasonal.time.dt.days_in_month).groupby("time.year").sum("time")
    wrong.attrs["units"] = "mm"
    wrong.to_dataset(name="seasonal_total").to_netcdf(scientific_submission / "seasonal.nc", mode="w")
    assert submission_checks(scientific_submission,PRIVATE)["seasonal_totals"]["state"] == "fail"


def test_coordinate_swap_rejected_even_when_probabilities_normalized(scientific_submission):
    p = scientific_submission / "forecast.nc"
    with xr.open_dataset(p) as d:
        modified = d.load().sel(region=["kenya","somalia","eastern-horn"])
    modified.to_netcdf(p, mode="w")
    assert submission_checks(scientific_submission,PRIVATE)["production_probabilities"]["state"] == "fail"


def test_wrong_inner_scores_and_retrospective_selection_fail(scientific_submission):
    p = scientific_submission / "hindcasts.nc"
    with xr.open_dataset(p) as d:
        modified = d.load()
    modified.inner_rps.values += .005
    modified.selected_candidate.values[:] = modified.selected_candidate.values[-1]
    modified.to_netcdf(p,mode="w")
    assert submission_checks(scientific_submission,PRIVATE)["inner_selection"]["state"] == "fail"


def test_answer_metrics_checked_separately_from_arrays(scientific_submission):
    p = scientific_submission / "answer.json"
    a = json.loads(p.read_text()); a["metrics"]["somalia"]["nested-search"]["rpss"] = .8
    p.write_text(json.dumps(a))
    assert submission_checks(scientific_submission,PRIVATE)["verification_arithmetic"]["state"] == "fail"


def test_empirical_quantile_distinct_from_numpy_default():
    a = np.array([1.,2.,4.,8.,16.,32.,64.,128.])
    assert cpt_quantile(a,1/3) != np.quantile(a,1/3)


def test_student_t_predictive_leverage_changes_uncertainty():
    x = np.arange(10.)
    y = x + np.array([1.,-.3,.2,-.7,.1,.3,-.5,.9,-.2,.4])
    p = fit_probability(x,y,np.array([4.5,30.]),"identity",np.array([3.,7.]))
    assert np.isfinite(p).all() and np.allclose(p.sum(axis=1),1)
    assert p[1,0] > 0  # Student-t observation uncertainty remains nonzero far away.


def test_nonfinite_complete_support_rejected():
    d = xr.Dataset({"probability":(("year","tercile"),np.array([[.2,.3,.5]]))},coords={"year":[2020],"tercile":["below","normal","above"]})
    changed = d.copy(deep=True); changed.probability.values[0,0]=np.nan
    assert comparison(changed,d,["probability"])[0] is False

@pytest.mark.parametrize('years,accepted',[(list(range(1993,2020)),True),([1993,2019],True),
                                         (list(range(1993,2019)),False),([1993,2020],False),
                                         (['1993','2019'],False)])
def test_training_period_accepts_equivalent_notation_but_rejects_wrong_years(scientific_submission,years,accepted):
    path=scientific_submission/'answer.json'
    answer=json.loads(path.read_text());answer['training_years']=years;path.write_text(json.dumps(answer))
    assert (submission_checks(scientific_submission,PRIVATE)['answer_schema']['state']=='pass') is accepted

@pytest.mark.parametrize('field,start,end',[('verification_years',2005,2019),('prediction_years',2020,2023)])
def test_other_period_notations_preserve_scientific_boundaries(scientific_submission,field,start,end):
    path=scientific_submission/'answer.json';answer=json.loads(path.read_text())
    answer[field]=[start,end];path.write_text(json.dumps(answer))
    assert submission_checks(scientific_submission,PRIVATE)['answer_schema']['state']=='pass'
    answer[field]=[start,end+1];path.write_text(json.dumps(answer))
    assert submission_checks(scientific_submission,PRIVATE)['answer_schema']['state']=='fail'
