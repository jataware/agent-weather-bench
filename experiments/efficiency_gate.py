"""Evaluate the predeclared replication gate; never launch a model."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from efficiency_summarize import summarize

def main():
    result = summarize()
    rows = [r for r in result['rows'] if r['replication'] == 1]
    assert len(rows) == 2 and not result['pending'], 'Initial pair is not complete'
    python = next(r for r in rows if r['assigned_arm'] == 'python')
    guided = next(r for r in rows if r['assigned_arm'] == 'guided_accord')
    review = guided['tool_review']
    improvements = {}
    for name, key in [('fresh_input_plus_output','fresh_input_plus_output_tokens'), ('agent_seconds','agent_seconds')]:
        a, b = python[key], guided[key]
        improvements[name] = (a-b)/a if a is not None and b is not None and a > 0 else None
    a, b = (python['usage'] or {}).get('total_tokens'), (guided['usage'] or {}).get('total_tokens')
    improvements['cumulative_tokens'] = (a-b)/a if a is not None and b is not None and a>0 else None
    conditions = {'guided_computed_pass':guided['computed']=='pass',
                  'guided_substantive_helpers':review.get('condition_compliance',{}).get('state')=='pass',
                  'guided_replay_pass':(guided['replay'] or {}).get('state')=='pass',
                  'no_known_grader_runtime_issue_both_initial_arms':review.get('both_initial_arms_runtime_and_grading_clearance') is True}
    informative = python['computed'] == 'fail' or any(v is not None and v >= .10 for v in improvements.values())
    gate = {'schema_version':1,'plan_sha256':result['plan_sha256'],'initial_runs':[r['run'] for r in rows],
            'required_conditions':conditions,'relative_resource_improvements_guided':improvements,
            'baseline_computed':python['computed'],'informative_improvement':informative,
            'eligible':all(conditions.values()) and informative,
            'launch_requires_shared_scientific_slot_coordination':True,
            'replication_pairs_authorized':1 if all(conditions.values()) and informative else 0,
            'interpretation':'Practical bounded replication gate, not statistical significance; missing evidence never satisfies a condition.'}
    (ROOT/'experiments/efficiency_replication_gate_2026-10-08.json').write_text(json.dumps(gate,indent=2)+'\n')
    print(json.dumps(gate,indent=2))

if __name__=='__main__':
    main()
