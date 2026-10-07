"""Build standalone, offline review pages from the tracked task packages."""
import hashlib
import html
import json
import re
from pathlib import Path

import yaml

from .prepare import PACKAGES, ROOT, TASKS, digest

ASSETS = Path(__file__).with_name("review_ui")
SUMMARIES = {
    "seasonal-calibration": (
        "01", "Seasonal calibration", "Existing forecasting workflow",
        "Acquire the rainfall inputs, build and validate a calibration without leaking training years, and retain a workflow that can predict from a frozen fit.",
        "The prediction years have already been inspected. This is a development task; their scores cannot establish untouched forecast skill.",
    ),
    "acmad-objective": (
        "02", "ACMAD objective", "Centre replication",
        "Combine three real probability products, account for missing component support, and audit how a different weighting changes the outlook.",
        "This reproduces the final consolidation step. It does not refit the components or verify an issued forecast against observations.",
    ),
    "wvg-definition-audit": (
        "03", "WVG definition audit", "Literature method audit",
        "Compare a paper’s predictor geometry with an existing implementation, recompute both indices, and explain what the differences mean.",
        "The reference isolates geometry under explicit curator choices. Matching it does not reproduce the paper’s full index or forecast-skill result.",
    ),
    "short-rains-workflow": (
        "04", "Short-rains workflow", "Forecast method adaptation",
        "Repair a real rainfall-unit convention, implement issue-time-safe nested selection, and retain calibrated forecasts with independent test targets.",
        "Predictive skill is an observed outcome. Passing requires scientific processing, leakage checks, inference from saved state, and honest interpretation.",
    ),
    "weatherbench-verification": (
        "05", "WeatherBench verification", "Benchmark verification and diagnosis",
        "Reproduce forecast metrics on common valid-time support and diagnose three consequential comparison mistakes.",
        "The real public forecast subset and curator-created availability faults test verification; they do not reproduce annual published rankings.",
    ),
    "subseasonal-optimization": (
        "06", "Subseasonal optimization", "Forecast optimization",
        "Improve weeks 3–4 precipitation forecasts using training data and at most five aggregate development scores, then freeze predictions for a private final period.",
        "Regional cosine-weighted RMSE is a curator adaptation of SubseasonalClimateUSA. Scientific completion and numerical performance are reported separately.",
    ),
    "cca-seasonal-reproduction": (
        "07", "Seasonal CCA reproduction", "Multivariate method adaptation",
        "Build training-only EOF/CCA forecasts, nested mode selection and probabilistic calibration with saved-state inference.",
        "The explicit method contract adapts source code to East African rainfall. It does not reproduce an entire CPT binary or a paper's published numerical scores.",
    ),
    "station-verification": (
        "08", "Station verification", "Observation and verification audit",
        "Parse actual East African station observations, match UTC valid times and quality flags, and compare gridded forecast interpolation on common station support.",
        "Real NOAA observations and WeatherBench forecasts support a WeatherReal-inspired adaptation; neither sparse coverage nor constructed method availability establishes a published ranking.",
    ),
    "monthly-cycle-calibration": (
        "09", "Monthly cyclic calibration", "Seasonal statistical sharing",
        "Fit cyclic monthly regression slopes with whole-year nested validation, quantify whether smoothing helps, and retain inference from saved state.",
        "Real lagged SST and rainfall support a statistical method adaptation; negative linear predictions and negative comparisons require honest interpretation.",
    ),
    "conservative-downscaling": (
        "10", "Conservative downscaling", "Forecast calibration and spatial support",
        "Diagnose uncertain raw forecast units, calibrate ranks to observed totals, and reconstruct nonnegative fine-scale rainfall that conserves mapped coarse-cell volume.",
        "The raw physical scale remains unresolved. Conservation applies to calibrated millimetres; this does not reproduce the original BCSD hydrological experiment.",
    ),
}


def esc(value):
    return html.escape(str(value), quote=True)


def inline(text):
    """Render the small inline Markdown vocabulary used by these packets safely."""
    # Tokenize before escaping so code and links are not parsed a second time.
    tokens = re.split(r"(`[^`]+`|\[[^\]]+\]\([^)]+\)|\*\*[^*]+\*\*)", text)
    out = []
    for token in tokens:
        if token.startswith("`") and token.endswith("`"):
            out.append(f"<code>{esc(token[1:-1])}</code>")
        elif match := re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", token):
            label, href = match.groups()
            external = href.startswith(("https://", "http://"))
            relative = not re.match(r"^(?:[a-z][a-z0-9+.-]*:|//)", href, re.I)
            if external or relative:
                out.append(f'<a href="{esc(href)}">{esc(label)}</a>')
            else:
                out.append(esc(label))
        elif token.startswith("**") and token.endswith("**"):
            out.append(f"<strong>{esc(token[2:-2])}</strong>")
        else:
            out.append(esc(token))
    return "".join(out)


def markdown(text, omit_title=False):
    """Offline renderer for paragraphs, headings, lists, code and pipe tables."""
    lines = text.splitlines()
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("```"):
            block = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            out.append("<pre><code>" + esc("\n".join(block)) + "</code></pre>")
            i += 1
        elif match := re.match(r"^(#{1,6}) (.*)", line):
            level = min(len(match[1]) + 1, 6)
            if not (omit_title and len(match[1]) == 1):
                out.append(f"<h{level}>{inline(match[2])}</h{level}>")
            i += 1
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = lines[i].strip().strip("|").split("|")
                if not all(re.fullmatch(r"\s*:?-+:?\s*", cell) for cell in cells):
                    rows.append(cells)
                i += 1
            table = []
            for index, row in enumerate(rows):
                tag = "th" if index == 0 else "td"
                table.append("<tr>" + "".join(f"<{tag}>{inline(cell.strip())}</{tag}>" for cell in row) + "</tr>")
            out.append('<div class="table-scroll"><table>' + "".join(table) + "</table></div>")
        elif re.match(r"^[-*] |^\d+\. ", line):
            ordered = bool(re.match(r"^\d+\. ", line))
            items = []
            pattern = r"^\d+\. " if ordered else r"^[-*] "
            while i < len(lines) and re.match(pattern, lines[i]):
                item = [re.sub(pattern, "", lines[i])]
                i += 1
                while i < len(lines) and lines[i].strip() and not re.match(r"^[-*] |^\d+\. |^#", lines[i]):
                    item.append(lines[i].strip())
                    i += 1
                items.append("<li>" + inline(" ".join(item)) + "</li>")
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
        else:
            para = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r"^#|^[-*] |^\d+\. |^```|^\|", lines[i]):
                para.append(lines[i])
                i += 1
            out.append("<p>" + inline(" ".join(para)) + "</p>")
    return "\n".join(out)


def display(value):
    if isinstance(value, dict):
        return '<dl class="record">' + "".join(f"<dt>{esc(k.replace('_', ' '))}</dt><dd>{display(v)}</dd>" for k, v in value.items()) + "</dl>"
    if isinstance(value, list):
        return "<ul>" + "".join(f"<li>{display(v)}</li>" for v in value) + "</ul>"
    if isinstance(value, str) and value.startswith(("https://", "http://")):
        return f'<a href="{esc(value)}" target="_blank" rel="noopener noreferrer">{esc(value)}</a>'
    if isinstance(value, str) and value.startswith(("../", "./")):
        return f'<a href="{esc(value)}">{esc(value)}</a>'
    return esc(value)


def note(field, label, placeholder):
    return f'<label class="note-label">{esc(label)}<textarea data-field="{esc(field)}" rows="3" placeholder="{esc(placeholder)}"></textarea></label>'


def rubric_html(node, share=1):
    if "children" in node:
        total = sum(child["weight"] for child in node["children"])
        children = "".join(rubric_html(child, share * child["weight"] / total) for child in node["children"])
        if node["id"] == "task_completion":
            return children
        return f'<details class="rubric-group" open><summary>{esc(node["id"].replace("_", " ").title())}<span>{share * 100:g}% of total</span></summary>{children}</details>'
    ident = node["id"]
    field = f"rubric.{ident}"
    required = "Required" if node.get("required") else "Optional"
    return f'''<article class="rubric-leaf" id="leaf-{esc(ident)}">
      <div class="leaf-meta"><code>{esc(ident)}</code><div><span class="chip">{esc(node['evaluator'])}</span><span class="chip">{required}</span><span class="share">{share * 100:.2f}%</span></div></div>
      <p>{esc(node['criterion'])}</p>
      <div class="evidence">Evidence: {esc(', '.join(node.get('evidence', [])))}</div>
      <details class="leaf-feedback"><summary>Critique this check <span class="note-dot" aria-label="Has critique" hidden>●</span></summary><div class="feedback-fields">
        <label>Criterion<select data-field="{field}.decision"><option value="">No opinion yet</option><option>Keep</option><option>Revise</option><option>Remove</option><option>Discuss</option></select></label>
        <label>Suggested sibling weight<input type="number" min="0" step="any" data-field="{field}.weight" placeholder="Current: {node['weight']}"></label>
        <label>Required status<select data-field="{field}.required"><option value="">Current: {required.lower()}</option><option>Required</option><option>Optional</option></select></label>
      </div>{note(field + '.comment', 'Reason / proposed wording', 'What would make this criterion clearer, fairer, or more verifiable?')}</details>
    </article>'''


def leaves(node):
    if "children" in node:
        return sum((leaves(child) for child in node["children"]), [])
    return [node]


def render():
    css = (ASSETS / "style.css").read_text()
    js = (ASSETS / "review.js").read_text()
    template = (ASSETS / "task.html").read_text()
    validation_path = ROOT / "var/validation/task-packages.json"
    validation = json.loads(validation_path.read_text()) if validation_path.exists() else {}
    cards, outputs = [], []
    for task in TASKS:
        folder = PACKAGES / task
        spec = yaml.safe_load((folder / "task.yaml").read_text())
        rubric = yaml.safe_load((folder / "rubric.yaml").read_text())
        sources = yaml.safe_load((folder / "sources.yaml").read_text())
        manifest = json.loads((folder / "input-manifest.json").read_text())
        number, short, category, summary, limitation = SUMMARIES[task]
        checks = leaves(rubric["tree"])
        hashes = {name: digest(folder / name) for name in ("task.yaml", "prompt.md", "rubric.yaml", "sources.yaml", "review.md", "input-manifest.json")}
        for name in spec["artifact_contracts"].values():
            hashes[name] = digest(folder / name)
        if "source_plan" in spec:
            hashes[spec["source_plan"]] = digest(folder / spec["source_plan"])
        fingerprint = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
        result = next((v for v in validation.get("packages", []) if v["task"] == task), None)
        current = bool(result and all(result.get(key) == hashes[name] for key, name in (("task_sha256", "task.yaml"), ("prompt_sha256", "prompt.md"), ("rubric_sha256", "rubric.yaml"))))
        proof = display(result["reference_validation"]) if current else '<p>No matching validation record. Run package validation to refresh this evidence.</p>'
        if spec["input_contract"]["mode"] == "agent_acquisition":
            proof += '<p>Acquisition runtime: pending preflight. The existing numerical fixtures validate processing; they do not establish successful agent retrieval or a working raw-response replay service.</p>'
        input_rows = []
        for entry in manifest["files"]:
            visibility = "Agent input" if entry["visibility"] == "agent" else "Controller only"
            if spec["input_contract"]["mode"] == "agent_acquisition" and entry["visibility"] == "agent":
                visibility = "Controller development fixture"
            metadata = {k: v for k, v in entry.items() if k not in ("file", "visibility", "bytes")}
            input_rows.append(f'<tr><td><details><summary><code>{esc(entry["file"])}</code></summary>{display(metadata)}</details></td><td>{visibility}</td><td>{entry["bytes"] / 1024:,.1f} KB</td></tr>')
        payload = {"task": task, "version": spec["version"], "title": spec["title"], "source_hashes": hashes,
                   "fingerprint": fingerprint, "leaves": [{"id": c["id"], "criterion": c["criterion"]} for c in checks]}
        data = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
        replacements = {
            "TITLE": esc(spec["title"]), "SHORT": esc(short), "NUMBER": number,
            "CATEGORY": esc(category), "SUMMARY": esc(summary), "LIMITATION": esc(limitation),
            "VERSION": esc(spec["version"]), "CHECK_COUNT": str(len(checks)),
            "PROMPT": markdown((folder / "prompt.md").read_text(), omit_title=True),
            "REVIEW": markdown((folder / "review.md").read_text(), omit_title=True),
            "EVALUATION": display(spec["evaluation"]), "OUTPUTS": "".join(f"<code>{esc(o)}</code>" for o in spec["outputs"]),
            "RUBRIC": rubric_html(rubric["tree"]), "COMPLETION": esc(rubric["completion"]),
            "SOURCES": display(sources), "INPUT_ROWS": "".join(input_rows), "VALIDATION": proof,
            "SPEC": display(spec), "DATA": data, "CSS": css, "JS": js,
            "INPUT_CONTRACT": display(spec["input_contract"]),
            "BASIC_VALIDITY": display(rubric["basic_validity"]),
            "PROMPT_NOTE": note("prompt", "Prompt critique", "Ambiguities, missing instructions, or changes to the scientific scope…"),
            "SCORING_NOTE": note("scoring", "Scoring critique", "Are the group weights, gates, and evidence requirements appropriate?"),
            "SOURCES_NOTE": note("sources", "Sources and inputs critique", "Provenance, frozen data, access, or redistribution questions…"),
            "DESIGN_NOTE": note("design", "Task design critique", "Is the task interesting and useful? What should change before a run?"),
        }
        # One substitution pass: source text must never be interpreted as template markup.
        page = re.sub(r"@@([A-Z_]+)@@", lambda m: replacements[m[1]], template)
        destination = folder / "review.html"
        destination.write_text(page)
        outputs.append(str(destination.relative_to(ROOT)))
        cards.append(f'<a class="task-card" href="{task}/review.html"><span class="eyebrow">{number} / {esc(category)}</span><h2>{esc(short)}</h2><p>{esc(summary)}</p><div class="card-foot"><span>{len(checks)} rubric checks</span><span>Inspect & critique ↗</span></div></a>')
    index = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Task reviews · Agent Weather Bench</title><style>{css}</style></head><body class="index-page"><main class="index-wrap"><div class="brand"><span class="brand-mark">≈</span> Agent Weather Bench <span class="brand-muted">/ task review</span></div><div class="index-hero"><span class="eyebrow">{len(TASKS)} drafts for joint review</span><h1>What makes a good<br>weather research task?</h1><p class="lede">Inspect the scientific contract, challenge the scoring, and leave concrete changes. These packages are development tasks for the benchmark.</p><span class="status">Scientific review pending · See the run report for development attempts</span></div><div class="task-cards">{''.join(cards)}</div><section class="index-note"><h2>A shared task pool, rather than a prescribed chain</h2><p>The primary accretion experiment runs different orders of standalone tasks with retained and reset substrates. Explicit related follow-ups remain an optional complementary experiment.</p><p>Each page works offline. Notes are saved in this browser when storage is available; export Markdown or JSON to share or preserve a critique. Notes do not modify task files or approve a benchmark run.</p><div class="source-links"><a href="../docs/task-package-review.md">Review guide ↗</a><a href="../experiments/accretion-review.yaml">Accretion design ↗</a><a href="README.md">Package documentation ↗</a></div></section></main></body></html>'''
    (PACKAGES / "index.html").write_text(index)
    outputs.append("tasks/index.html")
    return {"rendered": outputs, "model_calls": 0}
