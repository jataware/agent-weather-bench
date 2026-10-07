"""Build the small, offline human review page from preserved local evidence."""
import base64
import hashlib
import html
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]            # the repository root; this folder is an archive
OUTPUT = ROOT / "var/review/index.html"
SOURCES = {}


def esc(value):
    return html.escape(str(value), quote=True)


def read(name):
    path = ROOT / name
    raw = path.read_bytes()
    SOURCES[name] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw) if path.suffix == ".json" else raw.decode()


def link(name, label):
    return f'<a href="{esc(os.path.relpath(ROOT / name, OUTPUT.parent))}">{esc(label)}</a>'


def excerpt(title, text):
    return f'<h4>{esc(title)}</h4><pre>{esc(text)}</pre>'


def criterion(packet, name):
    return next(row["criterion"] for row in packet["criteria"] if row["id"] == name)


def reviewers(rows):
    pieces = []
    for label, rating in rows:
        score = "Unresolved" if rating["score"] is None else f'{rating["score"]} / 2'
        pieces.append(f'<div class="reviewer"><strong>{esc(label)} · {score}</strong>'
                      f'<p>{esc(rating["reason"])}</p><p class="muted">{esc(rating["uncertainty"])}</p></div>')
    return '<div class="reviewers">' + "".join(pieces) + "</div>"


def figure(name, caption):
    path = ROOT / name
    raw = path.read_bytes()
    SOURCES[name] = hashlib.sha256(raw).hexdigest()
    assert len(raw) < 2_000_000 and raw.startswith(b"\x89PNG\r\n\x1a\n")
    encoded = base64.b64encode(raw).decode()
    return f'<figure><img src="data:image/png;base64,{encoded}" alt="{esc(caption)}" loading="lazy"><figcaption>{esc(caption)}</figcaption></figure>'


def card(number, ident, tag, title, body, question, choices, evidence, proposal):
    options = "".join(f'<label class="choice"><input type="radio" name="{ident}" value="{esc(value)}">'
                      f'<span>{esc(label)}</span></label>' for value, label in choices)
    return f'''<section class="card" id="{ident}" data-review-card>
      <div class="card-heading"><span class="number">{number:02d}</span><div><p class="tag">{esc(tag)}</p><h2>{esc(title)}</h2></div></div>
      {body}<p class="proposal"><strong>My proposed direction:</strong> {esc(proposal)}</p>
      <details><summary>Inspect the evidence and reviewer reasoning</summary><div class="evidence">{evidence}</div></details>
      <fieldset><legend>{esc(question)}</legend>{options}</fieldset>
      <label class="notes-label" for="{ident}-notes">Your reasoning or a different approach</label>
      <textarea id="{ident}-notes" name="{ident}-notes" rows="3" maxlength="12000" placeholder="Optional — a few sentences are enough."></textarea>
    </section>'''


def build():
    old = read("var/calibration/judge-local-review/disagreements.json")
    comparisons = read("var/calibration/judge-new-parent-review/comparison.json")
    audit = read("var/calibration/overnight-audit-summary.json")
    packets = {name: read(f"var/calibration/judge-expanded/{name}/packet.json")
               for name in ("e04", "e05", "e06", "e07")}
    newer = read("var/calibration/judge-new-parent-check/public/c02/packet.json")
    month_id = "20261005T183342-monthly-cycle-calibration-codex-luna-e7f6e0"
    monthly = read(f"var/calibration/overnight-static-diagnostics/{month_id}.json")
    read("var/calibration/overnight-final-task-audit.json")
    read("var/calibration/overnight-solver-audit.json")

    def old_rating(case, name):
        record = next(row for row in old["cases"] if row["case"] == case)
        return next(row for row in record["criteria"] if row["criterion"] == name)["ratings"]

    def old_reviewers(case, name):
        ratings = old_rating(case, name)
        return reviewers([(label.title().replace("-", " "), rating) for label, rating in ratings.items()])

    cards = []
    p = packets["e06"]
    replay = p["evidence"]["controller:replay"]
    evidence = excerpt("Exact reusable-workflow criterion", criterion(p, "reusable_workflow"))
    evidence += excerpt("Trusted offline replay", json.dumps({"state": replay["state"], "exit_code": replay["exit_code"],
                         "infrastructure_unavailable": replay["infrastructure_unavailable"],
                         "last_error": replay["stderr"].splitlines()[-1]}, indent=2))
    evidence += old_reviewers("e06", "reusable_workflow")
    evidence += link("var/calibration/judge-expanded/e06/packet.json", "Full original WVG evidence packet")
    cards.append(card(1, "replay-credit", "Completion versus useful progress", "Working mathematics, broken replay",
        '<p>The WVG agent produced correct scientific arrays and genuine recomputation code. Its declared command ignores the output argument and fails with a permission error in the clean runtime. Two reviewers gave workflow ratings of <strong>1 versus 0</strong>.</p>'
        '<p>The controller already fails the required workflow outcome in either case. The decision is how much useful implementation progress to report alongside that failure.</p>',
        "How should we report this?",
        [("separate-progress", "Fail reusable workflow; show useful method progress separately."),
         ("partial-workflow", "Keep partial workflow credit, with completion blocked by replay."),
         ("discuss", "Needs discussion / another rule.")], evidence,
        "Keep successful science visible, but reserve reusable-workflow success for a command that actually works."))

    p = packets["e05"]
    source = p["evidence"]["file:documentation.py"]["text"]
    start = source.index("def uncertainty(")
    end = source.index("\n\ndef plot(", start)
    evidence = excerpt("Exact scientific-interpretation criterion", criterion(p, "scientific_interpretation"))
    evidence += excerpt("Visible in the original packet: complete uncertainty function", source[start:end])
    evidence += old_reviewers("e05", "scientific_interpretation")
    evidence += link("var/calibration/judge-expanded/e05/packet.json", "Original short-rains packet")
    cards.append(card(2, "visible-evidence", "Evidence quality", "A partial file can contain the whole relevant method",
        '<p>Short-rains interpretation received <strong>1 versus 2</strong>. Reviewer A said the uncertainty implementation was missing. The original packet actually includes the complete paired bootstrap function, with block lengths 2, 3 and 5, inside a partially included file.</p>'
        '<p>Other evidence really was omitted. The question is how to credit visible method evidence without overlooking those remaining gaps.</p>',
        "Which evidence rule should guide the judge?",
        [("relevant-sections", "Use visible relevant sections; identify each remaining gap specifically."),
         ("complete-files", "Require complete method files before full interpretation credit."),
         ("discuss", "Needs discussion / another rule.")], evidence,
        "Judge the relevant passages. A truncation flag does not make a visible implementation disappear; genuinely missing evidence should constrain only the claims it supports."))

    p = packets["e04"]
    checks = p["evidence"]["controller:static"]["check_results"]
    evidence = excerpt("Controller facts", json.dumps({name: checks[name] for name in
                       ("aggregation", "development_schema", "provenance_fields", "execution_schema")}, indent=2))
    evidence += excerpt("Exact data-preparation criterion", criterion(p, "data_preparation"))
    evidence += old_reviewers("e04", "data_preparation")
    evidence += link("var/calibration/judge-expanded/e04/packet.json", "Full seasonal evidence packet")
    cards.append(card(3, "packaging", "Criterion design", "When should missing delivery evidence reduce science credit?",
        '<p>Seasonal acquisition, aggregation and held-out predictions have correct components, while report/provenance/execution records are incomplete. Both reviewers reduced several scientific ratings because those records were missing.</p>'
        '<p>A missing record can matter scientifically: for example, an undocumented transformation may be unauditable. But applying the same packaging deduction to every criterion can obscure which scientific work succeeded.</p>',
        "Where should these deductions go?",
        [("criterion-specific", "Deduct for specific unsupported scientific claims; keep shared validity requirements separate."),
         ("all-dependent", "Incomplete provenance should reduce every scientific outcome that depends on it."),
         ("discuss", "Needs discussion / another rule.")], evidence,
        "Keep delivery gates, then explain criterion by criterion what missing evidence actually prevents us from establishing."))

    prediction = monthly["static"]["array_diagnostics"]["files"]["forecast.nc"]["fields"]["prediction"]
    evidence = excerpt("New ungraded diagnostic: production prediction", json.dumps({"units": prediction["units"],
                      "dimensions_agree": prediction["dimensions_agree"], "shape_agrees": prediction["shape_agrees"],
                      "numeric": {k: prediction["numeric"][k] for k in ("pairing", "finite_paired_count", "max_abs_error", "rmse")}}, indent=2))
    evidence += excerpt("Current nested-selection rubric", read("tasks/monthly-cycle-calibration/rubric.yaml"))
    evidence += '<p>The separate full-file audit identifies the error in the constant-slope comparator; the diagnostic above reports the maximum across the complete prediction field. It adds evidence and does not change a grade.</p>'
    evidence += link("var/calibration/overnight-final-task-audit.md", "Detailed monthly/downscaling code audit")
    cards.append(card(4, "monthly-outcomes", "Outcome granularity", "Correct nested selection, wrong production forecast",
        '<p>The monthly agent correctly fits outer folds, computes all six candidate losses and selects the nested parameter. Its production constant-slope comparator is wrong by up to <strong>34.9691 mm</strong>. Missing units originally hid that value error; late code edits also broke replay.</p>'
        '<p>The current selection outcome bundles nested selection, outer predictions and production predictions. One production failure therefore zeros the whole outcome, despite correct selection mathematics.</p>',
        "Should the next rubric split these outcomes?",
        [("split", "Separate fitting/selection, production correctness and replay outcomes."),
         ("combined", "Keep the combined outcome; successful components belong in diagnostics."),
         ("discuss", "Needs discussion / another rule.")], evidence,
        "Split scientifically distinct outcomes in the next task version, while still requiring all essential outcomes for completion."))

    p = packets["e07"]
    evidence = excerpt("Exact scientific-report criterion", criterion(p, "scientific_report"))
    evidence += excerpt("Original report", p["evidence"]["file:report.txt"]["text"])
    evidence += figure("var/calibration/judge-expanded/e07/figure.png", "Original submitted ACMAD figure. Reviewers observed probability and sensitivity panels, but no component-support panel.")
    evidence += old_reviewers("e07", "scientific_report")
    cards.append(card(5, "visual-support", "Scientific communication", "The report claims a panel the figure does not show",
        '<p>The probability-combination arrays and replay pass. The report says its figure includes a component-support panel. Both reviewers found that panel absent and gave the report <strong>1 / 2</strong>.</p>'
        '<p>Only 2 of 3,340 supported cells have all three components; 3,010 have one. Showing support could materially change how a forecaster interprets the map.</p>',
        "Is this a consequential reporting failure?",
        [("partial", "Yes — partial interpretation credit until support is communicated accurately."),
         ("minor", "Minor presentation issue; the report otherwise satisfies this criterion."),
         ("discuss", "Needs discussion / another rule.")], evidence,
        "Keep numerical success, and require the report and figure to communicate the evidence supporting each forecast."))

    pair = next(row for row in comparisons["comparisons"] if row["case"] == "c02" and row["criterion"] == "admissible_experiment")
    evidence = excerpt("Exact admissibility criterion", criterion(newer, "admissible_experiment"))
    evidence += excerpt("Trusted feedback ledger visible to both reviewers", json.dumps(newer["evidence"]["controller:feedback"], indent=2))
    evidence += reviewers([("Reviewer A", pair["a"]), ("Reviewer B", pair["b"])])
    evidence += '<h4>Later audit, outside the original reviewer packet</h4><p>The full trace shows the initial cross-validation code. Its reported RMSE omits division by the sum of spatial weights. That is a real metric-reporting error; the factor is constant across candidates and does not change their ordering. The original reviewers had only partial evidence of that calculation.</p>'
    evidence += link("var/calibration/judge-new-parent-review/comparison.json", "Original paired reviews") + ' · ' + link("var/calibration/overnight-solver-audit.md", "Full-trace scientific audit")
    cards.append(card(6, "optimization-admissibility", "Experiment auditability", "How much evidence establishes admissible optimization?",
        '<p>The subseasonal agent fits only training labels, uses one allowed development query and saves a working inference model. Reviewer A gives admissibility <strong>1</strong>; reviewer B gives <strong>2</strong>. The pre-query tuning command is omitted from their bounded trace, though its output and a later validation command are visible.</p>'
        '<p>Both reviewers flag unexplained validation scores. The full-log audit later finds the weight-normalization error, while confirming that candidate selection is unchanged.</p>',
        "How should we grade the original evidence boundary?",
        [("partial", "Partial admissibility: final fitting is safe, but the selection procedure is incompletely auditable."),
         ("full", "Full admissibility from code and trusted ledger; score the metric error under interpretation."),
         ("unresolved", "Leave admissibility unresolved until the original validation calculation is available."),
         ("discuss", "Needs discussion / another rule.")], evidence,
        "Separate information-boundary validity, auditability and metric correctness. Avoid treating uncertain history as either proven leakage or proven clean selection."))

    task_rows = []
    for path in sorted((ROOT / "tasks").glob("*/task.yaml")):
        import yaml
        spec = yaml.safe_load(path.read_text())
        task_rows.append(f'<tr><td>{link(str(path.parent.relative_to(ROOT) / "review.html"), spec["title"])}</td><td>{esc(spec["version"])}</td><td>Development · scientific review pending</td></tr>')
    read("archive/docs-2026-10/scripts/build_review_page.py")
    template = read("archive/docs-2026-10/scripts/review_page.html")
    manifest = {"schema_version": 1, "review_type": "development_evaluation_design", "sources": SOURCES,
                "experiment_policy_fingerprint": audit["policy_fingerprint"], "decisions": ["replay-credit", "visible-evidence", "packaging", "monthly-outcomes", "visual-support", "optimization-admissibility"]}
    identity = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    manifest["review_bundle_sha256"] = identity
    manifest_json = json.dumps(manifest, ensure_ascii=False).replace("<", "\\u003c")
    substitutions = {
        "@@CARDS@@": "\n".join(cards), "@@TASK_ROWS@@": "\n".join(task_rows),
        "@@MANIFEST@@": manifest_json, "@@BUNDLE@@": identity[:12],
        "@@REPORT_LINK@@": link("docs/overnight-development.md", "Full development audit"),
        "@@CHALLENGE_LINK@@": link("docs/frontier-challenge-next.md", "Stronger subseasonal challenge brief"),
        "@@TASK_INDEX_LINK@@": link("tasks/index.html", "All task review pages"),
    }
    for key, value in substitutions.items():
        template = template.replace(key, value)
    assert "@@" not in template
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(template)
    print(json.dumps({"html": str(OUTPUT), "bytes": OUTPUT.stat().st_size, "decision_count": 6,
                      "source_files": len(SOURCES), "review_bundle_sha256": identity}))


if __name__ == "__main__":
    build()
