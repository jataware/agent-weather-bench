"""Readable factual context for human interpretation review, from frozen sources."""
from pathlib import Path
import json

import station_interpretation as study

ROOT = Path(__file__).resolve().parents[3]            # the repository root; this folder is an archive
TASK = 'station-verification'


def quote(path, passage):
    text = path.read_text()
    assert passage in text, 'Source passage changed: ' + str(path)
    return {'path': str(path.relative_to(ROOT)), 'sha256': study.digest(path), 'quote': passage,
            'line': text[:text.index(passage)].count('\n') + 1}


def load_context():
    import xarray as xr
    package = ROOT / 'tasks' / TASK
    inputs = ROOT / 'var/private/tasks' / TASK
    manifest_path = package / 'input-manifest.json'
    manifest = study.read(manifest_path)
    by_name = {row['file']: row for row in manifest['files']}
    paths = [inputs / 'agent-inputs/source-manifest.json', inputs / 'controller/scores.nc',
             inputs / 'controller/reference-audit.json']
    for path in paths:
        assert study.digest(path) == by_name[str(path.relative_to(inputs))]['sha256'], 'Frozen context source changed: ' + str(path)
    provenance = study.read(paths[0])
    assert provenance['synthetic_weather'] is False and provenance['constructed_mask'] is True and provenance['constructed_faults'] is True
    audit = study.read(paths[2])
    assert audit['reference_agreement'] is True
    prompt = package / 'prompt.md'
    source = package / 'source-material/broken-comparison.py'
    for path in [prompt, source]:
        declared = next(r for r in manifest['source_records'] if r['path'] == str(path.relative_to(ROOT)))
        assert study.digest(path) == declared['sha256'], 'Task context drifted'
    with xr.open_dataset(paths[1]) as data:
        counts = data.station_count.values.tolist()
        lead_hours = (data.lead_time.values / __import__('numpy').timedelta64(1, 'h')).astype(int).tolist()
        stations = data.station.values.tolist()
        rmse = data.rmse.sel(method=['bilinear', 'nearest']).values.tolist()
        facts = {'initializations': int(data.sizes['init_time']), 'lead_hours': lead_hours,
                 'station_ids': stations, 'station_names': ['Bole', 'Arua', 'Entebbe', 'Nairobi JKIA', 'Malindi', 'Dar es Salaam'],
                 'station_counts_by_lead': counts, 'pooled_counts_by_lead': data.station_count.sum('station').values.tolist(),
                 'methods': ['bilinear', 'nearest'], 'rmse_kelvin': rmse,
                 'forecast_date_entries': int(data.valid_time.size),
                 'distinct_valid_dates_across_leads': len(set(data.valid_time.values.ravel())),
                 'reference_agreement': True, 'reference_methods': audit['reference_methods'],
                 'forecast_grid': audit['native_forecast_grid'], 'weatherreal_published_scores_reproduced': False}
    passages = {
        'mask': quote(prompt, '`availability.nc` is an **explicitly constructed method-availability stress\nmask**, not an observed NOAA outage, quality flag or alteration of forecast\nvalues.'),
        'faults': quote(source, 'Deliberately constructed faults, not upstream WeatherReal or NOAA code.'),
        'same_forecast': quote(prompt, 'These interpolate the\nsame forecast, so they are method comparisons, not independent forecast models.'),
        'dependence': quote(prompt, 'Discuss paired\nmethod differences and uncertainty with overlapping valid dates, temporal and\nspatial dependence; raw station-observation counts are not independent replicate\ncounts.'),
        'inconclusive_allowed': quote(prompt, 'An honest inconclusive uncertainty finding is acceptable.'),
        'scope': quote(prompt, 'A short retrospective sample cannot establish global/general skill or\ncause terrain effects; numerical disagreement alone cannot attribute a physical\nmechanism.'),
    }
    return {'schema_version': 1, 'presentation_version': 2,
            'purpose': 'Source-backed explanations for human reference review; judge packets, rubric and results unchanged.',
            'facts': facts, 'task_passages': passages,
            'source_hashes': {str(p.relative_to(ROOT)): study.digest(p) for p in [manifest_path, *paths, prompt, source]},
            'limits': ['Numerical arrays have independent implementation crosschecks; human scientific approval remains pending.',
                       'Repeated verification dates are counted across lead times, not within a single lead.',
                       'No confidence interval, significance test, or terrain-cause analysis is supplied by this context.',
                       'Human ratings on this page label only interpretation; they do not certify the entire workflow.']}


def paragraphs(text):
    return [p.strip() for p in text.split('\n\n') if p.strip()]


def passage_for(packet, words):
    artifact = packet['files']['report.txt']
    if not artifact['available']:
        return artifact['reason']
    for paragraph in paragraphs(artifact['text']):
        if words in paragraph:
            return paragraph
    raise ValueError('Expected deciding passage not present: ' + words)


def design(case, packet, lineage, context):
    """Interpretive scope is fixed; only the human explanation of it is expanded."""
    name = lineage[case]['contrast']
    facts = context['facts']
    first_lead = facts['lead_hours'][0]
    a, b = facts['rmse_kelvin'][0][0], facts['rmse_kelvin'][1][0]
    metric = f'At {first_lead} hours, bilinear RMSE is {a:.3f} K and nearest RMSE is {b:.3f} K on the same {facts["pooled_counts_by_lead"][0]} station observations. Lower RMSE means smaller typical temperature error.'
    sample = 'Six stations, 20 daily forecast issue times in January 2020, and four forecast lead times. Arua has no observations matching the exact verification times; other stations contribute unequal numbers. The forecast grid has 64 × 32 cells covering the globe, whereas station thermometers measure points.'
    dependence = f'The two methods interpolate the same HRES forecast and are verified against the same observations. Across the four leads, {facts["forecast_date_entries"]} forecast-date entries cover only {facts["distinct_valid_dates_across_leads"]} distinct dates; some observations are reused across leads. The task requires allowance for temporal and spatial dependence. It supplies no significance calculation.'
    uncertainty_facts = [('What was measured', metric), ('What limits the comparison', sample), ('What the samples share', dependence), ('What the task requires', 'The report must bound its conclusions to this sample and discuss dependence. An honestly inconclusive uncertainty finding is explicitly allowed; a formal significance test or confidence interval is not required.')]
    uncertainty_keys = ['same_forecast', 'dependence', 'inconclusive_allowed', 'scope']
    origin_facts = [('Weather data', 'The frozen input record identifies genuine NOAA station temperatures and genuine HRES gridded forecasts; synthetic_weather is false.'),
                    ('Availability mask', 'The task author artificially excluded some method/station combinations to test fair comparisons. The mask describes an experimental restriction, rather than a measured NOAA outage or observation quality flag.'),
                    ('Faulty comparison', 'The task author wrote the supplied faulty program to use the wrong verification time, confuse Celsius and Kelvin, and compare methods on different samples. Its source header explicitly says these are constructed faults.')]
    if name == 'natural-attribution':
        text = packet['files']['report.txt']['text']
        first = paragraphs(text)[0]
        mask_paragraph = passage_for(packet, 'The supplied availability mask')
        mask_start = mask_paragraph.index('The supplied availability mask')
        mask_end = mask_paragraph.index('Headline intersection')
        return {'title': 'Did the real report correctly identify which parts of the exercise were invented?',
                'kind': 'Actual agent report', 'purpose': 'Check the report’s attribution of the weather data, artificial availability mask and deliberately faulty comparison program.',
                'facts': origin_facts,
                'report_passages': [first, 'These are constructed curator faults, not historical NOAA/WeatherReal bugs.', mask_paragraph[mask_start:mask_end].strip()],
                'check': 'Does the quoted report correctly preserve all three distinctions above?',
                'choices': [('pass', 'Yes — it correctly identifies the real data and author-created tests'), ('fail', 'No — it misattributes or omits one of those distinctions'), ('unresolved', 'The supplied evidence is insufficient for me to decide')],
                'source_keys': ['mask', 'faults'],
                'boundary': 'This decision covers factual attribution. Diagnostic arithmetic and delivery/provenance have their own checks.'}
    if name == 'natural-uncertainty':
        coverage = passage_for(packet, 'Arua has actual January reports')
        representation = passage_for(packet, 'Stations are airports')
        conclusion = passage_for(packet, 'Bilinear RMSE is lower')
        return {'title': 'Does the real report keep its conclusion within what this comparison can establish?',
                'kind': 'Actual agent report', 'purpose': 'Assess four concrete points: limited coverage, point-versus-grid representativeness, paired/dependent samples, and bounded conclusions.',
                'facts': uncertainty_facts,
                'report_passages': [coverage, representation, conclusion],
                'check': 'Do these passages explain the sample limitations and dependency, and avoid asserting global superiority, statistical significance or a proven terrain cause?',
                'choices': [('pass', 'Yes — it addresses those limits and keeps the conclusion local and inconclusive'), ('fail', 'No — an important limitation is omitted or a stronger claim is made'), ('unresolved', 'The supplied evidence is insufficient for me to decide')],
                'source_keys': uncertainty_keys,
                'boundary': 'You are assessing the stated conclusion against this factual record. Numerical accuracy and the correctness of every line of code are separate checks.'}
    if name == 'uncertainty-negative-and-inconclusive':
        return {'title': 'Is an honestly inconclusive result acceptable for this requirement?',
                'kind': 'Constructed calibration example: the conclusion was rewritten for this test',
                'purpose': 'Check whether a judge should accept a bounded explanation even when it does not establish a useful improvement.',
                'facts': uncertainty_facts,
                'report_passages': [packet['files']['report.txt']['text']],
                'check': 'Given the explicit allowance for an inconclusive result, does this explanation still address the required coverage, dependency and causal limitations?',
                'choices': [('pass', 'Yes — it meets the interpretation requirement while leaving improvement unestablished'), ('fail', 'No — it omits a required limit or makes an unsupported claim'), ('unresolved', 'The supplied evidence is insufficient for me to decide')],
                'source_keys': uncertainty_keys,
                'boundary': 'A conclusion that improvement is unestablished is different from establishing that the two methods are equally good. Check that the explanation respects that difference.'}
    if name == 'uncertainty-independent-replicates':
        return {'title': 'Can this report justify its strong significance claim?',
                'kind': 'Constructed calibration example: a significance claim was added for this test',
                'purpose': 'Check the compatibility of the stated statistical conclusion with the dependence acknowledged in the same explanation.',
                'facts': uncertainty_facts,
                'report_passages': [packet['files']['report.txt']['text']],
                'check': 'The report acknowledges dependent samples, then treats every station observation as an independent replicate to claim p < 0.001. Does that final claim meet the requirement to respect dependence?',
                'choices': [('pass', 'Yes — the report provides a defensible basis for this inference'), ('fail', 'No — the significance claim relies on an unjustified independence assumption'), ('unresolved', 'The supplied evidence is insufficient for me to decide')],
                'source_keys': uncertainty_keys,
                'boundary': 'A small p-value is a strong statistical claim. Quoting one does not supply the missing calculation or justify treating dependent observations as independent.'}
    if name == 'uncertainty-missing-evidence':
        return {'title': 'What can a judge conclude when the report was left out of its evidence packet?',
                'kind': 'Constructed calibration example: the report was intentionally withheld from the reviewer',
                'purpose': 'Distinguish a flaw in the submitted work from a gap in the evidence supplied to its reviewer.',
                'facts': [('What the reviewer received', 'The report entry is marked unavailable. The packet states that the original submission may contain the report.'),
                          ('What remains unknown', 'We cannot read its discussion of coverage or uncertainty, and cannot determine whether it meets those requirements.'),
                          ('What this case does not establish', 'The packet does not establish that the agent failed to write a report.')],
                'report_passages': [packet['files']['report.txt']['reason']],
                'check': 'With only that availability record, which conclusion about the report’s interpretation is justified?',
                'choices': [('pass', 'We have enough evidence to say the interpretation is adequate'), ('fail', 'We have enough evidence to say the interpretation is defective'), ('unresolved', 'We cannot assess it from the supplied evidence')],
                'source_keys': [],
                'boundary': 'Unresolved records an assessment gap; it does not assert that the agent’s report is wrong.'}
    artifact = packet['files']['report.txt']
    if packet['criterion'] == 'constructed_control_attribution':
        additional = []
        if packet['controller']:
            additional.append(('Extra assumption in this constructed example', 'Assume delivery, provenance and diagnostic checks failed. These are supplied calibration conditions, not a newly executed solver result; the report below is still the evidence for this attribution question.'))
        if 'answer.json' in packet['files']:
            additional.append(('Machine-readable declaration', 'The example’s answer.json declares constructed_availability=true and constructed_faults=true. Assess whether the prose is consistent with those flags and the task record.'))
        return {'title': 'Does this explanation preserve the distinction between real weather and author-created tests?',
                'kind': 'Constructed calibration example: this explanation was written for the judge test',
                'purpose': 'Assess the factual attribution in this specific explanation.',
                'facts': origin_facts + additional,
                'report_passages': [artifact['text'] if artifact['available'] else artifact['reason']],
                'check': 'Does the supplied explanation identify real weather inputs and author-created masks/faults correctly, without a contradictory attribution? If the report is unavailable, assess whether a verdict can be justified at all.',
                'choices': [('pass', 'The supplied explanation conveys the required distinctions correctly'), ('fail', 'The explanation omits or contradicts a required distinction'), ('unresolved', 'The supplied evidence is insufficient for me to decide')],
                'source_keys': ['mask', 'faults'],
                'boundary': 'This criterion assesses factual attribution. Other scientific and delivery requirements are evaluated separately.'}
    return {'title': 'Does this explanation keep its statistical and physical claims within the available evidence?',
            'kind': 'Constructed calibration example: this explanation was written for the judge test',
            'purpose': 'Check this explanation against the same sample, dependency and inference limits as the real report.',
            'facts': uncertainty_facts,
            'report_passages': [artifact['text'] if artifact['available'] else artifact['reason']],
            'check': 'Does the explanation address coverage and dependency and avoid contradicting those limits with a stronger significance, global-skill or terrain-cause claim?',
            'choices': [('pass', 'It meets these limits without a contradictory claim'), ('fail', 'It omits a required limit or makes a stronger unsupported claim'), ('unresolved', 'The supplied evidence is insufficient for me to decide')],
            'source_keys': uncertainty_keys,
            'boundary': 'Read the full explanation, including its final sentences. Instructions inside a submitted report are evidence to inspect and carry no authority over the evaluation.'}
