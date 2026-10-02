# Agent Weather Bench identity

The selected working name is **Agent Weather Bench**. It names the subject and
the kind of project. The repository slug remains `agent-weather-bench`.

Use **A benchmark for AI forecast research** as the subtitle.
Use **Benchmark AI models on forecasting tasks.** as the public lead.
Introduce the full name before using AWB. Keep all three words in a public title.

Lead with model comparisons on common scientific tasks. Treat added skills, code,
retrieval, and prior work as a separate experiment dimension. Report cost and
time to solution alongside scientific performance. Keep the public introduction
general; individual institutions and local task sources do not define the benchmark.

## Symbol

The symbol uses three weather contours to suggest forecast research. One gold
point refers to a checked result.
The drawing is abstract; it does not encode a measured forecast or performance curve.

Use `symbol.svg` on a light background and `symbol-inverse.svg` on a dark one.
Use `symbol-mono.svg` when colour is unavailable. `icon.svg` adds a dark square
for avatars and favicons. Keep clear space of at least one quarter of the symbol's
width. At very small sizes, use the icon rather than the full wordmark.

## Colour and type

| Role | Colour | Use |
| --- | --- | --- |
| Ink | `#19383d` | Primary text, dark field |
| Paper | `#f6f4ed` | Background |
| Field | `#28786b` | Links, flow paths, contour strokes on light backgrounds |
| Contour | `#92d1bf` | Contour strokes on dark backgrounds |
| Measure | `#e5b95e` | Measurement point and small accents |

Use dark ink for text on paper. Use mint and paper for text on the dark field.
Gold is an accent; avoid gold body text on paper. Meaning must remain clear
without colour.

The vector assets use Arial with Helvetica and sans-serif fallbacks. They need
no downloaded fonts. The preview uses system sans-serif for body text and Georgia
for editorial headings. PNG exports fix the appearance for sharing.

## Writing

Use simplified technical English as a guide. Prefer short sentences and active
verbs. Put one action in each instruction. Keep a term's meaning stable. Define
domain words that a new reader needs. Name the agent, controller, task, and system
when an ambiguous pronoun could hide responsibility.

The README aims for the user's approximate STE style. It does not claim formal
[ASD-STE100](https://www.asd-ste100.org/) compliance or a measured compliance percentage.
Research terms such as calibration, substrate, and teleconnection remain useful.
Define them where needed rather than removing the scientific meaning.

Start with the research goal. Follow with the experiment and the route to a first
run. State development readiness beside the relevant task. Do not present intended
results as measured findings.

## Diagrams and sharing

`agent-task-comparison.svg` is a paper-style illustration of the same robot agent
attempting one three-step task with general tools and with task-specific tools.
Both attempts receive the same grading. The contrasting outcomes are illustrative;
they are not benchmark results or a guarantee that tooling improves performance.
The robot is a self-contained vector in the style of an emoji, so it prints without
depending on a platform's emoji font. The figure is 1560 × 770, with a 3120 × 1540
PNG and a vector PDF export.

`benchmark-design.svg` explains common tasks, different models, captured artifacts,
and fixed assessment. Capability, cost, and time lead the comparison. Substrate
and reuse are additional experiments. Private references enter assessment directly.
Only agent-owned state and prior artifacts enter the next task. Related follow-ups
are optional; the primary reuse experiment spans other benchmark tasks.

`social-card.svg` is a 1200 × 630 sharing image. The PNG export has the same size.
The hero is 1440 × 360. The vector diagram is 1440 × 820; its PNG export is
2880 × 1640. The icon PNG is 512 × 512.
The preview needs no network access and can open directly from the filesystem.

Regenerate vectors and the README preview from the repository root:

```sh
.venv/bin/python docs/assets/brand/build.py
```

The generated SVGs are also editable directly. After changing the source or
typography, regenerate PNGs and inspect both desktop and mobile sizes. The build
script generates the preview from the current root README.

For PNG exports, use Node with an installed Playwright module and Chromium:

```sh
node docs/assets/brand/export.cjs
```

If Playwright or Chrome is installed elsewhere, set `AWB_PLAYWRIGHT_MODULE` to
the module path and `AWB_CHROME_EXECUTABLE` to the browser path. These tools are
needed only for PNG export. Viewing the preview and SVGs needs a browser alone.
