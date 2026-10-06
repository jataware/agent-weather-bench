"""Current result presentation; frozen assessment inputs stay immutable."""
import hashlib
import json
from pathlib import Path
import station_evidence_audit as audit


def main():
    result = audit.compare()
    validation_path = audit.STUDY / 'citation-validation-initial.json'
    validation = audit.read(validation_path)
    original = audit.read(audit.STUDY / 'reviews/judge-luna.before-citation-repair.json')
    repaired = audit.read(audit.STUDY / 'reviews/judge-luna.json')
    first = {row['case']: row for row in original['ratings']}
    last = {row['case']: row for row in repaired['ratings']}
    assert first.keys() == last.keys()
    for case in first:
        assert {k:v for k,v in first[case].items() if k != 'citations'} == {k:v for k,v in last[case].items() if k != 'citations'}, 'Citation repair changed decisions: '+case
    result['initial_response_validation'] = {'valid': False, 'invalid_exact_citations': len(validation['invalid_exact_citations']), 'affected_cases': validation['affected_cases'], 'initial_schema_valid_case_records': len(first)-len(validation['affected_cases']), 'repair': 'Citation-only repair; all decisions, reasons and confidence unchanged.', 'verdict_correctness_feedback': False, 'repair_history': audit.read(audit.STUDY / 'citation-repair-history.json')}
    audit.write(audit.STUDY / 'comparison.json', result)
    output = Path(audit.render()['report'])
    text = output.read_text().replace('What the judge learned to distinguish', 'What the judge was tested on')
    note = '<section><h2>A judge failure caught by validation</h2><p>The first response contained two non-exact citations in two cases. One cited a field absent from the original answer; the other paraphrased the task contract as an exact quote. The response failed citation validation. The initial file is preserved, and a citation-only agent repair still left one non-exact quote. The controller removed that remaining quote because two exact report citations already supported the same conclusion. Every verdict, reason and confidence stayed unchanged. The agreement score describes these decisions; it does not mean the original response passed all checks.</p><p><a href="../calibration/station-evidence-audit-v2/citation-validation-initial.json">Initial validation failures</a> · <a href="../calibration/station-evidence-audit-v2/reviews/judge-luna.before-citation-repair.json">Unrepaired response</a> · <a href="../calibration/station-evidence-audit-v2/citation-repair-history.json">Repair history</a></p></section>'
    text = text.replace('<section><h2>What happens next</h2>', note+'<section><h2>What happens next</h2>')
    output.write_text(text)
    audit.write(audit.ROOT / 'var/review/station-audit.sources.json', {'report_sha256':audit.digest(output),'renderer_sha256':audit.digest(__file__),'reference_bundle_sha256':result['reference_bundle_sha256'],'judge_output_sha256':result['judge_output_sha256'],'initial_validation_sha256':audit.digest(validation_path),'amendment_sha256':audit.digest(audit.STUDY/'amendment-01.json')})
    print(json.dumps({'result_page':str(output),'decision_agreement':result['all']['exact_agreement'],'initial_invalid_citations':2},indent=2))

if __name__ == '__main__':
    main()
