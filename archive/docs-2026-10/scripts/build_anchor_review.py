"""Four bounded review decisions, backed by the secondary anchor profiles."""
from pathlib import Path
import hashlib
import html
import json
import sys

import yaml

ROOT = Path(__file__).resolve().parents[3]            # the repository root; this folder is an archive
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import anchor_profile as study  # noqa: E402

DEST = ROOT / "var/review/anchors.html"
DATA = ROOT / "var/calibration/anchor-calibration-v1"


def esc(x):
    return html.escape(str(x), quote=True)


def link(path, label):
    path = Path(path)
    if path.is_absolute():
        path = path.relative_to(ROOT)
    return f'<a href="../../{esc(path)}">{esc(label)}</a>'


def pre(text):
    return '<pre>' + esc(text if isinstance(text, str) else json.dumps(text, indent=2)) + '</pre>'


def detail(label, body):
    return '<details><summary>' + esc(label) + '</summary>' + body + '</details>'


def table(headers, rows):
    return '<div class="table-wrap"><table><thead><tr>' + ''.join('<th>' + esc(x) + '</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + x + '</td>' for x in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def lines(path, start, stop):
    return '\n'.join(f'{i}: {line}' for i, line in enumerate(path.read_text().splitlines(), 1) if start <= i <= stop)


def record(case):
    return study.read(DATA / (case + '.json'))


def criterion(case, name):
    return next(x for x in record(case)['criteria'] if x['id'] == name)


def evidence(run, filename, start=None, stop=None):
    path = ROOT / 'var/runs' / run / 'frozen' / filename
    text = lines(path, start, stop) if start is not None else path.read_text()
    return '<p>' + link(path, filename + (f' · lines {start}–{stop}' if start is not None else '')) + '</p>' + pre(text)


def main():
    study.main()
    index = study.read(DATA / 'index.json')
    portfolio = yaml.safe_load((HERE / 'studies/anchor-calibration-v1/portfolio.yaml').read_text())
    # Retain existing operational controls without copying scientific arrays or
    # relabeling them as fresh agent attempts / unseen judge checks.
    controls = []
    path = ROOT / 'var/calibration/cca-seasonal-reproduction/docker-controls.json'
    for name, c in study.read(path)['records'].items():
        controls.append({'task': 'cca-seasonal-reproduction', 'case': name, 'kind': 'constructed_reference_control', 'source': str(path.relative_to(ROOT)), 'scientific_checks': c['scientific_checks'], 'stored_probes': {k: c[k] for k in ('replay', 'counterfactual', 'prediction')}, 'split': 'development_previously_inspected', 'human_label': None})
    path = ROOT / 'var/calibration/station-verification/static-control-results.json'
    station_controls = study.read(path)
    for name, c in station_controls['checks'].items():
        controls.append({'task': 'station-verification', 'case': name, 'kind': 'constructed_reference_control', 'source': str(path.relative_to(ROOT)), 'scientific_checks': c, 'split': 'development_previously_inspected', 'human_label': None})
    (DATA / 'controls.json').write_text(json.dumps({'scope': 'Stored development controls, not fresh solver attempts or human gold', 'records': controls, 'new_execution_probes': 0}, indent=2) + '\n')

    ids = [x['parent'] for x in index['lineage'].values()]
    luna_cca, astra_cca, station, luna_s2s, astra_s2s = ids
    down_run = '20261005T183344-conservative-downscaling-codex-luna-733b9d'
    down = study.read(ROOT / 'var/runs' / down_run / 'assessment.json')
    private_final = down['forecast_outcomes']
    helper = study.read(ROOT / 'var/calibration/judge-new-parent-review/comparison.json')
    source_review = next(x for x in helper['comparisons'] if x['case'] == 'c01' and x['criterion'] == 'verification_and_route_audit')
    packet = DATA / 'packets/a02-source_route_interpretation.json'
    src_packet = study.read(packet)
    assert all(f['available'] and f['complete'] for f in src_packet['files'].values())
    feedback_record = study.read(ROOT / record('a05')['original_execution_evidence'])['feedback']
    feedback_rows = [[esc(r['query']), esc(r['prediction_file']), f"{r['metrics']['rmse_mm']:.6f}"] for r in feedback_record['requests']]

    cards = [
        {
            'id': 'component-credit', 'title': 'Credit a correct component when the larger workflow fails',
            'observation': 'The Luna CCA attempt has correct fixed-mode outer predictions, but wrong nested selection and other outputs. The original broad fitting criterion gives it no credit. The proposed split retains the correct component as a distinct accomplishment.',
            'proposal': 'Award the fixed-mode component its 10 points. Keep the nested-selection and other failures visible. Missing delivery still prevents complete workflow success.',
            'question': 'Does this distinction represent useful scientific progress?',
            'evidence': table(['Requirement', 'Read-only check'], [['Fixed CCA prediction', '<strong>' + esc(criterion('a01', 'fixed_cca_predictions')['state']) + '</strong><br>' + esc(criterion('a01', 'fixed_cca_predictions')['detail'])], ['Nested mode selection', '<strong>' + esc(criterion('a01', 'nested_mode_selection')['state']) + '</strong><br>' + esc(criterion('a01', 'nested_mode_selection')['detail'])]]) + '<p>Original score bounds: 0–20. Secondary profile: 10–48, still incomplete and awaiting interpretation/execution evidence. These are two versions of the assessment scheme, not new model attempts.</p>' + link(DATA / 'a01.json', 'Full criterion profile') + ' · ' + link(ROOT / 'var/runs' / luna_cca / 'assessment.json', 'Original assessment'),
        },
        {
            'id': 'source-evidence', 'title': 'Judge the source explanation using the actual source passage',
            'observation': 'Two helper reviewers gave Astra partial credit for its CCA source-route audit because the relevant source files were omitted from their packets. The files were present in the submission. The new criterion packet contains the complete source passages, report and workflow.',
            'proposal': 'Treat packet omission as missing assessment evidence. With the complete passage visible, my proposed judgment is that this specific source-route explanation is supported; the formal expert label is still unset.',
            'question': 'Does the passage support the report’s distinction between full-fit probabilities and independent verification?',
            'evidence': evidence(astra_cca, 'inputs/pycpt-probabilistic-route.py.txt') + evidence(astra_cca, 'report.txt', 3, 5) + detail('Original helper-reviewer reasons', pre({'A': source_review['a'], 'B': source_review['b']})) + '<p>' + link(packet, 'Complete source-route packet') + '. All five requested source/code/report artifacts are complete; no file is budget-truncated.</p>',
        },
        {
            'id': 'adaptive-feedback', 'title': 'Allow the development feedback that the task explicitly offers',
            'observation': 'Astra made five subseasonal development queries and designed later candidate families after seeing earlier scores. Its fitted coefficients used training data. The task permits adaptive development feedback, while final scores and targets stay unavailable.',
            'proposal': 'Accept this research trajectory under the current contract. Require disclosure that the development result is selected, and assess train-only fitting separately. A fixed, feedback-blind research design would be a different condition.',
            'question': 'Is this the research freedom we want in the optimization track?',
            'evidence': table(['Query', 'Frozen queried prediction', 'Development RMSE mm'], feedback_rows) + evidence(astra_s2s, 'validate.py', 14, 17) + '<p>The validation code excludes training targets whose 14-day windows have not ended before the validation-year origin.</p>' + detail('Full disclosure and selection rule', evidence(astra_s2s, 'selection.json')) + link(ROOT / 'var/runs' / astra_s2s / 'controller/feedback-public.json', 'Trusted public feedback ledger') + '<p>No final feedback was exposed. Passing this controller boundary alone does not prove every fit or scientific claim is valid.</p>',
        },
        {
            'id': 'negative-results', 'title': 'Separate valid scientific construction from improved forecast skill',
            'observation': 'The retained downscaling example passes its prescribed mapping, conservation and execution checks, yet has final RMSE 141.63 mm versus climatology 105.87 mm. This is a supporting example outside the three anchors.',
            'proposal': 'Keep its known scientific credit and report the negative skill explicitly. Completion and interpretation still need their own evidence. In the optimization track, a sound negative experiment can complete the workflow while failing to achieve improvement.',
            'question': 'Should the benchmark make these two outcomes explicit?',
            'evidence': '<p>Original deterministic scientific credit: 75 points; full bounds 75–100 with expert requirements unresolved.</p>' + pre(private_final) + link(ROOT / 'var/runs' / down_run / 'assessment.json', 'Preserved assessment and forecast outcome') + '<p>A positive implementation judgment does not imply that this method should be recommended operationally.</p>',
        },
    ]

    sources = [study.PROFILE, HERE / 'studies/anchor-calibration-v1/portfolio.yaml', Path(__file__), HERE / 'scripts/anchor_profile.py', DATA / 'index.json', DATA / 'controls.json']
    sources += [DATA / (case + '.json') for case in index['lineage']]
    sources += [ROOT / p['path'] for p in index['expert_packets']]
    sources += [ROOT / 'var/runs' / rid / 'assessment.json' for rid in [*ids, down_run]]
    sources += [ROOT / 'var/calibration/judge-new-parent-review/comparison.json', ROOT / 'var/calibration/cca-seasonal-reproduction/docker-controls.json', ROOT / 'var/calibration/station-verification/static-control-results.json']
    source_hashes = {str(p.relative_to(ROOT)): study.sha(p) for p in sources}
    bundle = hashlib.sha256(json.dumps(source_hashes, sort_keys=True).encode()).hexdigest()
    body = ''
    for number, card in enumerate(cards, 1):
        name = card['id']
        body += f'<section class="card" data-decision="{name}" id="{name}"><p class="eyebrow">Decision {number} of 4</p><h2>{esc(card["title"])}</h2><p>{esc(card["observation"])}</p><p class="proposal"><strong>My recommendation:</strong> {esc(card["proposal"])}</p>'
        body += detail('Inspect the relevant evidence', card['evidence'])
        body += f'<fieldset><legend>{esc(card["question"])}</legend>'
        for value, label in [('agree', 'Agree with the recommendation'), ('change', 'I would change this'), ('unsure', 'Unsure / needs more evidence')]:
            body += f'<label><input type="radio" name="{name}" value="{value}"> {label}</label>'
        body += f'</fieldset><label class="notes" for="{name}-notes">Notes (optional)</label><textarea id="{name}-notes" rows="2"></textarea></section>'
    profiles = []
    for row in index['records']:
        r = study.read(ROOT / row['path'])
        facts = table(['Requirement', 'Dimension', 'Points', 'State'], [[esc(c['id']), esc(c['dimension']), esc(c['weight']), esc(c['state'])] for c in r['criteria']])
        profiles.append(detail(row['case'] + ' · ' + row['task'] + ' · profile ' + '–'.join(map(str, row['profile_bounds'])), facts + '<p>' + link(ROOT / row['path'], 'Checks, provenance and original-score linkage') + '</p>'))
    packet_rows = [[esc(p['case']), esc(p['criterion']), esc(', '.join(p['omitted_artifacts']) or 'All requested artifacts complete'), link(ROOT / p['path'], 'Packet')] for p in index['expert_packets']]
    controls_rows = []
    for c in controls:
        states = ', '.join(f'{k}: {v["state"]}' for k, v in c['scientific_checks'].items())
        probes = ', '.join(f'{k}: {v.get("state", "unresolved")}' for k, v in c.get('stored_probes', {}).items())
        controls_rows.append([esc(c['task'] + ' / ' + c['case']), esc(states), esc(probes or 'Static control; full runtime record not included here')])

    page = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Weather Bench · Four review decisions</title><style>
:root{--ink:#213c43;--green:#236c61;--line:#d7ddd8;--paper:#f6f5ef}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.65 system-ui,-apple-system,sans-serif}main{max-width:870px;margin:auto;padding:26px 24px 60px}a{color:var(--green);overflow-wrap:anywhere}h1{font:400 42px/1.18 Georgia,serif}h2{font-size:22px;line-height:1.35;margin:6px 0 18px}.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.7px;color:var(--green)}.muted{font-size:13px;color:#526a70}.card{border:1px solid var(--line);border-radius:7px;background:#fffefa;padding:23px;margin:22px 0}.proposal{background:#eaf0e9;border-left:3px solid var(--green);padding:12px 16px}.toolbar{position:sticky;top:0;z-index:5;background:var(--ink);color:white;padding:12px 16px;border-radius:5px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}.toolbar span{margin-right:auto;font-size:13px}button{cursor:pointer;border:1px solid var(--line);border-radius:4px;background:#fffefa;color:var(--ink);font:inherit;font-size:13px;padding:7px 10px}a:focus-visible,button:focus-visible,summary:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid #c38622;outline-offset:3px}fieldset{border:0;padding:0;margin:18px 0 12px;min-width:0}legend{font-weight:600;margin-bottom:8px}fieldset label{display:block;border:1px solid var(--line);border-radius:4px;padding:8px 11px;margin:7px 0;font-size:14px;cursor:pointer}input{accent-color:var(--green)}label:has(input:checked){background:#eaf0e9;border-color:var(--green)}.notes{font-size:13px}textarea{width:100%;resize:vertical;padding:9px 12px;font:inherit;border:1px solid #bdcec3;border-radius:4px}details{border-top:1px solid var(--line);padding:12px 0;margin-top:16px}summary{font-size:14px;cursor:pointer;color:var(--green);font-weight:600}pre{font:12px/1.6 ui-monospace,Menlo,monospace;white-space:pre-wrap;overflow-wrap:anywhere;background:#eff2ec;border:1px solid var(--line);padding:12px;max-height:400px;overflow:auto}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;vertical-align:top;border-bottom:1px solid var(--line);padding:9px 10px}td{overflow-wrap:anywhere}.notice{font-size:13px;margin:12px 0;min-height:20px}.anchor-list li{margin:8px 0}footer{border-top:1px solid var(--line);margin-top:30px;padding-top:18px;font-size:12px;color:#526a70}@media(max-width:600px){main{padding:18px 14px 45px}h1{font-size:32px}.card{padding:18px 14px}h2{font-size:20px}}@media print{.toolbar{display:none}body{background:white}.card{break-inside:avoid}pre{max-height:none}}
</style></head><body><main><p class="eyebrow">Agent Weather Bench · Anchor calibration</p><h1>Four decisions,<br>with just the evidence they need.</h1><p>The next cycle focuses on <strong>CCA reconstruction, station verification and subseasonal optimization</strong>. The other seven examples remain supporting tests. These four decisions are your review; the detailed records below are optional.</p><p class="muted">Five existing solver parents; no new model calls, downloads or Docker runs. All cases have already been inspected during development. Human reference labels and a fresh check set remain outstanding.</p><div class="toolbar"><span id="progress">0 of 4 decisions annotated</span><button type="button" id="export">Export notes</button><button type="button" id="import">Import notes</button><button type="button" id="print">Print</button><input id="import-file" type="file" accept="application/json" hidden></div><p id="notice" class="notice" role="status"></p><form id="review">@@CARDS@@</form>
<details><summary>What has been implemented behind this review</summary><ul><li>A versioned profile separates scientific requirements, interpretation, delivery and measured forecast performance. Each original parent criterion keeps its total weight.</li><li>The profile rechecks fixed/nested CCA and station truth/interpolation against existing independent references. Original replay agreement is distinct from scientific correctness and changed-input probes.</li><li>Eighteen local criterion-specific expert packets include complete source/code/report files where available, with explicit missing-file records. No judge has been called on these packets.</li><li>The original task versions, rubric files, evaluator lock, solver artifacts and benchmark scores are unchanged. Secondary profile ranges are development comparisons, not official grades.</li></ul>@@PROFILES@@</details>
<details><summary>Criterion-specific evidence packets</summary>@@PACKETS@@<p class="muted">Missing files stay unknown; they are not treated as zero-credit scientific judgments. No gold labels are inferred from helper agreement.</p></details>
<details><summary>Existing numerical and execution controls</summary>@@CONTROLS@@<p class="muted">These constructed controls are previously inspected development evidence, not new natural attempts or a held-out judge test. Original controller records remain intact.</p></details>
<details><summary>Portfolio boundaries and the next stronger task</summary><p>Ten examples occupy six workflow families, with substantial shared rainfall/SST and calibration work. The station anchor supports verification but uses short-range forecasts. Autonomous retrieval, daily extremes/onset, other S2S variables and sequential operational updates remain coverage gaps.</p><p>Before another frontier run, independently reproduce a stronger source-backed subseasonal baseline on the existing nine-cell inputs and measure its cost and skill. The data do not support every published ABC feature; any restricted adaptation must be named honestly. Downloads remain paused.</p>@@PORTFOLIO@@</details>
<footer><p>Ratings and notes save locally when browser storage is available. Export saves development feedback; it does not rewrite task grades. You can rate any subset, leave notes blank or choose “unsure.”</p><p>@@LINKS@@</p></footer></main><script>
const bundle=@@BUNDLE@@, storageKey='awb-anchor-review:'+bundle;
const form=document.getElementById('review'), notice=document.getElementById('notice');
const names=[...form.querySelectorAll('[data-decision]')].map(e=>e.dataset.decision);
let storageAvailable=true;
function collect(){const fields={};for(const name of names){fields[name]=form.querySelector('input[name="'+name+'"]:checked')?.value||'';fields[name+'-notes']=document.getElementById(name+'-notes').value;}return {schema_version:1,kind:'human_development_feedback',review_bundle_sha256:bundle,fields};}
function progress(){const fields=collect().fields;const n=names.filter(name=>fields[name]||fields[name+'-notes'].trim()).length;document.getElementById('progress').textContent=n+' of 4 decisions annotated';}
function restore(data){if(data.schema_version!==1||data.review_bundle_sha256!==bundle||!data.fields||typeof data.fields!=='object')throw Error('This file belongs to a different review. Your current notes were kept.');for(const name of names){const choice=data.fields[name]||'';if(!['','agree','change','unsure'].includes(choice)||typeof(data.fields[name+'-notes']||'')!=='string')throw Error('Invalid review fields. Your current notes were kept.');}for(const name of names){for(const input of form.querySelectorAll('input[name="'+name+'"]'))input.checked=input.value===data.fields[name];document.getElementById(name+'-notes').value=data.fields[name+'-notes']||'';}progress();}
function save(){try{localStorage.setItem(storageKey,JSON.stringify(collect()));}catch(e){storageAvailable=false;notice.textContent='Browser storage is unavailable. Use Export notes to keep your feedback.';}progress();}
try{const saved=localStorage.getItem(storageKey);if(saved)restore(JSON.parse(saved));}catch(e){storageAvailable=false;notice.textContent='Saved notes could not be restored. You can still rate and export below.';}
form.addEventListener('submit',e=>e.preventDefault());form.addEventListener('input',save);form.addEventListener('change',save);
document.getElementById('export').onclick=()=>{save();const blob=new Blob([JSON.stringify(collect(),null,2)+'\n'],{type:'application/json'}),url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='weather-bench-four-decisions.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notice.textContent='Exported your development feedback.';};
document.getElementById('import').onclick=()=>document.getElementById('import-file').click();
document.getElementById('import-file').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;restore(JSON.parse(await file.text()));save();notice.textContent='Imported your notes.';}catch(error){notice.textContent=error.message;}finally{e.target.value='';}};
document.getElementById('print').onclick=()=>window.print();
</script></body></html>'''
    links = link(study.PROFILE, 'Versioned profile') + ' · ' + link(HERE / 'studies/anchor-calibration-v1/portfolio.yaml', 'Portfolio map') + ' · <a href="task-runs.html">Full experiment archive</a> · <a href="anchors.sources.json">Source hashes</a>'
    page = page.replace('@@CARDS@@', body).replace('@@PROFILES@@', ''.join(profiles)).replace('@@PACKETS@@', table(['Case', 'Criterion', 'Coverage', 'Evidence'], packet_rows)).replace('@@CONTROLS@@', table(['Control', 'Scientific checks', 'Recorded probes'], controls_rows)).replace('@@PORTFOLIO@@', link(HERE / 'studies/anchor-calibration-v1/portfolio.yaml', 'Portfolio and flagship readiness rules')).replace('@@LINKS@@', links).replace('@@BUNDLE@@', json.dumps(bundle))
    DEST.write_text(page)
    manifest = {'schema_version': 1, 'bundle_sha256': bundle, 'html_sha256': study.sha(DEST), 'sources_sha256': source_hashes, 'decisions': [c['id'] for c in cards], 'natural_parents': 5, 'expert_packets': len(index['expert_packets']), 'stored_controls': len(controls), 'new_model_calls': 0, 'new_docker_probes': 0, 'human_labels': None, 'fresh_check_parents': 0}
    DEST.with_suffix('.sources.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'html': str(DEST), 'bytes': DEST.stat().st_size, 'decisions': 4, 'expert_packets': len(index['expert_packets']), 'controls': len(controls), 'new_model_calls': 0}))


if __name__ == '__main__':
    main()
