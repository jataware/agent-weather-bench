import json

from weatherbench.judge import trace_evidence


def test_scientific_trace_excludes_provider_identity_and_preserves_failed_commands(tmp_path):
    (tmp_path/'logs').mkdir()
    rows=[{'type':'model','response':{'model':'hidden-model','content':[{'text':'hidden reasoning'}]}},
          {'type':'adapter','event':{'type':'usage','usage':{'usd':77}}},
          {'type':'adapter','event':{'type':'execute','command':'python broken.py'}},
          {'type':'tool_result','exit_code':1,'stderr':'ValueError'},
          {'type':'adapter','event':{'type':'execute','command':'python repaired.py'}},
          {'type':'tool_result','exit_code':0,'stdout':'done'}]
    (tmp_path/'logs/events.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    evidence=trace_evidence(tmp_path)
    assert evidence['total_tool_events']==4 and evidence['omitted_tool_events']==0
    assert evidence['events'][1]['exit_code']==1 and evidence['events'][3]['exit_code']==0
    assert 'hidden-model' not in json.dumps(evidence) and 'hidden reasoning' not in json.dumps(evidence)
    assert '"usd"' not in json.dumps(evidence)


def test_trace_explicitly_reports_missing_and_truncated_evidence(tmp_path):
    assert trace_evidence(tmp_path)['available'] is False
    (tmp_path/'logs').mkdir()
    rows=[{'type':'adapter','event':{'type':'execute','command':'x'*4000}} for _ in range(30)]
    (tmp_path/'logs/events.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    evidence=trace_evidence(tmp_path,limit=5000)
    assert evidence['truncated'] and evidence['omitted_tool_events']>0
    assert all(len(row['command'])<=2000 for row in evidence['events'])


def test_development_score_trace_exposes_public_query_not_private_ledger(tmp_path):
    (tmp_path/'logs').mkdir()
    rows=[{'type':'adapter','event':{'type':'score_development','prediction_file':'forecast.nc','provider':'hidden'}},
          {'type':'tool_result','exit_code':0,'stdout':'{"rmse":0.4}',
           'feedback_query':1,'feedback_remaining':2,'feedback_scope':'development_only',
           'prediction_sha256':'abc','private_error':'PRIVATE','snapshot':'/controller/private','usd':77}]
    (tmp_path/'logs/events.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    evidence=trace_evidence(tmp_path)
    assert evidence['events'][0]['tool']=='score_development'
    assert evidence['events'][0]['prediction_file']=='forecast.nc'
    assert evidence['events'][1]['feedback_query']==1
    assert evidence['events'][1]['prediction_sha256']=='abc'
    assert evidence['omitted_tool_events']==0 and evidence['total_tool_events']==2
    assert 'PRIVATE' not in json.dumps(evidence) and 'hidden' not in json.dumps(evidence)
    assert 'snapshot' not in json.dumps(evidence) and '"usd"' not in json.dumps(evidence)


def test_middle_feedback_is_preserved_when_long_trace_is_sampled(tmp_path):
    (tmp_path/'logs').mkdir()
    rows=[{'type':'adapter','event':{'type':'execute','command':f'candidate experiment {i}'}} for i in range(40)]
    rows[20]={'type':'adapter','event':{'type':'score_development','prediction_file':'selected.nc'}}
    rows[21]={'type':'tool_result','exit_code':0,'stdout':'{"rmse":0.4}',
              'feedback_query':1,'feedback_remaining':4,'feedback_scope':'development_only'}
    (tmp_path/'logs/events.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    evidence=trace_evidence(tmp_path,limit=5000)
    indexes=[row['event_index'] for row in evidence['events']]
    assert 20 in indexes and 21 in indexes and 19 in indexes
    assert indexes==sorted(indexes) and evidence['omitted_tool_events']>0


def test_sampled_results_preserve_their_calculation_even_under_budget_pressure(tmp_path):
    (tmp_path/'logs').mkdir()
    rows=[]
    for i in range(20):
        rows.extend([{'type':'adapter','event':{'type':'execute','command':f'calculation {i} ' + 'x'*1900}},
                     {'type':'tool_result','exit_code':0,'stdout':f'result {i} ' + 'y'*1900}])
    rows[20]={'type':'adapter','event':{'type':'score_development','prediction_file':'chosen.nc'}}
    rows[21]['feedback_query']=1
    (tmp_path/'logs/events.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    evidence=trace_evidence(tmp_path,limit=7000)
    indexes={row['event_index'] for row in evidence['events']}
    assert 20 in indexes and 21 in indexes
    assert evidence['omitted_tool_events']>0
    for index in indexes:
        assert (index+1 if index%2==0 else index-1) in indexes
    assert sum(len(json.dumps(row)) for row in evidence['events'])<=7000
