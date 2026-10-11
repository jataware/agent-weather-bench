"""Scientific attainability and separation of the audit task's interventions."""
import shutil
import json
import numpy as np
import pytest
from assessment.spec import ROOT, Template

needs_data=pytest.mark.skipif(not (ROOT/'var/private/templates/seasonal-forecast-audit/agent-inputs/targets.nc').is_file(),reason='Frozen audit inputs absent; run assessment prepare seasonal-forecast-audit')


@needs_data
def test_independent_candidate_reconstruction_covers_clean_and_faulted_cases(tmp_path):
    template=Template('seasonal-forecast-audit');h=template.hooks
    for p in h.candidate_instances():
        inputs=tmp_path/p['id'];h.stage_inputs(template.private,p,inputs)
        first=h.module('candidate_science').original(inputs);second=h.module('reference_independent').original(inputs)
        np.testing.assert_allclose(first,second,rtol=0,atol=np.finfo(np.float64).eps*1000000*10000)
        assert h.expected_claims(h.module('science').repaired(inputs),p)['original_report_supported']==[['yes' if p['id']=='case-a' else 'no']]

    regression=h.regression_checks(tmp_path/'regression')
    assert all(row['passed'] for row in regression)
    json.dumps(regression)  # certificate evidence must use serializable builtin scalars


@needs_data
def test_interventions_allow_later_learning_but_separate_leaked_evaluation(tmp_path):
    template=Template('seasonal-forecast-audit');h=template.hooks;p=template.instance('case-c')
    original=tmp_path/'original';h.stage_inputs(template.private,p,original);science=h.module('science')
    for cut in range(2005,2020):
        changed=tmp_path/str(cut);shutil.copytree(original,changed);h.perturb_inputs(changed,20261006,'cut_'+str(cut))
        length=cut-2004
        for method in ('ridge','climatology'):
            a=science.repaired(original,method=method);b=science.repaired(changed,method=method)
            np.testing.assert_array_equal(a['hindcast_mm'][:length],b['hindcast_mm'][:length])
            if cut<2019:assert np.max(np.abs(a['hindcast_mm'][length:]-b['hindcast_mm'][length:]))>1
        if cut in (2006,2007):
            a=science.repaired(original,defect='localized_lookahead');b=science.repaired(changed,defect='localized_lookahead')
            assert np.max(np.abs(a['hindcast_mm'][:length]-b['hindcast_mm'][:length]))>1
        for defect in ('global_preprocessing','global_selection','uses_targets','global_future_features'):
            a=science.repaired(original,defect=defect);b=science.repaired(changed,defect=defect)
            gap=np.max(np.abs(a['hindcast_mm'][:length]-b['hindcast_mm'][:length]))
            assert gap<1e-6 if defect=='global_selection' and cut in (2017,2018) else gap>1


@needs_data
def test_no_skill_improvement_threshold_and_report_scope_is_distinct(tmp_path):
    template=Template('seasonal-forecast-audit');h=template.hooks;p=template.instance('case-d')
    inputs=tmp_path/'inputs';h.stage_inputs(template.private,p,inputs)
    values=h.module('science').repaired(inputs,method='climatology')
    claims=h.expected_claims(values,p)
    assert claims['original_hindcast_is_past_only']==[['yes']]
    assert claims['original_report_supported']==[['no']]
    assert claims['repaired_beats_climatology']==[['no']]
    for rule in h.INVARIANTS.values():assert rule(values,p,inputs)[0]
    assert h.score(values,p,template.private)['skill_vs_climatology']==pytest.approx(0,abs=1e-12)


@needs_data
def test_each_production_boundary_excludes_later_features(tmp_path):
    template=Template('seasonal-forecast-audit');h=template.hooks;p=template.instance('case-a')
    original=tmp_path/'original';h.stage_inputs(template.private,p,original);science=h.module('science')
    for year in (2021,2022,2023):
        changed=tmp_path/str(year);shutil.copytree(original,changed)
        h.perturb_inputs(changed,20261006,'later_forecast' if year==2022 else 'production_'+str(year))
        for method in ('ridge','climatology'):
            a=science.repaired(original,method=method);b=science.repaired(changed,method=method)
            np.testing.assert_array_equal(a['forecast_mm'][:year-2020],b['forecast_mm'][:year-2020])
        a=science.repaired(original,defect='pooled_features');b=science.repaired(changed,defect='pooled_features')
        assert np.max(np.abs(a['forecast_mm'][:year-2020]-b['forecast_mm'][:year-2020]))>1e-3
        if year==2021:
            a=science.repaired(original,defect='localized_production_features');b=science.repaired(changed,defect='localized_production_features')
            assert np.max(np.abs(a['forecast_mm'][:1]-b['forecast_mm'][:1]))>1


@needs_data
def test_subtolerance_metric_change_cannot_manufacture_skill_claim(tmp_path):
    template=Template('seasonal-forecast-audit');h=template.hooks;p=template.instance('case-a')
    inputs=tmp_path/'inputs';h.stage_inputs(template.private,p,inputs)
    values=h.module('science').repaired(inputs,method='climatology')
    values['hindcast_rmse_mm']=values['climatology_rmse_mm']-1e-6
    assert h.INVARIANTS['metric_identity'](values,p,inputs)[0]
    assert h.expected_claims(values,p)['repaired_beats_climatology']==[['no']]
    assert h.score(values,p,template.private)['skill_vs_climatology']==pytest.approx(0,abs=1e-12)
