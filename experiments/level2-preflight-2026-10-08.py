"""Trusted Level 2 interface preflight; actor solution executes only in Docker."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment.assess import assess
from assessment.execute import Docker
from assessment.feedback import DevelopmentFeedback
from assessment.runner import development_scorer
from assessment.runtime import ToolSandbox
from assessment.spec import Template
from assessment.storage import digest, inventory


def main():
    image = 'sha256:08dbb4fce25955523a4c3caa3e2efdfb75b960dae3d2b8f3b92746e7f19f7c49'
    template = Template('weeks34-rainfall')
    before = template.fingerprint()
    certificate = json.loads((template.folder / 'certification.json').read_text())
    assert certificate['fingerprint'] == before and certificate['automatic_tests_passed']
    params = template.instance('final-2018-2021--all-cells')
    folder = ROOT / 'var/review/level2-preflight-20261008'
    folder.mkdir(parents=True, exist_ok=False)
    inputs, work, task, substrate = [folder / name for name in ('inputs', 'work', 'task', 'substrate')]
    for path in (inputs, work / 'submission', work / 'state', task, substrate):
        path.mkdir(parents=True)
    template.hooks.stage_inputs(template.private, params, inputs)
    (task / 'brief.md').write_text(template.brief(params, level=2))
    (task / 'envelope.md').write_text((ROOT / 'assessment/envelope.md').read_text())
    shutil.copy2(template.folder / 'controls/solve.py', work / 'submission/solve.py')
    (work / 'submission/report.md').write_text('Trusted public-interface preflight control; seasonal harmonics plus the raw forecast, fitted on training observations. No agent attempt.\n')
    input_before = inventory(inputs)
    scorer_calls = []
    callback = development_scorer(template, params, inputs)

    def score(store):
        metrics = callback(store)
        scorer_calls.append({'store': str(store.relative_to(folder)), 'metrics': metrics})
        return metrics

    feedback = DevelopmentFeedback(work, folder / 'controller/development-feedback', score, max_submissions=5)
    execute, replies = [], []
    with ToolSandbox(image, work, task, substrate, inputs, memory='1536m', cpus=2, feedback=feedback) as box:
        boundary = box.inspect()
        execute.append(box.execute('python /work/submission/solve.py --inputs /work/inputs --output /work/submission', 120))
        assert execute[-1]['exit_code'] == 0, execute[-1]
        replies.append(box.score_development('results.zarr'))
        assert replies[-1]['exit_code'] == 0, replies[-1]
        development = json.loads(replies[-1]['stdout'])
        assert development['split'] == 'development'
        claim = development['rmse_mm']
        patch = "from pathlib import Path; import json; p=Path('/work/submission/variant.json'); p.write_text(json.dumps({'claims':{'development_rmse_mm':" + repr(claim) + "}}))"
        execute.append(box.execute("python -c " + __import__('shlex').quote(patch) + ' && python /work/submission/solve.py --inputs /work/inputs --output /work/submission', 120))
        assert execute[-1]['exit_code'] == 0, execute[-1]
        for name in ('results.zarr', '../escape.zarr', 'results.zarr', 'results.zarr', 'results.zarr'):
            replies.append(box.score_development(name))
        assert [reply['exit_code'] for reply in replies] == [0, 0, 1, 0, 0, 1]
        assert [reply['feedback_remaining'] for reply in replies] == [4, 3, 2, 1, 0, 0]
        assert 'limit reached' in replies[-1]['stderr']
        public = feedback.public_summary()
        assert len(scorer_calls) == 4 and len(public['requests']) == 5 and public['limit_denials'] == 1
        assert not public['final_score_exposed'] and not public['final_observations_exposed']
        assert all('final' not in json.loads(reply['stdout']).get('split', '') for reply in replies if reply['stdout'])
        assert 'private_error' not in json.dumps(public)
    feedback.finish()
    frozen = folder / 'frozen'
    shutil.copytree(work / 'submission', frozen)
    result = assess(template, params, frozen, Docker(image, memory='1536m', cpus=2), folder / 'assessment-scratch', level=2, feedback=public)
    (folder / 'assessment.json').write_text(json.dumps(result, indent=2) + '\n')
    assert result['computed_outcome'] == 'pass', result['checks']
    assert result['checks']['claim.development_rmse_mm']['state'] == 'pass'
    assert result['checks']['feedback.limit']['state'] == 'pass'
    assert template.fingerprint() == before and inventory(inputs) == input_before
    record = {'schema_version':1, 'verified_at':datetime.now(timezone.utc).isoformat(),
              'state':'pass', 'template':template.name, 'spec_version':template.spec['spec_version'],
              'fingerprint':before, 'instance':params, 'runtime_image':image,
              'certificate_sha256':digest(template.folder / 'certification.json'),
              'certificate_automatic_tests_passed':True, 'domain_scientist_certified':certificate['certified'],
              'interface':'ToolSandbox.score_development → DevelopmentFeedback.query → runner.development_scorer',
              'actor_solver_execution':'Docker only; two original actor executions, plus controller Docker validity replays',
              'actor_boundary':boundary, 'execute_results':execute, 'public_tool_replies':replies,
              'feedback_public_summary':public, 'scorer_invocations':scorer_calls,
              'development_score':development, 'original_measured_claim':claim,
              'assessment':{'path':str((folder / 'assessment.json').relative_to(ROOT)), 'sha256':digest(folder / 'assessment.json'),
                            'computed_outcome':result['computed_outcome'], 'outcome':result['outcome'],
                            'checks':{k:v['state'] for k,v in result['checks'].items()}, 'skill':result.get('skill')},
              'request_budget':{'allowed':5, 'reserved_requests':5, 'malformed_requests_counted':1,
                                'actual_score_computations':4, 'additional_denials':1,
                                'sixth_request_returned_score':False},
              'final_score_exposed_to_actor':False, 'final_observations_exposed_to_actor':False,
              'template_unchanged':True, 'model_artifacts_modified':False, 'model_calls':0, 'paid_api_calls':0,
              'evidence':{'folder':str(folder.relative_to(ROOT)), 'input_manifest':input_before,
                          'frozen_manifest':inventory(frozen), 'feedback_ledger_sha256':digest(folder / 'controller/development-feedback/ledger.json')},
              'blockers':[], 'caveats':['Public historical targets, not an untouched holdout.', 'Outcome task permits arbitrary valid methods; no prescribed statistical recipe.', 'No domain scientist certification.']}
    (ROOT / 'experiments/level2-preflight-2026-10-08.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'state':record['state'], 'fingerprint':before, 'development':development,
                      'skill':result.get('skill'), 'computed_outcome':result['computed_outcome'],
                      'budget':record['request_budget']}, indent=2))


if __name__ == '__main__':
    main()
