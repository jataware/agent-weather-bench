"""Draw docs/figures/overview.svg: the system in a sandbox, the controller that checks its delivery, and how that scales.

Run from the repository root: .venv/bin/python docs/figures/draw_overview.py
"""
from pathlib import Path

BLUE, GREEN, ORANGE, SLATE, RED, GREY = "#2563eb", "#15803d", "#c2410c", "#1f2937", "#b91c1c", "#6b7280"
W, H = 1440, 700

def text(x, y, s, size=13, fill="#111", weight="normal", anchor="start", family="Helvetica, Arial, sans-serif"):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" text-anchor="{anchor}" font-family="{family}">{s}</text>'
def box(x, y, w, h, color, fill="#fff", dash=None, r=10):
    extra = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{color}" stroke-width="2"{extra}/>'
def head(x, y, w, color, label):
    return f'<rect x="{x}" y="{y}" width="{w}" height="36" rx="10" fill="{color}"/><rect x="{x}" y="{y + 24}" width="{w}" height="12" fill="{color}"/>' + text(x + w / 2, y + 24, label, 17, "#fff", "bold", "middle")
def arrow(x1, y1, x2, y2, color="#333", width=2.5):
    return f'<path d="M {x1} {y1} L {x2} {y2}" stroke="{color}" stroke-width="{width}" fill="none" marker-end="url(#arrow)"/>'
def pill(x, y, w, label, color):
    return f'<rect x="{x}" y="{y - 13}" width="{w}" height="20" rx="10" fill="{color}"/>' + text(x + w / 2, y + 1, label, 12, "#fff", "bold", "middle")
def hexmix(a, b, t):
    a, b = [int(a[i:i+2], 16) for i in (1, 3, 5)], [int(b[i:i+2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(p + (q - p) * t) for p, q in zip(a, b))
def minimap(x, y, size, seed, cols=4, rows=3):
    import random
    rng = random.Random(seed); out = []
    cw = size / cols
    for i in range(rows):
        for j in range(cols):
            out.append(f'<rect x="{x + j * cw:.1f}" y="{y + i * cw:.1f}" width="{cw:.1f}" height="{cw:.1f}" fill="{hexmix("#eff6ff", "#1e3a8a", rng.random())}" stroke="#fff"/>')
    return "\n".join(out)

s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Helvetica, Arial, sans-serif">',
     '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#333"/></marker></defs>',
     f'<rect width="{W}" height="{H}" fill="#fff"/>',
     text(W / 2, 34, "A forecasting task goes into a sandbox; what comes out is checked by computation and by a narrow judge", 21, "#111", "bold", "middle")]

# ---- 1. task ---------------------------------------------------------------------------------
x, y, w, h = 30, 70, 230, 300
s.append(box(x, y, w, h, BLUE, "#eff6ff")); s.append(head(x, y, w, BLUE, "The task"))
s.append(text(x + 14, y + 62, "A forecaster's job, stated as a product:", 12))
s.append(text(x + 14, y + 80, "an outlook, a calibration, a verification.", 12))
s.append(minimap(x + 14, y + 96, 96, 3))
s.append(text(x + 122, y + 118, "frozen data", 12)); s.append(text(x + 122, y + 136, "a short brief", 12)); s.append(text(x + 122, y + 154, "a budget", 12))
s.append(text(x + 14, y + 196, "The method is not stated.", 12, "#111", "bold"))
s.append(text(x + 14, y + 214, "Region and time window are", 12)); s.append(text(x + 14, y + 232, "parameters: one task, many instances.", 12))

# ---- 2. sandbox -------------------------------------------------------------------------------
x, y, w, h = 300, 70, 400, 300
s.append(box(x, y, w, h, GREEN, "#f0fdf4", dash="8 5")); s.append(head(x, y, w, GREEN, "The sandbox: no network, fixed budget"))
s.append(box(x + 16, y + 56, 170, 110, GREEN)); s.append(text(x + 101, y + 80, "The agent", 14, GREEN, "bold", "middle"))
s.append(text(x + 28, y + 104, "a model", 12)); s.append(text(x + 28, y + 122, "driven by a harness", 12)); s.append(text(x + 28, y + 140, "reads, writes code, runs it", 12))
s.append(box(x + 214, y + 56, 170, 110, GREEN, "#fff", dash="5 4")); s.append(text(x + 299, y + 80, "Tooling: in or out", 14, GREEN, "bold", "middle"))
s.append(text(x + 226, y + 104, "skills catalog, libraries,", 12)); s.append(text(x + 226, y + 122, "a conventions sheet,", 12)); s.append(text(x + 226, y + 140, "its own earlier work", 12))
s.append(arrow(x + 214, y + 111, x + 186, y + 111, GREEN, 2))
s.append(text(x + 16, y + 196, "Delivers a fixed envelope, any method:", 12, "#111", "bold"))
s.append(minimap(x + 16, y + 206, 60, 7)); s.append(text(x + 84, y + 222, "results.zarr   labelled arrays", 12, family="Menlo, monospace"))
s.append(text(x + 84, y + 240, "answer.json    numbers, claims, run cmd", 12, family="Menlo, monospace"))
s.append(text(x + 84, y + 258, "code           regenerates the results", 12, family="Menlo, monospace"))
s.append(text(x + 84, y + 276, "report.md      what, why, limits", 12, family="Menlo, monospace"))

# ---- 3. controller -----------------------------------------------------------------------------
x, y, w, h = 740, 70, 430, 300
s.append(box(x, y, w, h, ORANGE, "#fff7ed")); s.append(head(x, y, w, ORANGE, "The controller checks the delivery"))
rows = [("Compute", "a private reference under every defensible reading of the brief,", "so a known wrong reading is named as a pitfall;", "rules every valid answer obeys; skill against withheld observations"),
        ("Rerun", "the agent's own code on changed data: the results must follow", "the data, and must not use what a valid method may not use,", "such as a held-out year or a forecast from the future"),
        ("Judge", "Claude Opus 5.5, one narrow question at a time, on exact", "quotations only: does the report say what the code and the", "numbers say, and state its uncertainty in plain language?")]
for k, (name, a, b, c) in enumerate(rows):
    yy = y + 62 + k * 76
    s.append(f'<rect x="{x + 12}" y="{yy - 14}" width="68" height="22" rx="4" fill="{ORANGE}"/>'); s.append(text(x + 46, yy + 2, name, 13, "#fff", "bold", "middle"))
    s.append(text(x + 90, yy, a, 12)); s.append(text(x + 90, yy + 17, b, 12)); s.append(text(x + 90, yy + 34, c, 12))
s.append(text(x + 12, y + 290, "No human per run. A scientist certifies each task's reference and pitfalls once.", 12))

# ---- 4. result ---------------------------------------------------------------------------------
x, y, w, h = 1210, 70, 200, 300
s.append(box(x, y, w, h, SLATE, "#f3f4f6")); s.append(head(x, y, w, SLATE, "The result"))
s.append(pill(x + 20, y + 72, 60, "pass", GREEN)); s.append(text(x + 90, y + 76, "right, every check", 12))
s.append(pill(x + 20, y + 104, 60, "fail", RED)); s.append(text(x + 90, y + 100, "at fault; the pitfall", 12)); s.append(text(x + 90, y + 116, "or defect named", 12))
s.append(pill(x + 20, y + 144, 90, "unresolved", GREY)); s.append(text(x + 118, y + 148, "outside cause", 12))
s.append(text(x + 20, y + 190, "+ skill score", 12)); s.append(text(x + 20, y + 208, "+ cost, tokens, time", 12)); s.append(text(x + 20, y + 226, "+ which tooling was used", 12)); s.append(text(x + 20, y + 244, "+ every quote and trace", 12))
s.append(text(x + 20, y + 280, "Same checks for every system.", 12))

# arrows between panels
s.append(arrow(260, 220, 300, 220)); s.append(arrow(700, 220, 740, 220)); s.append(arrow(1170, 220, 1210, 220))

# ---- 5. how it scales --------------------------------------------------------------------------------
y = 400
s.append(text(30, y + 20, "How it scales", 18, "#111", "bold"))
# a. instances
x = 30
s.append(text(x, y + 50, "Tasks × instances", 13, BLUE, "bold"))
for i in range(4):
    for j in range(6):
        s.append(f'<rect x="{x + j * 30}" y="{y + 62 + i * 24}" width="26" height="20" rx="3" fill="{hexmix("#dbeafe", "#1d4ed8", (i * 6 + j) / 23)}"/>')
s.append(text(x, y + 176, "25 templates ↓  ×  regions and windows →", 11))
# b. systems × tooling
x = 320
s.append(text(x, y + 50, "Systems × tooling", 13, GREEN, "bold"))
cols = ["none", "skills", "libraries", "sheet"]
for j, c in enumerate(cols): s.append(text(x + 110 + j * 58, y + 68, c, 10, GREY, anchor="middle"))
for i, r in enumerate(["cheap model", "frontier model", "harness A", "harness B"]):
    s.append(text(x, y + 88 + i * 24, r, 11))
    for j in range(4):
        s.append(f'<rect x="{x + 82 + j * 58}" y="{y + 74 + i * 24}" width="54" height="20" rx="3" fill="{hexmix("#dcfce7", "#15803d", ((i * 4 + j) * 7 % 11) / 10)}"/>')
s.append(text(x, y + 176, "Each cell: pass rate, cost, time. Change one thing at a time.", 11))
# c. episodes
x = 680
s.append(text(x, y + 50, "Episodes", 13, ORANGE, "bold"))
for k, label in enumerate(["Ethiopia", "Kenya", "Nigeria"]):
    bx = x + k * 120
    s.append(box(bx, y + 62, 96, 44, ORANGE, "#fff7ed", r=6)); s.append(text(bx + 48, y + 80, label, 12, anchor="middle")); s.append(text(bx + 48, y + 97, f"episode {k + 1}", 10, GREY, anchor="middle"))
    if k < 2: s.append(arrow(bx + 96, y + 84, bx + 120, y + 84, ORANGE, 2))
s.append(text(x, y + 130, "The agent keeps its earlier work.", 11)); s.append(text(x, y + 148, "Compare with a fresh run: does work", 11)); s.append(text(x, y + 166, "accumulate, and what does it save?", 11))
# d. leaderboard
x = 1060
s.append(text(x, y + 50, "Leaderboard", 13, SLATE, "bold"))
for i, (name, v) in enumerate([("system C", 0.9), ("system A", 0.7), ("system B", 0.55), ("climatology", 0.4)]):
    s.append(text(x, y + 78 + i * 22, name, 11)); s.append(f'<rect x="{x + 80}" y="{y + 66 + i * 22}" width="{v * 200:.0f}" height="16" rx="3" fill="{SLATE if name != "climatology" else GREY}"/>')
s.append(text(x, y + 176, "Forecast tasks also take an optimised", 11)); s.append(text(x, y + 194, "submission, scored on withheld observations.", 11))

s.append(text(30, 656, "Under what conditions can a forecaster's task be handed to an agent system and come back right? Per task, per system and per tooling, with the same checks each time.", 12, "#444"))
s.append("</svg>")
Path(__file__).with_name("overview.svg").write_text("\n".join(s))
print("ok")
