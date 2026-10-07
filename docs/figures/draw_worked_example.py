"""Draw docs/figures/worked-example.svg from one seasonal calibration run.

Run from the repository root: .venv/bin/python docs/figures/draw_worked_example.py
The run is found by the suffix of its id; change RUN to draw another.
"""
import json
from pathlib import Path
import numpy as np, xarray as xr
import warnings; warnings.simplefilter("ignore")

RUN = "50c036"
f = next(p for p in Path("var/template-runs").iterdir() if RUN in p.name)
ds = xr.open_zarr(f / "frozen/results.zarr", chunks=None).load()
meta = json.load(open(f / "run.json")); asm = json.load(open(f / "assessment.json"))
secs, tok = round(meta["seconds"]), meta["usage"]["total_tokens"]
obs = ds.observed_total_mm.transpose("year", "latitude", "longitude").values.mean(axis=0)
fmean = ds.forecast_mean_mm.transpose("year", "latitude", "longitude").values
above = ds.forecast_probability.transpose("new_year", "category", "latitude", "longitude").values[0, 2]
rpss = float(ds.hindcast_rpss.values) if "hindcast_rpss" in ds else json.load(open(f / "frozen/answer.json"))["results"]["hindcast_rpss"]
xs = fmean[:, 2, 1]; ys = ds.observed_total_mm.transpose("year", "latitude", "longitude").values[:, 2, 1]
checks = sum(1 for c in asm["checks"].values()); passed = sum(c["state"] == "pass" for c in asm["checks"].values())

BLUE, GREEN, ORANGE, SLATE, RED = "#2563eb", "#15803d", "#c2410c", "#1f2937", "#b91c1c"
def hexmix(a, b, t):
    a, b = [int(a[i:i+2], 16) for i in (1, 3, 5)], [int(b[i:i+2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))
def text(x, y, s, size=13, fill="#111", weight="normal", anchor="start", family="Helvetica, Arial, sans-serif"):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" text-anchor="{anchor}" font-family="{family}">{s}</text>'
def mono(x, y, s, size=11, fill="#111"): return text(x, y, s, size, fill, family="Menlo, Consolas, monospace")
def grid(x, y, w, values, color):
    rows, cols = values.shape; cw = w / cols
    return "\n".join(f'<rect x="{x + j * cw:.1f}" y="{y + i * cw:.1f}" width="{cw:.1f}" height="{cw:.1f}" fill="{color(values[i, j])}" stroke="#fff"/>' for i in range(rows) for j in range(cols)), cw * cols, cw * rows
def badge(x, y, label, color, w=52):
    return f'<rect x="{x}" y="{y - 13}" width="{w}" height="18" rx="9" fill="{color}"/>' + text(x + w / 2, y, label, 11, "#fff", "bold", "middle")
def arrow(x1, y1, x2, y2): return f'<path d="M {x1} {y1} L {x2} {y2}" stroke="#333" stroke-width="2" fill="none" marker-end="url(#arrow)"/>'
def card(x, y, w, h, color, fill="#fff"): return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{color}" stroke-width="1.8"/>'

W, H = 1440, 780
s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Helvetica, Arial, sans-serif">',
     '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#333"/></marker></defs>',
     f'<rect width="{W}" height="{H}" fill="#fff"/>',
     text(W / 2, 32, "An agent drives a seasonal-forecast workflow, and the benchmark checks every step", 22, "#111", "bold", "middle"),
     text(W / 2, 56, f"A real run: gpt-6-luna, seasonal rainfall calibration to the WMO guidance, a box in Kenya, trained on 1993–2004, outlook for 2005–2006. {secs} s, {tok:,} tokens.", 13, "#555", anchor="middle")]

# ---- band labels -----------------------------------------------------------------------------
s.append(f'<rect x="24" y="78" width="26" height="250" rx="6" fill="{GREEN}"/>')
s.append(f'<text transform="translate(42 203) rotate(-90)" text-anchor="middle" font-size="14" font-weight="bold" fill="#fff">THE AGENT</text>')
s.append(f'<rect x="24" y="340" width="26" height="150" rx="6" fill="{ORANGE}"/>')
s.append(f'<text transform="translate(42 415) rotate(-90)" text-anchor="middle" font-size="14" font-weight="bold" fill="#fff">THE CHECKS</text>')

steps = ["1 Get the data", "2 Prepare", "3 Calibrate", "4 Cross-validate", "5 Verify", "6 Issue the outlook"]
cx, cw, gap = 64, 212, 14
X = [cx + k * (cw + gap) for k in range(6)]
for k, title in enumerate(steps):
    s.append(card(X[k], 78, cw, 250, GREEN, "#f0fdf4"))
    s.append(text(X[k] + 10, 100, title, 14, GREEN, "bold"))
    if k < 5: s.append(arrow(X[k] + cw, 200, X[k + 1], 200))

# 1 data
x = X[0]
for i in range(3):
    s.append(f'<rect x="{x + 18 + i * 6}" y="{118 + i * 6}" width="90" height="56" rx="4" fill="{hexmix("#dbeafe", "#1e40af", 0.25 + 0.2 * i)}" stroke="#fff"/>')
s.append(text(x + 18, 196, "ECMWF, 25 members", 10)); s.append(text(x + 18, 209, "monthly rates", 10, "#555"))
g, gw, gh = grid(x + 128, 118, 66, np.random.default_rng(1).uniform(0, 1, (6, 6)), lambda v: hexmix("#eff6ff", "#1e3a8a", v))
s.append(g); s.append(text(x + 128, 196, "CHIRPS obs", 10)); s.append(text(x + 128, 209, "0.05°, monthly", 10, "#555"))
s.append(text(x + 10, 240, "forecast-training.nc", 11, "#555", family="Menlo, monospace")); s.append(text(x + 10, 256, "observations-training.nc", 11, "#555", family="Menlo, monospace")); s.append(text(x + 10, 272, "forecast-new.nc", 11, "#555", family="Menlo, monospace"))
s.append(text(x + 10, 300, "Frozen, offline, hashed", 11, "#555"))
# 2 prepare
x = X[1]
g, gw, gh = grid(x + 20, 116, 84, obs, lambda v: hexmix("#eff6ff", "#1e3a8a", (v - obs.min()) / (obs.max() - obs.min() + 1e-9)))
s.append(g); s.append(text(x + 20 + gw / 2, 116 + gh + 16, "observed OND total, 1° grid", 11, anchor="middle"))
s.append(text(x + 120, 134, "rate × days", 11)); s.append(text(x + 120, 148, "in each month", 11)); s.append(text(x + 120, 170, "obs cells averaged", 11)); s.append(text(x + 120, 184, "into each 1° cell", 11))
s.append(text(x + 10, 272, "12 seasons × 12 cells", 11, "#555")); s.append(text(x + 10, 300, "Totals in mm, on the forecast grid", 11, "#555"))
# 3 calibrate: scatter of one cell
x = X[2]
ox, oy, ow, oh = x + 24, 116, 96, 110
s.append(f'<line x1="{ox}" y1="{oy + oh}" x2="{ox + ow}" y2="{oy + oh}" stroke="#333"/><line x1="{ox}" y1="{oy}" x2="{ox}" y2="{oy + oh}" stroke="#333"/>')
xn = (xs - xs.min()) / (xs.max() - xs.min()); yn = (ys - ys.min()) / (ys.max() - ys.min())
b, a = np.polyfit(xn, yn, 1)
for px, py in zip(xn, yn): s.append(f'<circle cx="{ox + px * ow:.1f}" cy="{oy + oh - py * oh:.1f}" r="3.5" fill="{GREEN}"/>')
s.append(f'<line x1="{ox}" y1="{oy + oh - a * oh:.1f}" x2="{ox + ow}" y2="{oy + oh - (a + b) * oh:.1f}" stroke="{ORANGE}" stroke-width="2"/>')
s.append(text(ox + ow / 2, oy + oh + 16, "model total →", 10, "#555", anchor="middle")); s.append(f'<text transform="translate({ox - 8} {oy + oh / 2}) rotate(-90)" text-anchor="middle" font-size="10" fill="#555">observed →</text>')
s.append(text(x + 132, 140, "per cell:", 11)); s.append(text(x + 132, 154, "obs = a + b·model", 11)); s.append(text(x + 132, 176, "Gaussian residual", 11)); s.append(text(x + 132, 190, "→ tercile", 11)); s.append(text(x + 132, 204, "probabilities", 11))
s.append(text(x + 10, 272, "one cell shown, 12 years", 11, "#555")); s.append(text(x + 10, 300, "Any sound calibration is acceptable", 11, "#555"))
# 4 cross-validate
x = X[3]
for i in range(12):
    col, row = i % 6, i // 6
    held = i == 4
    s.append(f'<rect x="{x + 16 + col * 30}" y="{120 + row * 30}" width="26" height="26" rx="4" fill="{RED if held else "#bbf7d0"}" stroke="#fff"/>')
    s.append(text(x + 29 + col * 30, 138 + row * 30, str(1993 + i)[2:], 10, "#fff" if held else "#14532d", anchor="middle"))
s.append(text(x + 10, 200, "Each year held out of the fit", 11)); s.append(text(x + 10, 214, "and of the tercile boundaries,", 11)); s.append(text(x + 10, 228, "then forecast", 11))
s.append(text(x + 10, 272, "12 hindcasts, one per year", 11, "#555")); s.append(text(x + 10, 300, "The WMO practice the task requires", 11, "#555"))
# 5 verify
x = X[4]
bx, by, bw = x + 16, 150, 180
s.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="18" rx="4" fill="#e5e7eb"/>')
s.append(f'<rect x="{bx + bw * 0.5}" y="{by}" width="{bw * 0.5 * rpss / 0.5:.1f}" height="18" rx="4" fill="{GREEN}"/>')
s.append(f'<line x1="{bx + bw * 0.5}" y1="{by - 6}" x2="{bx + bw * 0.5}" y2="{by + 24}" stroke="#333"/>')
s.append(text(bx + bw * 0.5, by - 10, "climatology = 0", 10, "#555", anchor="middle")); s.append(text(bx + bw, by + 38, "+0.5", 10, "#555", anchor="end")); s.append(text(bx, by + 38, "−0.5", 10, "#555"))
s.append(text(bx + bw * 0.5 + bw * 0.5 * rpss / 0.5 + 4, by + 13, f"RPSS {rpss:.2f}", 12, GREEN, "bold"))
s.append(text(x + 10, 214, "ranked probability skill of the 12", 11)); s.append(text(x + 10, 228, "hindcasts, pooled over cells, against", 11)); s.append(text(x + 10, 242, "a one-third-each forecast", 11))
s.append(text(x + 10, 300, "Reported with the outlook", 11, "#555"))
# 6 outlook
x = X[5]
g, gw, gh = grid(x + 16, 116, 84, above, lambda v: hexmix("#fff7ed", "#1d4ed8", min(1, max(0, (v - 0.2) / 0.4))))
s.append(g)
for i in range(above.shape[0]):
    for j in range(above.shape[1]):
        s.append(text(x + 16 + 28 * j + 14, 116 + 28 * i + 18, f"{above[i, j]:.0%}", 9, "#111" if above[i, j] < 0.4 else "#fff", anchor="middle"))
s.append(text(x + 16, 116 + gh + 16, "P(above normal), OND 2005", 10))
s.append(text(x + 112, 134, "three tercile", 11)); s.append(text(x + 112, 148, "probabilities", 11)); s.append(text(x + 112, 162, "per cell, per year", 11))
s.append(text(x + 10, 272, "“a 40% probability still means the", 11, "#555")); s.append(text(x + 10, 286, "other outcomes remain likely” — report", 11, "#555"))
s.append(text(x + 10, 304, "Uncertainty stated in plain language", 11, "#555"))

# ---- the checks band -------------------------------------------------------------------------
checks_text = [
    ["Inputs hashed; the whole", "tool trace is recorded.", "Rerun on changed data:", "the results follow the data."],
    ["Totals match the reference", "under the actual month", "lengths, not 30-day months", "or raw rates. Two readings of", "the obs weighting both accepted."],
    ["Judge reads the cited code:", "“lstsq(X, ytrain)” with a", "residual spread — does what", "the method entry says."],
    ["Probe: change one year's", "observation → that year's", "hindcast does not move.", "Categories match the", "leave-one-out boundaries."],
    ["RPSS recomputed from the", "submitted probabilities and", "categories: 0.269 ✓, within", "a float32 error bound."],
    ["Probabilities valid and sum", "to 1. Probe: change one new", "year's forecast → the other", "year's outlook is unchanged.", "Judge: plain language ✓."],
]
for k, lines in enumerate(checks_text):
    s.append(card(X[k], 340, cw, 150, ORANGE, "#fff7ed"))
    for i, line in enumerate(lines): s.append(text(X[k] + 10, 362 + 16 * i, line, 11))
    s.append(badge(X[k] + cw - 62, 480, "pass", GREEN))
    s.append(f'<line x1="{X[k] + cw / 2}" y1="328" x2="{X[k] + cw / 2}" y2="340" stroke="{ORANGE}" stroke-width="2" stroke-dasharray="3 2"/>')

# ---- bottom: delivery, checklist, result -----------------------------------------------------
y3 = 508
s.append(card(64, y3, 300, 150, GREEN, "#f0fdf4")); s.append(text(74, y3 + 22, "The agent delivered", 13, GREEN, "bold"))
for i, line in enumerate(["results.zarr  6 labelled arrays: totals,", "              categories, probabilities", "answer.json   RPSS, method pointers, run cmd",
                          "run.py        regenerates everything", "report.md     what, why, limits"]):
    s.append(mono(74, y3 + 46 + 18 * i, line, 10.5))
s.append(card(380, y3, 560, 150, ORANGE, "#fff7ed")); s.append(text(390, y3 + 22, "The WMO checklist, 11 steps, each from the most exact evidence", 13, ORANGE, "bold"))
names = [("reproducible", "probes"), ("model forecast prepared", "reference"), ("observations prepared", "reference"), ("cross-validated", "probe"), ("verification categories", "reference"), ("historical performance", "reference"),
         ("probabilistic format", "rule"), ("operational application", "probe"), ("documented calibration", "judge"), ("documented cross-validation", "judge"), ("plain-language uncertainty", "judge")]
for i, (n, ev) in enumerate(names):
    col, row = i % 2, i // 2
    xx, yy = 392 + col * 275, y3 + 46 + 17 * row
    s.append(f'<circle cx="{xx + 6}" cy="{yy - 4}" r="5" fill="{GREEN}"/>'); s.append(text(xx + 16, yy, n, 11)); s.append(text(xx + 200, yy, ev, 10, "#777"))
s.append(card(956, y3, 460, 150, SLATE, "#f3f4f6"))
s.append(f'<rect x="{970}" y="{y3 + 16}" width="130" height="44" rx="22" fill="{GREEN}"/>'); s.append(text(1035, y3 + 46, "PASS", 24, "#fff", "bold", "middle"))
s.append(text(1112, y3 + 32, f"{passed} of {checks} checks", 13, SLATE, "bold")); s.append(text(1112, y3 + 50, "the judge's 6 included", 11, "#555"))
s.append(text(970, y3 + 78, f"Recorded: {secs} s, {tok:,} tokens, model, harness, substrate,", 11)); s.append(text(970, y3 + 93, "input and artifact hashes, the tool trace, the judge id.", 11))
s.append(badge(970, y3 + 112, "fail", RED, 44)); s.append(text(1020, y3 + 112, "a named pitfall or defect", 11))
s.append(badge(1180, y3 + 112, "unresolved", "#6b7280", 78)); s.append(text(1264, y3 + 112, "an outside cause", 11))
s.append(text(970, y3 + 138, "The other attempt on this box that day failed: its boundaries included the held-out year.", 11, "#444"))

s.append(text(64, 700, "Same task, same data, same checks for every system. Change the model, the harness, the substrate or the supplied material, and compare pass rate, cost and time.", 12, "#444"))
s.append(text(64, 720, "A second episode hands this submission to the same system for another box, another season or the next task.", 12, "#444"))
s.append(text(64, 752, "Terms: a probe reruns the agent's code on changed data; a pitfall is a known wrong method with a computable wrong answer; the reference is controller code that computes the answer under every defensible reading of the brief.", 10.5, "#666"))
s.append("</svg>")
Path("docs/figures/worked-example.svg").write_text("\n".join(s))
print("ok", passed, checks, round(rpss, 3))
