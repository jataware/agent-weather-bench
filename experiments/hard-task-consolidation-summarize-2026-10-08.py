"""Summarize immutable pilot evidence without rerunning agent code or graders."""
from pathlib import Path
import hashlib
import json
ROOT=Path(__file__).resolve().parents[1]


def main():
    folder=ROOT/'var/review/hard-task-consolidation/one-luna-attempt-prelaunch-recovery'
    invocation=json.loads((folder/'invocation.json').read_text());assert invocation['status']=='finished'
    assert invocation['exit_code']==0, 'Preserve and diagnose actual invocation error; do not silently infer success.'
    run=ROOT/invocation['result']['directory'];meta=json.loads((run/'run.json').read_text());assessment=json.loads((run/'assessment.json').read_text())
    events=[json.loads(line) for line in (run/'logs/events.jsonl').read_text().splitlines()]
    acquisition=assessment.get('acquisition',{});probes=acquisition.get('probes',[])
    record={'template':'seasonal-objective-consolidation','run':meta['id'],'system':meta['system'],
            'fingerprint':assessment['fingerprint'],'runtime_status':meta['status'],'completion':assessment['outcome'],
            'computed_outcome':assessment['computed_outcome'],'advisory_outcome':assessment['advisory_outcome'],
            'ranking_outcome':assessment['ranking_outcome'],'checks':{name:row['state'] for name,row in assessment['checks'].items()},
            'usage':meta.get('usage'),'seconds':meta.get('seconds'),'tool_calls':meta.get('tool_calls'),
            'cli_seconds':invocation['cli_wall_seconds'],'direct_paid_api_usd':0,
            'subscription_invoice_cost_usd':None,'agent_retries':0,'actual_model_attempts':1,
            'prelaunch_harness_failures_without_inference':1,
            'prelaunch_failure_evidence':'experiments/hard-task-consolidation-prelaunch-failure-2026-10-08.json',
            'acquisition':{'probe_count':len(probes),'bytes':acquisition.get('bytes'),'seconds':acquisition.get('seconds'),
                           'replay_resources':{p['probe']:p.get('retrieved_resources') for p in probes}},
            'science_validity_is_not_observed_skill':True,'observations_in_source':False,
            'assessment_sha256':hashlib.sha256((run/'assessment.json').read_bytes()).hexdigest(),
            'original_submission_and_assessment_unchanged':True,
            'interpretation':('Luna passed lean canonical objective consolidation, including partial-vector changed-input check. No capability boundary found; bounded round stops.' if assessment['outcome']=='pass' else 'Numerical/contract failure requires diagnosis against frozen controls before any scientific inability claim.')}
    usage=record['usage'] or {}
    if isinstance(usage.get('input_tokens'),int):record['uncached_input_tokens']=usage['input_tokens']-usage.get('cached_input_tokens',0)
    path=ROOT/'experiments/hard-task-consolidation-results-2026-10-08.json';assert not path.exists();path.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
