"""Draw docs/figures/overview.svg: task, tooling and supplements go into a sandbox with the agent; the controller inspects the submission and trace.

Run from the repository root: .venv/bin/python docs/figures/draw_overview.py
"""
from pathlib import Path

BLUE, PURPLE, GREEN, ORANGE, SLATE, RED, GREY, INK = "#2563eb", "#6d28d9", "#15803d", "#c2410c", "#1f2937", "#b91c1c", "#6b7280", "#111"
W, H = 1440, 720
MONO = "Menlo, Consolas, monospace"

def text(x, y, s, size=13, fill=INK, weight="normal", anchor="start", family="Helvetica, Arial, sans-serif"):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" text-anchor="{anchor}" font-family="{family}">{s}</text>'
def box(x, y, w, h, color, fill="#fff", dash=None, r=10, width=2):
    extra = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{color}" stroke-width="{width}"{extra}/>'
def head(x, y, w, color, label):
    return f'<rect x="{x}" y="{y}" width="{w}" height="34" rx="10" fill="{color}"/><rect x="{x}" y="{y + 22}" width="{w}" height="12" fill="{color}"/>' + text(x + w / 2, y + 23, label, 16, "#fff", "bold", "middle")
def arrow(x1, y1, x2, y2, color="#333", width=2.5):
    return f'<path d="M {x1} {y1} L {x2} {y2}" stroke="{color}" stroke-width="{width}" fill="none" marker-end="url(#arrow)"/>'
def pill(x, y, w, label, color, size=12):
    return f'<rect x="{x}" y="{y - 13}" width="{w}" height="20" rx="10" fill="{color}"/>' + text(x + w / 2, y + 1, label, size, "#fff", "bold", "middle")
def example(x, y, label):
    """A labelled example in another font: what the element could be."""
    w = 7.2 * len(label) + 14
    return f'<rect x="{x}" y="{y - 12}" width="{w:.0f}" height="17" rx="8" fill="#f3f4f6" stroke="#9ca3af" stroke-width="0.8"/>' + text(x + 7, y, label, 10.5, "#374151", family=MONO)
def item(x, y, name, ex, size=12):
    return text(x, y, name, size) + example(x + 6.6 * len(name) + 8, y, ex)
def hexmix(a, b, t):
    a, b = [int(a[i:i+2], 16) for i in (1, 3, 5)], [int(b[i:i+2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(p + (q - p) * t) for p, q in zip(a, b))
def minimap(x, y, size, seed, cols=4, rows=3, a="#eff6ff", b="#1e3a8a"):
    import random
    rng = random.Random(seed); out = []; cw = size / cols
    for i in range(rows):
        for j in range(cols):
            out.append(f'<rect x="{x + j * cw:.1f}" y="{y + i * cw:.1f}" width="{cw:.1f}" height="{cw:.1f}" fill="{hexmix(a, b, rng.random())}" stroke="#fff"/>')
    return "\n".join(out)

s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Helvetica, Arial, sans-serif">',
     '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#333"/></marker>'
     '<marker id="oarrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#c2410c"/></marker></defs>',
     f'<rect width="{W}" height="{H}" fill="#fff"/>',
     text(W / 2, 32, "A task and its tooling go into a sandbox with an agent; the controller inspects what comes out", 21, INK, "bold", "middle")]

TOP = 62
# ---- inputs: task and tooling ---------------------------------------------------------------------
x, w = 30, 250
s.append(box(x, TOP, w, 160, BLUE, "#eff6ff")); s.append(head(x, TOP, w, BLUE, "The task"))
s.append(text(x + 12, TOP + 54, "A forecaster's job, stated as a product.", 10.5, GREY)); s.append(text(x + 12, TOP + 68, "The method is not stated.", 10.5, GREY))
s.append(item(x + 12, TOP + 92, "brief", "seasonal outlook, Kenya"))
s.append(item(x + 12, TOP + 116, "data", "ECMWF members + CHIRPS"))
s.append(item(x + 12, TOP + 140, "budget", "20 min, offline"))
s.append(box(x, TOP + 176, w, 164, PURPLE, "#f5f3ff")); s.append(head(x, TOP + 176, w, PURPLE, "Tooling and supplements"))
s.append(item(x + 12, TOP + 230, "skills", "Rhiza weather-skills"))
s.append(item(x + 12, TOP + 254, "libraries", "AfricaS2S, acmadDL"))
s.append(item(x + 12, TOP + 278, "earlier work", "episode 1 output"))
s.append(item(x + 12, TOP + 302, "supplement", "conventions.md"))
s.append(text(x + 12, TOP + 330, "Each can be present or absent in a run.", 10.5, GREY))

# ---- sandbox --------------------------------------------------------------------------------------------
x, w = 320, 290
s.append(box(x, TOP, w, 340, GREEN, "#f0fdf4", dash="8 5")); s.append(head(x, TOP, w, GREEN, "The sandbox"))
s.append(text(x + 12, TOP + 56, "No network. Task, tooling and supplements are mounted.", 10.5, GREY))
s.append(box(x + 14, TOP + 70, w - 28, 120, GREEN)); s.append(text(x + w / 2, TOP + 92, "The agent", 14, GREEN, "bold", "middle"))
s.append(item(x + 26, TOP + 118, "model", "gpt-6-luna"))
s.append(item(x + 26, TOP + 142, "harness", "Codex"))
s.append(text(x + 26, TOP + 170, "reads, writes code, runs it, writes up", 12))
s.append(arrow(x + w / 2, TOP + 190, x + w / 2, TOP + 216, GREEN, 2))
s.append(text(x + w / 2, TOP + 236, "produces, by any method", 12, GREEN, "bold", "middle"))
s.append(text(x + 12, TOP + 262, "a submission and a trace", 13, INK, "bold"))
s.append(text(x + 12, TOP + 282, "The submission is a fixed envelope: arrays,", 12)); s.append(text(x + 12, TOP + 300, "numbers, code and a report. The trace is", 12)); s.append(text(x + 12, TOP + 318, "every command and tool call, kept by the controller.", 12))

# ---- what comes out ---------------------------------------------------------------------------------------
x, w = 640, 200
s.append(box(x, TOP, w, 340, SLATE, "#fafafa", r=10, width=1.5)); s.append(head(x, TOP, w, SLATE, "What comes out"))
parts = [("results.zarr", "labelled arrays", 56), ("answer.json", "numbers, claims, run command", 112), ("code", "regenerates the results", 168), ("report.md", "what, why, limits", 224), ("trace", "commands, tool calls, cost, time", 280)]
PY = {}
for name, what, dy in parts:
    yy = TOP + dy
    s.append(box(x + 10, yy - 2, w - 20, 44, "#d1d5db", "#fff", r=6, width=1))
    s.append(text(x + 18, yy + 16, name, 12, INK, "bold", family=MONO)); s.append(text(x + 18, yy + 32, what, 10.5, GREY))
    PY[name] = yy + 20
s.append(minimap(x + w - 48, TOP + 60, 34, 7, 3, 3))

# ---- controller -------------------------------------------------------------------------------------------
x, w = 870, 340
s.append(box(x, TOP, w, 340, ORANGE, "#fff7ed")); s.append(head(x, TOP, w, ORANGE, "The controller inspects it"))
rows = [("Compute", ["a private reference under every defensible", "reading of the brief; a known wrong reading", "is named as a pitfall; skill against withheld", "observations"], ["results.zarr", "answer.json"]),
        ("Rerun", ["the agent's own code on changed data: the", "results must follow the data and must not use", "a held-out year or a forecast from the future"], ["code"]),
        ("Judge", ["Claude Opus 5.5, one narrow question at a time,", "on exact quotations: does the report say what", "the code and numbers say, in plain language?"], ["report.md", "answer.json"]),
        ("Record", ["which tooling was used, cost, tokens, time"], ["trace"])]
yy = TOP + 60
for name, lines, targets in rows:
    s.append(pill(x + 12, yy + 2, 64, name, ORANGE, 12))
    for i, line in enumerate(lines): s.append(text(x + 86, yy + i * 15, line, 11.5))
    for t in targets:
        s.append(f'<path d="M {x} {yy - 2} C {x - 14} {yy - 2}, {x - 14} {PY[t]}, {840} {PY[t]}" stroke="{ORANGE}" stroke-width="1.4" fill="none" marker-end="url(#oarrow)"/>')
    yy += 15 * len(lines) + 24
s.append(text(x + 12, TOP + 312, "No human per run. A scientist certifies each task's", 10.5, GREY)); s.append(text(x + 12, TOP + 326, "reference and pitfalls once.", 10.5, GREY))

# ---- result --------------------------------------------------------------------------------------------------
x, w = 1240, 175
s.append(box(x, TOP, w, 340, SLATE, "#f3f4f6")); s.append(head(x, TOP, w, SLATE, "The result"))
s.append(pill(x + 14, TOP + 70, 56, "pass", GREEN)); s.append(text(x + 78, TOP + 74, "right, every check", 11.5))
s.append(pill(x + 14, TOP + 102, 56, "fail", RED)); s.append(text(x + 78, TOP + 98, "at fault; the", 11.5)); s.append(text(x + 78, TOP + 114, "pitfall named", 11.5))
s.append(pill(x + 14, TOP + 142, 86, "unresolved", GREY)); s.append(text(x + 14, TOP + 166, "an outside cause; never a fail", 11.5))
s.append(text(x + 14, TOP + 200, "+ skill score", 11.5)); s.append(text(x + 14, TOP + 218, "+ cost, tokens, time", 11.5)); s.append(text(x + 14, TOP + 236, "+ tooling used", 11.5)); s.append(text(x + 14, TOP + 254, "+ every quote and rerun", 11.5))
s.append(text(x + 14, TOP + 290, "Same checks for every", 11.5)); s.append(text(x + 14, TOP + 306, "system and tooling.", 11.5))

# arrows between columns
s.append(arrow(280, TOP + 100, 320, TOP + 100)); s.append(arrow(280, TOP + 258, 320, TOP + 258))
s.append(arrow(610, TOP + 170, 640, TOP + 170)); s.append(arrow(1210, TOP + 170, 1240, TOP + 170))

# ---- how it scales, in black -----------------------------------------------------------------------------------
y = 430
s.append(text(30, y + 20, "How it scales", 18, INK, "bold"))
x = 30
s.append(text(x, y + 50, "Tasks × instances", 13, INK, "bold"))
for i in range(4):
    for j in range(6):
        s.append(f'<rect x="{x + j * 30}" y="{y + 62 + i * 24}" width="26" height="20" rx="3" fill="{hexmix("#e5e7eb", "#374151", (i * 6 + j) / 23)}"/>')
s.append(text(x, y + 176, "25 templates ↓  ×  regions and windows →", 11))
x = 320
s.append(text(x, y + 50, "Systems × tooling and supplements", 13, INK, "bold"))
for j, c in enumerate(["none", "skills", "libraries", "supplement"]): s.append(text(x + 110 + j * 58, y + 68, c, 10, GREY, anchor="middle"))
for i, r in enumerate(["cheap model", "frontier model", "harness A", "harness B"]):
    s.append(text(x, y + 88 + i * 24, r, 11))
    for j in range(4):
        s.append(f'<rect x="{x + 82 + j * 58}" y="{y + 74 + i * 24}" width="54" height="20" rx="3" fill="{hexmix("#e5e7eb", "#374151", ((i * 4 + j) * 7 % 11) / 10)}"/>')
s.append(text(x, y + 176, "Each cell: pass rate, cost, time. Change one thing at a time.", 11))
x = 680
s.append(text(x, y + 50, "Episodes", 13, INK, "bold"))
for k, label in enumerate(["Ethiopia", "Kenya", "Nigeria"]):
    bx = x + k * 120
    s.append(box(bx, y + 62, 96, 44, "#374151", "#f9fafb", r=6, width=1.5)); s.append(text(bx + 48, y + 80, label, 12, anchor="middle")); s.append(text(bx + 48, y + 97, f"episode {k + 1}", 10, GREY, anchor="middle"))
    if k < 2: s.append(arrow(bx + 96, y + 84, bx + 120, y + 84, "#374151", 2))
s.append(text(x, y + 130, "The agent keeps its earlier work.", 11)); s.append(text(x, y + 148, "Compare with a fresh run: does work", 11)); s.append(text(x, y + 166, "accumulate, and what does it save?", 11))
x = 1060
s.append(text(x, y + 50, "Leaderboard", 13, INK, "bold"))
for i, (name, v) in enumerate([("system C", 0.9), ("system A", 0.7), ("system B", 0.55), ("climatology", 0.4)]):
    s.append(text(x, y + 78 + i * 22, name, 11)); s.append(f'<rect x="{x + 80}" y="{y + 66 + i * 22}" width="{v * 200:.0f}" height="16" rx="3" fill="{"#374151" if name != "climatology" else "#9ca3af"}"/>')
s.append(text(x, y + 176, "Forecast tasks also take an optimised", 11)); s.append(text(x, y + 194, "submission, scored on withheld observations.", 11))
s.append(text(30, 686, "With which model, harness and tooling can a forecaster's task be handed to an agent system and come back right? Per task, per system and per tooling, with the same checks each time.", 12, "#444"))
s.append("</svg>")
Path(__file__).with_name("overview.svg").write_text("\n".join(s))
print("ok")
