"""One fresh scientific process: locked baseline verification and score checks."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment.spec import Template


def main():
    template = Template('mam-forecast-synthesis'); hooks = template.hooks
    params = hooks.candidate_instances()[0]; hooks.prepare(template.private)
    lockpath = template.private / 'controller/expert-lock.json'
    lock = json.loads(lockpath.read_text())
    if hashlib.sha256((template.folder/'science.py').read_bytes()).hexdigest() != lock['method_code_sha256']:
        raise ValueError('Expert code changed after selection lock')
    if hashlib.sha256((ROOT/'experiments/hard-task-mam-expert-design-2026-10-08.json').read_bytes()).hexdigest() != lock['predeclared_design_sha256']:
        raise ValueError('Predeclared design changed after selection lock')
    scores = {}; worst = 0.
    for name in ('expert','climatology','raw_models'):
        result = hooks.baseline_results(template.private, params, name)
        primary = hooks.score(result, params, template.private, 'blind_years')
        independent = hooks.independent_score(result, params, template.private, 'blind_years')
        worst = max(worst, *(abs(primary[k]-independent[k]) for k in primary if isinstance(primary[k],float)))
        assert np.max(np.abs(np.asarray(primary['annual_rps'])-np.asarray(independent['annual_rps']))) < 1e-9
        scores[name] = primary
    checks = hooks.regression_checks(ROOT/'var/review/hard-task-synthesis/regression')
    assert all(row['passed'] for row in checks), checks
    assert worst < 1e-9
    expert = scores['expert']; delta = expert['climatology_rps'] - expert['rps']
    gate = lock['selected']['alpha'] > 0 and delta >= .01
    # Circular moving-block intervals sample years, not spatial cells.
    rng = np.random.default_rng(8102026)
    differences = np.asarray(expert['annual_rps'])-np.asarray(expert['annual_climatology_rps'])
    sampled = []
    for _ in range(2000):
        starts = rng.integers(0,12,size=6)
        indices = np.asarray([(start+offset)%12 for start in starts for offset in (0,1)])
        sampled.append(float(differences[indices].mean()))
    record = {'template': template.name, 'expert_lock_sha256': hashlib.sha256(lockpath.read_bytes()).hexdigest(),
              'design_sha256': lock['predeclared_design_sha256'], 'selected': lock['selected'],
              'scores': scores, 'score_implementation_max_gap': worst, 'regression_checks': checks,
              'expert_improvement_over_climatology': delta, 'predeclared_inference_gate_passed': gate,
              'annual_expert_minus_climatology': differences.tolist(),
              'paired_year_block_bootstrap_95_percent_interval': list(map(float,np.quantile(sampled,[.025,.975]))),
              'bootstrap': {'unit':'year','circular_block_length':2,'replicates':2000,'seed':8102026},
              'interpretation': 'Candidate informative enough for one attempt' if gate else 'Candidate uninformative by predeclared gate; no Luna attempt; no retuning'}
    path = ROOT/'experiments/hard-task-mam-baseline-verification-2026-10-08.json'
    if path.exists():
        raise ValueError('Do not overwrite original score evidence')
    path.write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'selected':lock['selected'],'rps':{name:value['rps'] for name,value in scores.items()},
                      'improvement':delta,'inference_gate':gate,'score_gap':worst,'checks':checks},indent=2))


if __name__ == '__main__':
    main()
