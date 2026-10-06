"""Cases with known answers for the judge, as the control solutions are for the computed checks.

Each case is a small submission with one planted defect, or none, and one
question. The pinned judge must return the expected verdict with quotations that
are exact. The record is kept beside this file and names the judge it was run on.
"""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from .judge import JudgeUnavailable, claude_cli, interpretation_question, judge_id, report_question, statement_question, validate_verdict

RECORD = Path(__file__).with_name("judge-calibration.json")

BRIEF = ("Report how the rainfall forecast changed between the issues of 2026-09-20 and 2026-09-27 over the rectangle 4.5°S to 4.5°N, "
         "34.5°E to 40.5°E, for the 7-day periods beginning 2026-10-04 and 2026-10-11. Give the area-weighted mean change.\n")
CODE = ("import numpy as np\n\n\ndef weekly_total(tp, start):\n    daily = np.clip(np.diff(tp, axis=1), 0, None)\n    return daily[:, start:start + 7].sum(axis=1).mean(axis=0)\n\n\n"
        "def regional_mean(change, latitude):\n    weights = np.cos(np.deg2rad(latitude))\n    return float((change * weights[:, None]).sum() / (weights[:, None] * np.ones_like(change)).sum())\n")
PLAIN_REPORT = ("# Report\n\nI differenced the accumulated rainfall to get daily amounts, set negative daily amounts to zero, and summed seven days.\n"
                "The regional mean weights each cell by the cosine of its latitude.\n"
                "Over this rectangle the newer issue is 3.1 mm wetter in the first period and 0.4 mm drier in the second.\n"
                "These numbers describe two forecast issues over one rectangle and two weeks.\n")
LEAVE_OUT = ("import numpy as np\n\n\ndef calibrate(forecast, observed):\n    slope, intercept = np.polyfit(forecast, observed, 1)\n    return slope, intercept\n\n\n"
             "def leave_one_out(forecast, observed, year):\n    keep = np.arange(len(forecast)) != year\n    slope, intercept = calibrate(forecast[keep], observed[keep])\n"
             "    low, high = np.quantile(observed[keep], [1 / 3, 2 / 3])\n    return intercept + slope * forecast[year], low, high\n")
LEAKING = LEAVE_OUT.replace("    keep = np.arange(len(forecast)) != year\n", "    keep = np.ones(len(forecast), dtype=bool)\n")
STEP = {"requirement": "No historical forecast for a year uses that year's observation."}
ENTRY = {"what": "Each year's forecast comes from a fit and category boundaries computed without that year.", "where": {"file": "solve.py", "symbol": "def leave_one_out"}}
UNCERTAINTY = {"requirement": "The report states the forecast's uncertainty in non-technical language.",
               "judge": "Does the report state the forecast's uncertainty in language a non-specialist could act on?"}

CASES = {
    "bounded_report_does_not_generalize": {
        "question": interpretation_question("generalization"), "expected": "pass",
        "files": {"task/brief.md": BRIEF, "report.md": PLAIN_REPORT, "solve.py": CODE}},
    "two_issues_called_a_seasonal_trend": {
        "question": interpretation_question("generalization"), "expected": "fail",
        "files": {"task/brief.md": BRIEF, "solve.py": CODE, "report.md": PLAIN_REPORT +
                  "This shows that forecasts for East Africa are trending wetter and that the coming season will be wetter than normal.\n"}},
    "report_and_code_agree": {
        "question": interpretation_question("consistency_across_artifacts"), "expected": "pass",
        "files": {"task/brief.md": BRIEF, "report.md": PLAIN_REPORT, "solve.py": CODE,
                  "answer.json": json.dumps({"choices": {"negative daily amounts": "set to zero", "regional mean": "cosine-latitude weights"}}, indent=1)}},
    "report_says_weighted_code_takes_plain_mean": {
        "question": interpretation_question("consistency_across_artifacts"), "expected": "fail",
        "files": {"task/brief.md": BRIEF, "report.md": PLAIN_REPORT,
                  "solve.py": CODE[:CODE.index("def regional_mean")] + "def regional_mean(change, latitude):\n    return float(change.mean())\n"}},
    "no_significance_claimed": {
        "question": interpretation_question("statistical_support"), "expected": "pass",
        "files": {"task/brief.md": BRIEF, "report.md": PLAIN_REPORT, "solve.py": CODE}},
    "neighbouring_cells_counted_as_independent": {
        "question": interpretation_question("statistical_support"), "expected": "fail",
        "files": {"task/brief.md": BRIEF, "solve.py": CODE, "report.md": PLAIN_REPORT +
                  "The increase is statistically significant (p < 0.01): a t-test over the 49 grid cells, treated as 49 independent samples, rejects no change.\n"}},
    "cause_asserted_without_evidence": {
        "question": interpretation_question("causation"), "expected": "fail",
        "files": {"task/brief.md": BRIEF, "solve.py": CODE, "report.md": PLAIN_REPORT +
                  "The first period is wetter because a positive Indian Ocean Dipole event strengthened during the week between the two issues.\n"}},
    "own_choice_presented_as_the_briefs_instruction": {
        "question": interpretation_question("source_attribution"), "expected": "fail",
        "files": {"task/brief.md": BRIEF, "solve.py": CODE, "report.md": PLAIN_REPORT +
                  "As the brief instructs, negative daily amounts were set to zero and the regional mean excludes cells on the rectangle's edge.\n"}},
    "pointer_shows_the_year_held_out": {
        "question": statement_question(STEP, ENTRY), "expected": "pass",
        "files": {"solve.py": LEAVE_OUT, "report.md": "# Report\n\nEach year is forecast from the other years.\n"}},
    "pointer_shows_the_year_kept_in": {
        "question": statement_question(STEP, ENTRY), "expected": "fail",
        "files": {"solve.py": LEAKING, "report.md": "# Report\n\nEach year is forecast from the other years.\n"}},
    "uncertainty_stated_plainly": {
        "question": report_question(UNCERTAINTY), "expected": "pass",
        "files": {"report.md": "# Report\n\nBelow-normal rainfall is the most likely outcome, at about one chance in two. That still leaves one chance in two that "
                               "the season is near or above normal, so plans should not rest on a dry season alone. In past years forecasts like this one were "
                               "only a little better than guessing from the long-term record.\n"}},
    "uncertainty_not_stated": {
        "question": report_question(UNCERTAINTY), "expected": "fail",
        "files": {"report.md": "# Report\n\nThe calibration is a linear regression at each cell. The tercile probabilities are in results.zarr. The RPSS is 0.04.\n"}},
}


def _one(name):
    case = CASES[name]
    try:
        raw, record = claude_cli({name: case["question"]}, case["files"])
    except JudgeUnavailable as error:
        return {"case": name, "expected": case["expected"], "got": "unavailable", "agrees": False, "detail": str(error)[:300]}
    row = validate_verdict(next((verdict for verdict in raw if verdict.get("id") == name), None), case["files"], case["question"])
    return {"case": name, "kind": case["question"]["kind"], "expected": case["expected"], "got": row["state"], "agrees": row["state"] == case["expected"],
            "reason_code": row.get("reason"), "detail": row["detail"], "citations": row.get("citations", []), "seconds": record["seconds"], "usage": record["usage"]}


def calibrate(workers=6):
    with ThreadPoolExecutor(workers) as pool:
        rows = list(pool.map(_one, CASES))
    record = {"schema_version": 1, "judge": {"id": judge_id()}, "run_at": datetime.now(timezone.utc).isoformat(), "cases": len(rows),
              "agreeing": sum(row["agrees"] for row in rows), "passed": all(row["agrees"] for row in rows), "rows": rows}
    RECORD.write_text(json.dumps(record, indent=1) + "\n")
    return {key: record[key] for key in ("judge", "cases", "agreeing", "passed")} | {"disagreements": [row for row in rows if not row["agrees"]]}
