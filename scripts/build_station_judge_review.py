"""A short result summary and a separate, initially blinded human label form."""
from pathlib import Path
import hashlib
import html
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import station_interpretation as study
import station_reference_context as human_context


def esc(value):
    return html.escape(str(value), quote=True)


STYLE = '''*{box-sizing:border-box}body{margin:0;background:#f5f5ef;color:#213c43;font:16px/1.65 system-ui,sans-serif}main{max-width:920px;margin:auto;padding:28px 24px 60px}h1{font:400 36px/1.2 Georgia,serif}h2{font-size:21px}a{color:#236c61;overflow-wrap:anywhere}section{padding:20px;border:1px solid #d7ddd8;background:#fffefa;border-radius:7px;margin:20px 0}.muted{font-size:13px;color:#536970}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:440px;overflow:auto;background:#eff2ec;padding:15px;font:13px/1.65 ui-monospace,monospace}details{margin:15px 0}summary{cursor:pointer;color:#236c61;font-weight:600}fieldset{border:0;padding:0;margin:12px 0}legend{font-weight:600}fieldset label{display:block;padding:8px;border:1px solid #d7ddd8;border-radius:4px;margin:7px 0;cursor:pointer}input{accent-color:#236c61}textarea{width:100%;padding:10px;font:inherit;border:1px solid #bdcec3;border-radius:4px}button{font:inherit;padding:7px 12px;border:1px solid #bdcec3;border-radius:4px;background:white;color:#213c43;cursor:pointer}.toolbar{position:sticky;top:0;background:#213c43;color:white;padding:12px 15px;display:flex;flex-wrap:wrap;gap:10px;align-items:center;z-index:2}.toolbar span{margin-right:auto;font-size:13px}table{width:100%;border-collapse:collapse;font-size:14px}td,th{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #d7ddd8}.table{overflow:auto}.notice{min-height:24px;font-size:13px}input:focus-visible,button:focus-visible,summary:focus-visible,textarea:focus-visible,a:focus-visible{outline:3px solid #c38623;outline-offset:3px}@media(max-width:600px){main{padding:16px 12px}h1{font-size:30px}section{padding:15px}}'''
STYLE += '''h3{font-size:15px;margin-top:24px}.kind{font-size:13px;color:#536970}.fact-table th{width:25%;font-weight:600}.fact-table td{font-size:15px}.written{border-left:3px solid #236c61;padding:3px 17px;background:#edf2eb;margin:12px 0;font-size:15px}.written p{white-space:pre-wrap}.decision{background:#f6eedb;padding:12px 15px;border-radius:4px}.boundary{font-size:13px;color:#536970}.review-case{border:1px solid #d7ddd8;border-radius:7px;background:#fffefa;margin:18px 0}.review-case>summary{padding:16px 20px;font-size:16px}.review-case>section{border:0;margin:0;border-top:1px solid #d7ddd8;border-radius:0}.source-note{font-size:12px;margin-top:7px}.technical{font-size:13px}.metric-table td,.metric-table th{font-size:13px}label:has(input:checked){background:#edf2eb;border-color:#236c61}.optional{font-size:14px}@media(max-width:600px){.fact-table th{width:30%}.fact-table td{font-size:14px}.review-case>summary{padding:14px}}'''


def page(title, body, script=''):
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + esc(title) + '</title><style>' + STYLE + '</style></head><body><main>' + body + '</main>' + ('<script>' + script + '</script>' if script else '') + '</body></html>'


def card(case, packet, design=None, context=None):
    criterion = packet['criterion']
    artifact = packet['files']['report.txt']
    shown = artifact['text'] if artifact['available'] else artifact['reason']
    if design:
        body = '<section data-case="' + case + '" id="' + case + '"><p class="kind">' + esc(design['kind']) + '</p><h2>' + esc(design['title']) + '</h2><p>' + esc(design['purpose']) + '</p><h3>1. What we know about this exercise</h3><div class="table"><table class="fact-table">'
        for title, fact in design['facts']:
            body += '<tr><th>' + esc(title) + '</th><td>' + esc(fact) + '</td></tr>'
        body += '</table></div>'
        if criterion == 'coverage_and_uncertainty' and artifact['available']:
            facts = context['facts']
            body += '<div class="table"><table class="metric-table"><tr><th>Forecast lead</th><th>Bilinear error</th><th>Nearest error</th><th>Shared observations</th></tr>'
            for i, lead in enumerate(facts['lead_hours']):
                body += f'<tr><td>{lead} hours</td><td>{facts["rmse_kelvin"][0][i]:.3f} K</td><td>{facts["rmse_kelvin"][1][i]:.3f} K</td><td>{facts["pooled_counts_by_lead"][i]}</td></tr>'
            body += '</table></div><p class="source-note">RMSE = root mean squared error; smaller means better agreement with the observations. A 1 K temperature difference is a 1 °C difference. Values are from the independent controller reference, whose two implementations were crosschecked during task preparation.</p>'
        body += '<h3>2. What the report says</h3>'
        for passage in design['report_passages']:
            assert passage in shown, 'Human excerpt is not an exact packet passage: ' + case
            body += '<blockquote class="written"><p>' + esc(passage) + '</p></blockquote>'
        body += '<p class="source-note">Exact passage' + ('s' if len(design['report_passages']) > 1 else '') + ' from the frozen ' + ('report' if artifact['available'] else 'availability record') + ' in case ' + case + '.</p>'
        body += '<h3>3. The decision</h3><p class="decision">' + esc(design['check']) + '</p><p class="boundary">' + esc(design['boundary']) + '</p>'
        body += '<fieldset><legend>Your assessment of this explanation</legend>'
        for choice, label in design['choices']:
            body += '<label><input type="radio" name="' + case + '" value="' + choice + '"> ' + esc(label) + '</label>'
        body += '</fieldset><label for="' + case + '-notes">What is unclear, missing or wrong? (optional)</label><textarea id="' + case + '-notes" rows="2"></textarea>'
        body += '<details class="technical"><summary>Check the supporting source record</summary>'
        if design['source_keys']:
            for key in design['source_keys']:
                source = context['task_passages'][key]
                body += '<p>' + esc(source['path']) + ' · line ' + str(source['line']) + '</p><blockquote class="written"><p>' + esc(source['quote']) + '</p></blockquote>'
        else:
            body += '<p>The unavailable report entry comes from this case’s frozen evidence packet.</p>'
        if criterion == 'constructed_control_attribution':
            body += '<p>The frozen input manifest also records synthetic_weather=false, constructed_mask=true and constructed_faults=true. <a href="station-reference.context.json">Inspect the factual record and source hashes</a>.</p>'
        body += '</details><details class="technical"><summary>Complete report and exact criterion</summary><pre>' + esc(shown) + '</pre><pre>' + esc(json.dumps(packet['rubric'], indent=2, ensure_ascii=False)) + '</pre><details><summary>Complete task instructions</summary><pre>' + esc(packet['task_contract']) + '</pre></details></details></section>'
        return body
    body = '<section data-case="' + case + '" id="' + case + '"><p class="muted">' + esc(case + ' · ' + criterion.replace('_', ' ')) + '</p><h2>' + esc(packet['rubric']['question']) + '</h2><ul>'
    body += ''.join('<li>' + esc(r) + '</li>' for r in packet['rubric']['requirements']) + '</ul>'
    body += '<p class="muted">' + esc(packet['rubric']['decision_rule']) + '</p><details><summary>Read the explanation and available evidence</summary><pre>' + esc(shown) + '</pre>'
    for name, item in packet['files'].items():
        if name != 'report.txt':
            body += '<p>' + esc(name) + '</p><pre>' + esc(item.get('text', item.get('reason', 'Unavailable'))) + '</pre>'
    if packet['controller']:
        body += '<p>Other checks, provided to test whether you keep requirements separate:</p><pre>' + esc(json.dumps(packet['controller'], indent=2)) + '</pre>'
    body += '<details><summary>Original task instructions</summary><pre>' + esc(packet['task_contract']) + '</pre></details></details><fieldset><legend>Your reference decision</legend>'
    for choice, label in [('pass', 'Pass: the explanation meets this requirement'), ('fail', 'Fail: a material contradiction or required omission'), ('unresolved', 'Unresolved: insufficient assessment evidence')]:
        body += '<label><input type="radio" name="' + case + '" value="' + choice + '"> ' + label + '</label>'
    return body + '</fieldset><label for="' + case + '-notes">Reason or uncertainty (optional)</label><textarea id="' + case + '-notes" rows="2"></textarea></section>'


SCRIPT = r'''
const bundle=@@BUNDLE@@, contextHash=@@CONTEXT@@, priorityCases=@@PRIORITY@@, storageKey='awb-station-reference:'+bundle, form=document.getElementById('review'), notice=document.getElementById('notice');
const cases=[...form.querySelectorAll('[data-case]')].map(x=>x.dataset.case);
function collect(){const fields={};for(const name of cases){fields[name]=form.querySelector('input[name="'+name+'"]:checked')?.value||'';fields[name+'-notes']=document.getElementById(name+'-notes').value;}return {schema_version:1,kind:'human_reference_judgments',review_bundle_sha256:bundle,review_presentation_version:2,review_context_sha256:contextHash,fields};}
function progress(){const fields=collect().fields;const primary=priorityCases.filter(x=>fields[x]).length,other=cases.filter(x=>!priorityCases.includes(x)&&fields[x]).length;document.getElementById('progress').textContent=primary+' of 5 main decisions'+(other?' · '+other+' optional':'');}
function restore(data){if(data.schema_version!==1||data.kind!=='human_reference_judgments'||data.review_bundle_sha256!==bundle||!data.fields||typeof data.fields!=='object')throw Error('Different review or invalid file. Your current notes were kept.');for(const c of cases){if(!['','pass','fail','unresolved'].includes(data.fields[c]||'')||typeof(data.fields[c+'-notes']||'')!=='string')throw Error('Invalid fields. Your current notes were kept.');}for(const c of cases){for(const el of form.querySelectorAll('input[name="'+c+'"]'))el.checked=el.value===data.fields[c];document.getElementById(c+'-notes').value=data.fields[c+'-notes']||'';}progress();}
function save(){try{localStorage.setItem(storageKey,JSON.stringify(collect()));}catch(e){notice.textContent='Browser storage unavailable. Export to preserve your decisions.';}progress();}
try{const saved=localStorage.getItem(storageKey);if(saved)restore(JSON.parse(saved));}catch(e){notice.textContent='Saved decisions could not be restored. You can still rate and export.';}
form.addEventListener('submit',e=>e.preventDefault());form.addEventListener('input',save);form.addEventListener('change',save);
document.getElementById('export').onclick=()=>{save();const url=URL.createObjectURL(new Blob([JSON.stringify(collect(),null,2)+'\n'],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='station-reference-decisions.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notice.textContent='Exported the decisions you made. Unrated cases remain unconfirmed.';};
document.getElementById('import').onclick=()=>document.getElementById('import-file').click();
document.getElementById('import-file').onchange=async e=>{try{const file=e.target.files[0];if(file){restore(JSON.parse(await file.text()));save();notice.textContent='Imported your decisions.';}}catch(error){notice.textContent=error.message;}finally{e.target.value='';}};
progress();
'''


def main():
    packets = study.packets()
    reference = study.read(study.STUDY / 'private/reference.json')
    lineage = study.read(study.STUDY / 'private/lineage.json')
    wanted = ('natural-attribution', 'natural-uncertainty', 'uncertainty-negative-and-inconclusive', 'uncertainty-independent-replicates', 'uncertainty-missing-evidence')
    selected = [next(k for k, v in lineage.items() if v['contrast'] == name) for name in wanted]
    context = human_context.load_context()
    assert all(p['task_contract'] == (ROOT / 'tasks/station-verification/prompt.md').read_text() for p in packets.values()), 'Human context differs from the judge task contract'
    context_path = ROOT / 'var/review/station-reference.context.json'
    study.write(context_path, context)
    designs = {case: human_context.design(case, packet, lineage, context) for case, packet in packets.items()}
    body = '<p class="muted">Station verification · Reviewing the judge’s reference cases</p><h1>What was known?<br>What did the report conclude?</h1><p>An agent compared temperature forecasts with six East African weather stations. We are testing whether a judge can recognize a defensible explanation and identify an unsupported claim. Each example below supplies the deciding facts, exact report passages and one specific question.</p><p>This annotation form is optional; the <a href="station-audit.html">autonomous agent audit</a> continues without human labels. Two examples use the actual agent report; three were deliberately constructed to test the judge. You can answer any subset, or use the notes to explain why a case remains unreviewable. Judge and assistant decisions are hidden.</p><div class="toolbar"><span id="progress">0 of 5 main decisions</span><button type="button" id="export">Export decisions</button><button type="button" id="import">Import decisions</button><input hidden type="file" accept="application/json" id="import-file"></div><p class="notice" id="notice" role="status"></p><form id="review">'
    for number, case in enumerate(selected, 1):
        body += '<details class="review-case"' + (' open' if number == 1 else '') + '><summary>' + str(number) + '. ' + esc(designs[case]['title']) + '</summary>' + card(case, packets[case], designs[case], context) + '</details>'
    body += '<details class="optional"><summary>Optional: the remaining thirteen reference cases</summary>'
    for case, packet in packets.items():
        if case not in selected:
            body += '<details class="review-case"><summary>' + esc(case + ' · ' + designs[case]['title']) + '</summary>' + card(case, packet, designs[case], context) + '</details>'
    body += '</details></form><p class="muted">Nothing is preselected. Choices save locally and export as human reference decisions; no unreviewed case is inferred from agreement. Original benchmark grades remain unchanged.</p><p class="muted">Presentation version 2 adds factual context and plain-language questions. The frozen judge packets, criteria, provisional labels and 18-case result are unchanged. Existing notes use the same storage key and remain available.</p>'
    bundle = reference['reference_bundle_sha256']
    review = ROOT / 'var/review/station-reference.html'
    script = SCRIPT.replace('@@BUNDLE@@', json.dumps(bundle)).replace('@@CONTEXT@@', json.dumps(study.digest(context_path))).replace('@@PRIORITY@@', json.dumps(selected))
    review.write_text(page('Station interpretation reference decisions', body, script))

    comparison = study.read(study.STUDY / 'comparison.json')
    score = comparison['all']
    agreement = score['exact_agreement']
    summary = '<p class="muted">Station verification · Judge development check</p><h1>A first interpretation-judge check.</h1><p>A Luna-class subscription judge agreed with the frozen provisional references on <strong>' + str(agreement['numerator']) + ' of ' + str(agreement['denominator']) + ' criterion cases</strong>. The references were developed from the task contract and reviewed independently by two assistants before the judge ran.</p><p><strong>This is development agreement, not human-validated judge accuracy.</strong> Eighteen cases derive from one previously inspected report: two natural criterion assessments and sixteen constructed text contrasts. No fresh workflow, held-out parent or task-transfer test was run.</p>'
    summary += '<section><h2>What this check tested</h2><ul><li>Recognizing curator-created controls and genuine observations.</li><li>Accepting equivalent explanations and honestly inconclusive or negative findings.</li><li>Rejecting outage/historical-bug misattribution, independence assumptions, global-rank and terrain-cause overclaims.</li><li>Keeping unrelated numerical and packaging defects separate.</li><li>Ignoring an instruction embedded in a report and abstaining when evidence is unavailable.</li></ul></section>'
    summary += '<section><h2>Observed outcomes</h2><div class="table"><table><tr><th>Criterion</th><th>Agreement</th><th>False acceptance</th><th>False rejection</th></tr>'
    for criterion, metrics in comparison['by_criterion'].items():
        count = metrics['exact_agreement']
        summary += '<tr><td>' + esc(criterion.replace('_', ' ')) + '</td><td>' + str(count['numerator']) + '/' + str(count['denominator']) + '</td><td>' + str(metrics['false_acceptance']) + '</td><td>' + str(metrics['false_rejection']) + '</td></tr>'
    summary += '</table></div><p>All 18 output records passed schema and exact-passage citation checks. This verifies that cited text exists, not that every rationale is scientifically sound.</p><p>No separately billed API calls, dataset downloads or Docker runs. Subscription token charges are not available; measured cost is recorded as unknown.</p></section>'
    summary += '<section><h2>Continued autonomous review</h2><p>The <a href="station-audit.html">full-source agent audit and evidence-based judge check</a> continues this work without requiring you to label cases. The <a href="station-reference.html">human annotation form</a> remains optional and retains existing notes. Human-confirmed accuracy stays unset unless explicit labels are supplied. A fresh independent workflow is required before claiming general judge reliability.</p></section><details><summary>Inspect every case, reference and judge decision</summary>'
    judge = study.validate(study.read(study.STUDY / 'reviews/judge-luna.json'), packets)
    for case, packet in packets.items():
        ref = reference['records'][case]
        summary += '<details><summary>' + esc(case + ' · ' + packet['criterion'].replace('_', ' ') + ' · reference ' + ref['verdict'] + ', judge ' + judge[case]['verdict']) + '</summary><pre>' + esc(json.dumps({'reference': ref, 'judge': judge[case]}, indent=2)) + '</pre><pre>' + esc(packet['files']['report.txt'].get('text') or packet['files']['report.txt']['reason']) + '</pre></details>'
    summary += '</details><p class="muted">Original task versions, evaluation lock and run assessments were preserved. This subscription helper check does not exercise the locked native autojudge adapter. Reviewers had fresh contexts and were instructed to read only the public packets; shared-host filesystem access was not restricted by an OS sandbox. Full packet and response records are retained, while helper tool traces remain in the platform conversation rather than the benchmark controller log.</p>'
    result = ROOT / 'var/review/station-judge.html'
    result.write_text(page('Station interpretation judge check', summary))
    manifest = {'schema_version': 1, 'reference_bundle_sha256': bundle, 'reference_review_cases': selected,
                'review_presentation_version': 2, 'review_context_sha256': study.digest(context_path),
                'source_hashes': {str(p.relative_to(ROOT)): study.digest(p) for p in [Path(__file__), ROOT / 'scripts/station_reference_context.py', context_path, study.STUDY / 'comparison.json', study.STUDY / 'private/reference.json', study.STUDY / 'reviews/judge-luna.json', study.STUDY / 'execution-metadata.json']},
                'html_hashes': {p.name: study.digest(p) for p in (review, result)}}
    study.write(ROOT / 'var/review/station-judge.sources.json', manifest)
    print(json.dumps({'result_page': str(result), 'human_review_page': str(review), 'initial_human_decisions': len(selected), 'total_available': len(packets)}))


if __name__ == '__main__':
    main()
