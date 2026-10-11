"""Read-only integrity validation and explicit-arm efficiency accounting."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment.storage import digest, inventory
from assessment.spec import Template
from experiments.evidence_contracts import contract_status

def read(path):
    return json.loads(path.read_text())

def transfer(log):
    if not log or not log.get('log_path'):
        return {'evidence': 'unavailable', 'requests': None, 'successful_get_bytes': None}
    path = Path(log['log_path'])
    assert digest(path) == log['log_sha256'], path
    events = [json.loads(line) for line in path.read_text().splitlines()]
    responses = [e for e in events if e.get('method') == 'GET' and e.get('status') == 200]
    return {'evidence': 'verified', 'log_path': str(path), 'log_sha256': log['log_sha256'],
            'requests': len(responses), 'successful_get_bytes': sum(e.get('bytes', 0) for e in responses)}

def summarize(precision=False):
    plan_name = 'efficiency_precision_plan_2026-10-08.json' if precision else 'efficiency_plan_2026-10-08.json'
    plan = read(ROOT / 'experiments' / plan_name)
    review_path = ROOT / 'experiments' / ('efficiency_precision_tool_review_2026-10-08.json' if precision else 'efficiency_tool_review_2026-10-08.json')
    reviews = read(review_path).get('runs', {}) if review_path.exists() else {}
    template = Template(plan['template'])
    plan_contract_status = contract_status(template, plan['fingerprint'])
    invocations = {}
    invocation_folder = 'var/review/mam-efficiency-precision-20261008' if precision else 'var/review/mam-efficiency-20261008'
    for path in (ROOT / invocation_folder).glob('*/invocation.json'):
        invocation = read(path)
        if invocation.get('result'):
            invocations[invocation['result']['run']] = invocation
    rows, pending, seen = [], [], set()
    for folder in sorted((ROOT / 'var/template-runs').glob('*mam-multimodel-outlook*')):
        meta = read(folder / 'run.json')
        if meta['system'] not in plan['systems']:
            continue
        assert meta['system'] not in seen, 'Undeclared duplicate attempt'
        seen.add(meta['system'])
        if meta['status'] in ('created', 'running') or not (folder / 'assessment.json').exists():
            pending.append(meta['id'])
            continue
        assignment = plan['systems'][meta['system']]
        a = read(folder / 'assessment.json')
        assert meta['fingerprint'] == a['fingerprint'] == plan['fingerprint']
        assert meta['system_sha256'] == assignment['files']['system.yaml']
        for directory, manifest in [('frozen', 'artifacts.json'), ('inputs', 'input-manifest.json'), ('system', 'substrate-manifest.json')]:
            assert inventory(folder / directory) == read(folder / manifest), (meta['id'], directory)
        provenance = read(folder / 'controller/provenance.json')
        trace = folder / 'logs/events.jsonl'
        if trace.exists():
            assert digest(trace) == provenance['trace']['sha256']
        events = [json.loads(line) for line in trace.read_text().splitlines()] if trace.exists() else []
        command = sum(e.get('seconds', 0) for e in events if e.get('type') == 'tool_result')
        acquisition = a.get('acquisition', {})
        probes = acquisition.get('probes', [])
        assert all(p.get('evidence_persisted') for p in probes)
        initial = provenance['sandbox'].get('acquisition') or {}
        initial_transfer = transfer(initial)
        replay_transfer = [transfer(p) for p in probes]
        usage = meta.get('usage')
        fresh = max(0, usage.get('input_tokens', 0) - usage.get('cached_input_tokens', 0)) if usage else None
        invocation = invocations.get(meta['id'], {})
        rows.append({'run': meta['id'], 'system': meta['system'], 'assigned_arm': assignment['arm'],
                     'replication': assignment['replication'], 'directory': str(folder.relative_to(ROOT)),
                     'status': meta['status'], 'reason': meta.get('reason'), 'computed': a['computed_outcome'],
                     'overall': a['outcome'], 'supplementary': a['advisory_outcome'],
                     'failed_checks': [k for k,v in a['checks'].items() if v['state']=='fail'],
                     'unresolved_checks': [k for k,v in a['checks'].items() if v['state']=='unresolved'],
                     'replay': a['checks'].get('probe.replay'), 'usage': usage,
                     'uncached_input_tokens': fresh,
                     'fresh_input_plus_output_tokens': fresh + usage.get('output_tokens',0) if usage else None,
                     'agent_seconds': meta.get('seconds'), 'command_seconds': command,
                     'model_adapter_transport_overhead_proxy_seconds': max(0,meta['seconds']-command) if meta.get('seconds') is not None else None,
                     'cli_assessment_seconds': invocation.get('cli_wall_seconds'),
                     'controller_assessment_overhead_proxy_seconds': max(0, invocation['cli_wall_seconds']-meta['seconds']) if invocation.get('cli_wall_seconds') is not None and meta.get('seconds') is not None else None,
                     'tool_calls': meta.get('tool_calls'), 'initial_transfer': initial_transfer,
                     'replay_transfer': replay_transfer, 'tool_review': reviews.get(meta['id'], {'status':'pending'}),
                     'invocation': invocation})
    arms = {}
    for arm in ('python','guided_accord'):
        assigned = [r for r in rows if r['assigned_arm']==arm]
        valid = sum(r['computed']=='pass' for r in assigned)
        fresh = sum(r['fresh_input_plus_output_tokens'] or 0 for r in assigned)
        known_usage = all(r['usage'] is not None for r in assigned)
        arms[arm] = {'assigned_attempts':len(assigned),'scientifically_valid_completions':valid,
                     'unknown_usage_runs':[r['run'] for r in assigned if r['usage'] is None],
                     'token_totals':{k:sum(r['usage'][k] for r in assigned) if known_usage and all(k in r['usage'] for r in assigned) else None for k in ('input_tokens','cached_input_tokens','cache_write_input_tokens','output_tokens','reasoning_output_tokens','total_tokens')},
                     'known_fresh_input_plus_output_lower_bound':fresh,
                     'fresh_input_plus_output_including_failures':fresh if known_usage else None,
                     'fresh_input_plus_output_per_valid_completion':fresh/valid if valid and known_usage else None,
                     'agent_seconds_including_failures':sum(r['agent_seconds'] for r in assigned) if all(r['agent_seconds'] is not None for r in assigned) else None,
                     'cli_seconds_including_failures':sum(r['cli_assessment_seconds'] for r in assigned) if all(r['cli_assessment_seconds'] is not None for r in assigned) else None}
    comparison = None
    if len(rows) == 2 and len({r['assigned_arm'] for r in rows}) == 2:
        baseline = next(r for r in rows if r['assigned_arm']=='python')
        guided = next(r for r in rows if r['assigned_arm']=='guided_accord')
        reductions = {}
        for label, key in [('fresh_input_plus_output','fresh_input_plus_output_tokens'),('agent_time','agent_seconds'),('command_time','command_seconds'),('full_cli_time','cli_assessment_seconds')]:
            a,b = baseline[key],guided[key]
            reductions[label] = (a-b)/a if a is not None and b is not None and a>0 else None
        for key in ('input_tokens','cached_input_tokens','output_tokens','total_tokens'):
            a,b = (baseline['usage'] or {}).get(key),(guided['usage'] or {}).get(key)
            reductions[key] = (a-b)/a if a is not None and b is not None and a>0 else None
        a,b = baseline['uncached_input_tokens'],guided['uncached_input_tokens']
        reductions['uncached_input_tokens'] = (a-b)/a if a is not None and b is not None and a>0 else None
        active = [reductions[k] for k in ('uncached_input_tokens','cached_input_tokens','output_tokens')]
        zero_writes = all((r['usage'] or {}).get('cache_write_input_tokens')==0 for r in rows)
        dominated = zero_writes and all(v is not None and v>0 for v in active)
        comparison = {'guided_relative_resource_reductions':reductions,
                      'baseline_computed':baseline['computed'],'guided_computed':guided['computed'],
                      'variable_token_charge_proxy':{'all_three_active_components_lower':dominated,
                        'hypothetical_rate_weighted_reduction_bounds':{'minimum':min(active),'maximum':max(active)} if dominated else None,
                        'formula':'fresh_input * p_fresh + cached_input * p_cached + output * p_output',
                        'assumptions':'Same model, nonnegative rates, positive billed denominator, only these three active metered classes, no fixed or tool fees. Both reported cache-write counts are zero. Reasoning is already inside output.',
                        'interpretation':'Hypothetical per-attempt variable token charge, not subscription invoice, dollars saved, or a reliable cost per valid completion.'},
                      'interpretation':'One fresh matched pair; descriptive resource and completion differences, not statistical significance.'}
    return {'schema_version':1,'plan':'experiments/'+plan_name, 'contract_status':plan_contract_status,
            'plan_sha256':digest(ROOT/'experiments'/plan_name),
            'fingerprint':plan['fingerprint'],'rows':rows,'pending':pending,'by_arm':arms,'paired_comparison':comparison,
            'direct_paid_api_usd':0,'subscription_invoice_usd':None,
            'interpretation':'Bundle comparison on one instance; no significance, dollar savings or cross-instance generalization claimed.'}

def all_phases():
    phases = {'initial_v1':summarize(), 'precision_clarification_v2':summarize(precision=True)}
    rows = [dict(row, phase=phase) for phase, data in phases.items() for row in data['rows']]
    known = all(row['usage'] is not None for row in rows)
    return {'schema_version':1, 'phases':phases, 'all_attempts_ledger':rows,
            'recorded_attempts':len(rows), 'maximum_authorized_attempts':4,
            'pending':[run for data in phases.values() for run in data['pending']],
            'token_totals_including_failures':{key:sum(row['usage'][key] for row in rows) if known and all(key in row['usage'] for row in rows) else None
                for key in ('input_tokens','cached_input_tokens','cache_write_input_tokens','output_tokens','reasoning_output_tokens','total_tokens')},
            'direct_paid_api_usd':0, 'subscription_invoice_usd':None,
            'interpretation':'All attempts count toward investigation resources. Scientific completion and success-adjusted efficiency remain phase-specific because the grading version and common precision instruction changed. No third pair.'}

if __name__ == '__main__':
    precision = '--precision' in sys.argv[1:]
    combined = '--all-phases' in sys.argv[1:]
    result=all_phases() if combined else summarize(precision=precision)
    output_name = 'efficiency_all_phases_results_2026-10-08.json' if combined else 'efficiency_precision_results_2026-10-08.json' if precision else 'efficiency_results_2026-10-08.json'
    (ROOT/'experiments'/output_name).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','phases','all_attempts_ledger')},indent=2))
