"""Bounded, neutral historical code-review calibration; never execute submissions.

Preparation is offline. Model requests require an explicit --judge invocation,
are counted durably before dispatch, and never load the private expected labels.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment import judge

DESTINATION = ROOT / 'var/review/failure-judge-calibration-20261008'
PRIVATE = ROOT / 'var/private/calibration/failure-judge-calibration-20261008'
AUDIT = ROOT / 'experiments/original-portfolio-failure-audit-2026-10-08.json'
MAX_REQUESTS = 8
MAX_PACKET_CHARACTERS = 90000
RUNS = {
    'monthly': '20261005T183342-monthly-cycle-calibration-codex-luna-e7f6e0',
    'station': '20261005T181603-station-verification-codex-luna-ff16df',
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,prefix='.'+path.name+'-',delete=False) as handle:
        handle.write(json.dumps(value, indent=2, allow_nan=False) + '\n')
        temporary=Path(handle.name)
    temporary.replace(path)


def correction(domain, code):
    """Only the implicated scientific expression changes; no runtime repairs."""
    if domain == 'monthly':
        old = 'preds[2]=predict(x[idx],pars,1)'
        new = 'preds[2]=pars[2][None,:,:]+pars[3][None,:,:]*pars[4].mean(0)[None,None,:]*(x[idx]-pars[0][None,:])[:,:,None]/pars[1][None,:,None]'
    elif domain == 'station':
        old, new = 'if v==2: truth=truth-273.15', 'if v in (2,4): truth=truth-273.15'
    else:
        raise ValueError('Unknown calibration domain')
    if code.count(old) != 1:
        raise ValueError('Historical source expression changed; refuse approximate repair')
    return code.replace(old, new), {'before': old, 'after': new, 'replacement_count': 1}


def questions(domain):
    if domain == 'monthly':
        requirements = {
            'production_method': 'Review only the constant-slope production prediction expression and its fitted parameters. '
                'Does it implement the constant comparator and physical prediction formula defined in task/algorithm.md? '
                'Trace the calculation independently from the retained code. Distinguish this method question from '
                'runtime execution, unit metadata and the correctness of other systems.',
            'validation_method': 'Review only the nested whole-year validation method for hindcasts. '
                'Does the retained code recompute all means/scales/slopes using earlier training years within '
                'each complete-year inner fold, select one global candidate using the declared normalized loss, '
                'and produce the nested-cyclic outer prediction from the appropriate outer fit? '
                'Do not propagate an unrelated production or delivery defect into this answer.',
        }
    elif domain == 'station':
        requirements = {
            'diagnostic_method': 'Review the diagnostic variants required by task/brief.md. '
                'Does the retained workflow implement each isolated variant and the combined variant with the '
                'specified truth values, time matching, individual/common masks and pooled observation-sample RMSE? '
                'Trace which transformations execute in each variant; assess code method separately from delivery.',
            'headline_method': 'Review only the headline station verification calculation. '
                'Does the workflow implement the specified valid-time/QC/duplicate matching, Kelvin conversion, '
                'interpolation, common finite availability support, pooled RMSE and empty-station treatment? '
                'Do not propagate a diagnostic-variant or packaging error into the headline method verdict.',
        }
    else:
        raise ValueError('Unknown calibration domain')
    return {key: {'kind': 'method_statement', 'silence': 'not applicable', 'requirement': value}
            for key, value in requirements.items()}


def numeric_rows(diagnostic):
    """Independent metadata and value evidence; never short-circuit on units."""
    rows = []
    for filename, entry in sorted(diagnostic['static']['array_diagnostics']['files'].items()):
        for name, field in sorted(entry.get('fields', {}).items()):
            rows.append({'file': filename, 'variable': name,
                         'dimensions_agree': field.get('dimensions_agree'),
                         'shape_agrees': field.get('shape_agrees'),
                         'units': deepcopy(field.get('units')),
                         'numeric': deepcopy(field.get('numeric'))})
    if not rows:
        raise ValueError('Independent numeric diagnostics are missing')
    return rows


def make_packet(domain, source, corrected=False):
    """Judge input has neutral file names and contains no expected labels."""
    run = ROOT / 'var/runs' / RUNS[domain]
    code = (run / 'frozen/workflow.py').read_text()
    repair = None
    if corrected:
        code, repair = correction(domain, code)
    files = {'task/brief.md': (run / 'task/prompt.md').read_text(), 'workflow.py': code}
    if domain == 'monthly':
        files['task/algorithm.md'] = (run / 'inputs/algorithm.md').read_text()
    if corrected:
        # Original outputs/reports cannot truthfully describe an unexecuted repair.
        files['controller/scope.txt'] = (
            'Constructed source-only control: the workflow is a modified copy of a historical submission. '
            'No arrays have been regenerated and no report or original numeric diagnostics are supplied for '
            'this copy. Answer only the narrow code-method questions. Runtime validity, delivery and numerical '
            'output agreement are outside this packet and have not been established.\n')
    else:
        diagnostic = json.loads((ROOT / 'var/calibration/overnight-static-diagnostics' /
                                 (RUNS[domain] + '.json')).read_text())
        files['report.txt'] = (run / 'frozen/report.txt').read_text()
        files['answer.json'] = (run / 'frozen/answer.json').read_text()
        files['controller/array-diagnostics.json'] = json.dumps({
            'scope': 'Stored independent comparison of the historical submitted arrays; no new execution. '
                     'Metadata and numeric differences are separate measurements. '
                     'A whole-field difference does not identify which system/variant caused it.',
            'rows': numeric_rows(diagnostic)}, indent=2)
        files['controller/scope.txt'] = (
            'Historical submission, unchanged. The full retained scientific workflow and report are shown. '
            'Stored independent array diagnostics are supplementary evidence, not a source-code explanation. '
            'Decide each narrow method question independently; do not infer global completion from it.\n')
    packet = {'schema_version': 1, 'questions': questions(domain), 'files': files}
    size = sum(len(text) for text in files.values())
    if size > MAX_PACKET_CHARACTERS or any(len(text) > judge.FILE_LIMIT for text in files.values()):
        raise ValueError('Packet exceeds the predeclared complete-code bound')
    return packet, repair


def prepare(destination=DESTINATION, private=PRIVATE):
    destination, private = Path(destination), Path(private)
    if (destination/'requests.json').exists():
        raise ValueError('Requests already dispatched; prepared study inputs are immutable')
    audit = json.loads(AUDIT.read_text())
    originals = {relative: expected for row in audit['runs'].values() for relative, expected in row['sources'].items()}
    for relative, expected in originals.items():
        if digest(ROOT / relative) != expected:
            raise ValueError('Historical evidence changed: ' + relative)
    frozen_count = 0
    for run_id in RUNS.values():
        run = ROOT / 'var/runs' / run_id
        for relative, entry in json.loads((run / 'artifacts.json').read_text()).items():
            path = run / 'frozen' / relative
            if path.is_symlink() or digest(path) != entry['sha256'] or path.stat().st_size != entry['bytes']:
                raise ValueError('Historical frozen artifact changed: ' + str(path))
            frozen_count += 1
    manifest, expected = [], {}
    # Deliberately interleave domains and original/control identities.
    assignments = [('sample-a', 'monthly', False), ('sample-b', 'station', True),
                   ('sample-c', 'station', False), ('sample-d', 'monthly', True)]
    for name, domain, corrected in assignments:
        packet, repair = make_packet(domain, audit['runs'][domain], corrected)
        path = destination / 'packets' / name / 'packet.json'
        if path.exists() and json.loads(path.read_text()) != packet:
            raise ValueError('Refusing to overwrite an existing different calibration packet')
        write(path, packet)
        rendered = path.with_name('input.txt')
        rendered.write_text(judge.render(packet['questions'], packet['files']))
        manifest.append({'sample': name, 'packet': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                         'packet_sha256': digest(path), 'characters': sum(map(len, packet['files'].values())),
                         'files': {key: hashlib.sha256(text.encode()).hexdigest() for key, text in packet['files'].items()}})
        expected[name] = {'domain': domain, 'source_run': RUNS[domain], 'constructed': corrected,
                          'scope': 'source-method-only; no complete-submission positive control' if corrected else 'historical original',
                          'expected': {key: 'pass' if corrected or key in ('validation_method', 'headline_method') else 'fail'
                                       for key in packet['questions']}, 'surgical_change': repair}
    write(private / 'expected.json', expected)
    archival = {domain: {'judge': json.loads((ROOT / 'var/runs' / run / 'assessment.json').read_text()).get('judge'),
                        'interpretation': 'No original model judge ran: only a judge packet was stored. '
                        'There is no observed original judge catch/miss rate. Deterministic checks found the '
                        'station diagnostic discrepancy and monthly missing units; a separate independent '
                        'numeric overlay reveals the production value error hidden by the first-failure units check.'}
                for domain, run in RUNS.items()}
    record = {'schema_version': 1, 'status': 'prepared', 'new_model_calls': 0,
              'packets': manifest, 'max_requests': MAX_REQUESTS, 'per_request_cli_budget_usd': 2,
              'max_cli_budget_usd': 16, 'paid_actual_usd': None,
              'judge_identity': {'model': judge.MODEL, 'effort': judge.EFFORT, 'id': judge.judge_id()},
              'archival_judge': archival, 'original_hashes_verified': originals,
              'original_frozen_files_verified': frozen_count,
              'expected_labels_path': str(private / 'expected.json'),
              'limitations': ['Method questions are deliberately targeted, not a blind general bug-discovery test.',
                             'Constructed repaired controls are code-only and cannot establish numerical/runtime validity.',
                             'No original outputs, reports, assessments, source files or certifications are edited.']}
    write(destination / 'manifest.json', record)
    return record


def run_judges(destination=DESTINATION, max_new_requests=4):
    """Exclusive single study launcher; text-only judge calls may overlap."""
    destination = Path(destination)
    if type(max_new_requests) is not int or not 1 <= max_new_requests <= 4:
        raise ValueError('At most the four declared initial packets per invocation')
    lock = destination / 'requests.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.write(fd, str(os.getpid()).encode())
        return _run_judges(destination, max_new_requests)
    finally:
        os.close(fd)
        lock.unlink()


def _run_judges(destination, max_new_requests):
    """No auto retry: every dispatch is reserved first, with an absolute study cap."""
    destination = Path(destination)
    manifest = json.loads((destination / 'manifest.json').read_text())
    ledger_path = destination / 'requests.json'
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else []
    selected = []
    for item in manifest['packets']:
        if any(row['sample'] == item['sample'] for row in ledger):
            continue
        if len(selected) >= max_new_requests:
            break
        if len(ledger) >= MAX_REQUESTS:
            raise ValueError('Absolute judge request cap reached')
        path = Path(item['packet'])
        path = path if path.is_absolute() else ROOT / path
        if digest(path) != item['packet_sha256']:
            raise ValueError('Prepared judge packet changed')
        packet = json.loads(path.read_text())
        row = {'request': len(ledger)+1, 'sample': item['sample'], 'status': 'reserved',
               'created_at': datetime.now(timezone.utc).isoformat(), 'packet_sha256': digest(path)}
        ledger.append(row)
        write(ledger_path, ledger)
        selected.append((item, packet, row))

    def dispatch(payload):
        item, packet, row = payload
        row = dict(row)
        try:
            raw, request = judge.claude_cli(packet['questions'], packet['files'])
            raw_path = destination / 'responses' / (item['sample'] + '.json')
            write(raw_path, {'verdicts': raw, 'request': request})
            by_id = {value.get('id'): value for value in raw if isinstance(value, dict)}
            validated = {key: judge.validate_verdict(by_id.get(key), packet['files'], question)
                         for key, question in packet['questions'].items()}
            row.update(status='completed', response_sha256=digest(raw_path), validated=validated,
                       usage=request.get('usage'), backend_record=request,
                       requested_model=judge.MODEL, effective_model=request.get('model'),
                       actual_billed_usd=None, cost_scope='CLI list-price accounting is not proof of a paid API charge')
        except judge.JudgeUnavailable as error:
            row.update(status='unavailable', error=str(error))
        return row

    # These threads orchestrate JSON-only CLI requests; no scientific imports or I/O.
    with ThreadPoolExecutor(max_workers=2) as pool:
        for completed in pool.map(dispatch, selected):
            next(row for row in ledger if row['request']==completed['request']).update(completed)
            write(ledger_path, ledger)
    return ledger


def prepare_general(destination=DESTINATION, private=PRIVATE):
    """Separate uncued original-only requests; never change targeted packet bytes."""
    destination, private = Path(destination), Path(private)
    manifest_path = destination / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    expected_path = private / 'expected.json'
    expected = json.loads(expected_path.read_text())
    for name, domain in [('sample-e','monthly'),('sample-f','station')]:
        run = ROOT / 'var/runs' / RUNS[domain]
        files = {'task/brief.md': (run/'task/prompt.md').read_text(),
                 'workflow.py': (run/'frozen/workflow.py').read_text(),
                 'report.txt': (run/'frozen/report.txt').read_text(),
                 'answer.json': (run/'frozen/answer.json').read_text()}
        if domain=='monthly':
            files['task/algorithm.md']=(run/'inputs/algorithm.md').read_text()
        q = {
            'consistency_across_artifacts': judge.interpretation_question('consistency_across_artifacts'),
            'method_conformance': {'kind':'method_statement','silence':'not applicable',
                 'requirement':'Does the retained scientific workflow implement the computational procedure '
                               'required by the supplied task documents? Review its source independently and '
                               'identify any supported scientific or execution inconsistency. Assess this '
                               'separately from file-format, provenance, or delivery defects.'},
        }
        packet={'schema_version':1,'questions':q,'files':files}
        path=destination/'packets'/name/'packet.json'
        if path.exists() and json.loads(path.read_text())!=packet:
            raise ValueError('Refusing to change an existing general-review packet')
        write(path,packet)
        path.with_name('input.txt').write_text(judge.render(q,files))
        if not any(row['sample']==name for row in manifest['packets']):
            manifest['packets'].append({'sample':name,'calibration_mode':'general_original_without_diagnostics',
                'packet':str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                'packet_sha256':digest(path),'characters':sum(map(len,files.values())),
                'files':{key:hashlib.sha256(text.encode()).hexdigest() for key,text in files.items()}})
        expected[name]={'domain':domain,'source_run':RUNS[domain],'constructed':False,
                        'scope':'separately dispatched general original review; no targeted question or numeric diagnostic',
                        'expected':{'method_conformance':'fail'},
                        'consistency_note':'Assess cited rationale manually; a general failure for some other issue '
                                           'does not establish discovery of the targeted scientific error.'}
    write(expected_path,expected)
    write(manifest_path,manifest)
    return manifest


def prepare_ablation(destination=DESTINATION, private=PRIVATE):
    """Copy targeted originals, removing exactly the numeric-diagnostic file."""
    destination,private=Path(destination),Path(private)
    manifest_path=destination/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    ledger=json.loads((destination/'requests.json').read_text())
    if len(ledger)!=6 or any(row['status']!='completed' for row in ledger):
        raise ValueError('Freeze the completed six-call baseline before ablation')
    expected_path=private/'expected.json'
    expected=json.loads(expected_path.read_text())
    for name,original in [('sample-g','sample-a'),('sample-h','sample-c')]:
        source=next(row for row in manifest['packets'] if row['sample']==original)
        sourcepath=Path(source['packet'])
        sourcepath=sourcepath if sourcepath.is_absolute() else ROOT/sourcepath
        if digest(sourcepath)!=source['packet_sha256']:
            raise ValueError('Original targeted packet changed')
        packet=json.loads(sourcepath.read_text())
        del packet['files']['controller/array-diagnostics.json']
        path=destination/'packets'/name/'packet.json'
        if path.exists() and json.loads(path.read_text())!=packet:
            raise ValueError('Refusing to alter an existing ablation packet')
        write(path,packet)
        path.with_name('input.txt').write_text(judge.render(packet['questions'],packet['files']))
        if not any(row['sample']==name for row in manifest['packets']):
            manifest['packets'].append({'sample':name,'calibration_mode':'targeted_original_without_numeric_diagnostics',
                'ablation_of':original,'removed_files':['controller/array-diagnostics.json'],
                'packet':str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                'packet_sha256':digest(path),'characters':sum(map(len,packet['files'].values())),
                'files':{key:hashlib.sha256(text.encode()).hexdigest() for key,text in packet['files'].items()}})
        expected[name]=deepcopy(expected[original])
        expected[name]['scope']='Same targeted original packet with only numeric diagnostic file removed'
        expected[name]['ablation_of']=original
    write(expected_path,expected)
    write(manifest_path,manifest)
    return manifest


def summarize(destination=DESTINATION, private=PRIVATE, output=None, expected_requests=6):
    """Post-call analysis reads private labels only after inference is complete."""
    destination, private = Path(destination), Path(private)
    ledger=json.loads((destination/'requests.json').read_text())
    if expected_requests not in (6,8) or len(ledger)!=expected_requests or any(row['status']!='completed' for row in ledger):
        raise ValueError('All declared requests must complete before final analysis')
    expected=json.loads((private/'expected.json').read_text())
    targeted=[]
    for row in ledger[:4]:
        for name,label in expected[row['sample']]['expected'].items():
            actual=row['validated'][name]['state']
            targeted.append({'sample':row['sample'],'question':name,'expected':label,'actual':actual,
                             'matches':actual==label})
    sources=[Path(__file__),ROOT/'tests/test_failure_judge_calibration.py',
             destination/'manifest.json',destination/'requests.json',private/'expected.json',
             ROOT/'experiments/historical-science-slices-2026-10-08.json',AUDIT]
    sources += sorted((destination/'responses').glob('*.json'))
    result={'schema_version':1,'status':'completed','new_judge_requests':len(ledger),
        'request_cap':MAX_REQUESTS,'retries':0,'model':judge.MODEL,'effort':judge.EFFORT,
        'requested_effective_models':[{key:row.get(key) for key in ('sample','requested_model','effective_model')}
                                       for row in ledger],
        'usage':{'input_tokens':sum(row['usage'].get('input_tokens',0) for row in ledger),
                 'output_tokens':sum(row['usage'].get('output_tokens',0) for row in ledger),
                 'cli_list_price_usd':sum(row['usage'].get('list_price_usd',0) for row in ledger),
                 'actual_billed_usd':None,
                 'auth':'Root-relayed readiness: Claude CLI logged in through claude.ai Max subscription.',
                 'cost_scope':'Reported CLI list price is not proof of a paid API charge; actual subscription attribution unknown.'},
        'targeted':{'rows':targeted,'matching_verdicts':sum(row['matches'] for row in targeted),'total_verdicts':len(targeted),
                    'faults_detected':sum(row['expected']=='fail' and row['actual']=='fail' for row in targeted),
                    'faults_tested':sum(row['expected']=='fail' for row in targeted),
                    'method_passes_preserved':sum(row['expected']=='pass' and row['actual']=='pass' for row in targeted),
                    'method_passes_tested':sum(row['expected']=='pass' for row in targeted),
                    'scope':'Targeted code-method questions; source-only repairs do not establish full runtime/numeric validity.'},
        'general_without_diagnostics':{
            'monthly':{'sample':'sample-e','standing_consistency':ledger[4]['validated']['consistency_across_artifacts']['state'],
                       'generic_conformance':ledger[4]['validated']['method_conformance']['state'],
                       'target_scientific_fault_identified':True,
                       'manual_rationale_review':'Explicitly identifies production betas[1] versus mean(raw_beta), and separately ds initialization.'},
            'station':{'sample':'sample-f','standing_consistency':ledger[5]['validated']['consistency_across_artifacts']['state'],
                       'generic_conformance':ledger[5]['validated']['method_conformance']['state'],
                       'target_scientific_fault_identified':False,
                       'manual_rationale_review':'Incorrectly asserts diagnostic variants are implemented, without noticing v==2 excludes v==4.'},
            'comparison':'Generic method conformance finds one of two known scientific faults. Standing consistency '
                         'flags neither; consistency is a different obligation and can pass when artifacts agree on a wrong calculation.'},
        'all_citations_valid':all(value.get('reason')!='invalid_citation' for row in ledger for value in row['validated'].values()),
        'independent_numeric_localization':json.loads((ROOT/'experiments/historical-science-slices-2026-10-08.json').read_text()),
        'archival_judge':'Both original assessments recorded judge=none. This study is new calibration, not evidence of an original judge miss.',
        'interpretation':'Narrow, task-owned method questions can expose these errors while preserving component successes. '
                         'A broad consistency or conformance judge is not a substitute for deterministic numeric comparisons.',
        'limits':['Two selected historical failures and one judgment per packet; no sensitivity/specificity estimate for a population.',
                  'Targeted and general modes differ in both question specificity and access to numeric diagnostics; their effects are confounded.',
                  'The constructed repaired controls change only one expression; remaining runtime/provenance defects are intentionally not repaired.',
                  'No submission code was executed for this calibration; original artifacts and assessments remain unchanged.'],
        'evidence':{str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path):digest(path) for path in sources}}
    if expected_requests==8:
        result['targeted_without_numeric_diagnostics']={}
        for original,new,domain in [('sample-a','sample-g','monthly'),('sample-c','sample-h','station')]:
            before=next(row for row in ledger if row['sample']==original)
            after=next(row for row in ledger if row['sample']==new)
            result['targeted_without_numeric_diagnostics'][domain]={
                'original_sample':original,'ablation_sample':new,
                'with_numeric_diagnostics':{key:row['state'] for key,row in before['validated'].items()},
                'without_numeric_diagnostics':{key:row['state'] for key,row in after['validated'].items()},
                'same_question_verdicts':{key:row['state'] for key,row in before['validated'].items()}==
                                       {key:row['state'] for key,row in after['validated'].items()},
                'verdicts':after['validated']}
        result['six_call_baseline']={'path':'experiments/failure-judge-calibration-2026-10-08.json',
            'sha256':digest(ROOT/'experiments/failure-judge-calibration-2026-10-08.json'),
            'snapshot':'experiments/failure-judge-calibration-six-call-snapshot-2026-10-08.json',
            'snapshot_sha256':digest(ROOT/'experiments/failure-judge-calibration-six-call-snapshot-2026-10-08.json')}
        result['ablation_inference']={
            'both_faults_still_detected':all(row['same_question_verdicts'] for row in result['targeted_without_numeric_diagnostics'].values()),
            'scope':'The separate controller numeric-diagnostic file was unnecessary for these two targeted '
                    'detections in this trial. Task documents, full code, reports and answer JSON remained '
                    'identical; reports still contain numerical values. This is not an evidence-free or '
                    'blind-discovery test and does not establish a population effect.'}
        result['limits'][1]=('One targeted ablation per original removes only numeric diagnostics. '
                           'This isolates the supplied numeric file within these two targeted reviews, '
                           'but does not isolate specificity from every other aspect of general-review context.')
        result['interpretation']=('Read the targeted numeric-removal ablation separately from the general-review comparison. '
            'Task-owned code-method questions preserve component successes; a broad judge remains fallible '
            'and is not a substitute for deterministic numeric comparisons.')
        output=output or ROOT/'experiments/failure-judge-calibration-eight-call-2026-10-08.json'
    write(output or ROOT/'experiments/failure-judge-calibration-2026-10-08.json',result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--judge', action='store_true')
    parser.add_argument('--prepare-general', action='store_true')
    parser.add_argument('--summarize',action='store_true')
    parser.add_argument('--prepare-ablation',action='store_true')
    parser.add_argument('--summarize-eight',action='store_true')
    parser.add_argument('--max-new-requests', type=int, default=4)
    args = parser.parse_args()
    if args.prepare:
        result = prepare()
        print(json.dumps({'status': result['status'], 'packets': len(result['packets']), 'model_calls': 0}))
    if args.judge:
        result = run_judges(max_new_requests=args.max_new_requests)
        print(json.dumps({'requests': len(result), 'status': [row['status'] for row in result]}))
    if args.prepare_general:
        result=prepare_general()
        print(json.dumps({'status':'general_prepared','packets':len(result['packets']),'model_calls':0}))
    if args.summarize:
        result=summarize()
        print(json.dumps({'status':result['status'],'requests':result['new_judge_requests'],
                          'targeted_matches':result['targeted']['matching_verdicts'],
                          'general':result['general_without_diagnostics'],'usage':result['usage']},indent=2))
    if args.prepare_ablation:
        result=prepare_ablation()
        print(json.dumps({'status':'ablation_prepared','packets':len(result['packets']),'model_calls':0}))
    if args.summarize_eight:
        result=summarize(expected_requests=8)
        print(json.dumps({'requests':result['new_judge_requests'],'ablation':result['targeted_without_numeric_diagnostics'],
                          'usage':result['usage']},indent=2))
