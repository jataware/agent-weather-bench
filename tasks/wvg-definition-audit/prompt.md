# Audit a literature-derived Western V Gradient definition

A forecaster wants to know whether an existing teleconnection implementation
represents the predictor described in the literature. Audit the Western V
Gradient geometry in Funk and colleagues' 2023 paper against the supplied
implementation excerpt. Recompute both geometries from the same observed SST
input under the common processing convention below, quantify their differences,
and explain what this audit establishes.

The sources are the paper's Figure 1 caption and gradient discussion, the supplied
`inputs/implementation-excerpt.txt`, and the inherited ERSSTv5 provenance record.
Consult the paper through the experiment's supplied literature access. The
structured definitions below make the numerical contract available to every
substrate; interpretation of source differences is still part of the task.

`inputs/sst.nc` supplies monthly ERSSTv5 over the relevant Pacific domain for
1981–2023 in `degree_Celsius`, with normalized monthly timestamps. Use all complete
MAM seasons. Include centres on closed box boundaries, use cosine-latitude weights,
exclude missing SST cells and renormalize valid weights. Compute each month's box
mean, then average March, April and May with equal month weights.

The boxes below use south, north, west, east coordinates with longitude in 0–360.

| Region | Paper geometry | Existing geometry |
| --- | --- | --- |
| Niño 3.4 | −5, 5, 190, 240 | −5, 5, 190, 240 |
| West equatorial | −15, 15, 110, 140 | −15, 20, 120, 160 |
| West north | 20, 35, 160, 200 | 20, 35, 160, 210 |
| West south | −30, −15, 155, 200 | −30, −15, 155, 210 |

For each geometry, define Western V temperature as the equal average of its three
western box temperatures. Standardize Niño 3.4 and the composite Western V series
separately over MAM 1981–2010, using sample standard deviation (`ddof=1`). Compute
`WVG = standardized Niño 3.4 − standardized Western V`.

These weighting, compositing and standardization conventions are **curator
choices for a controlled geometry audit**. They do not establish the paper's
complete numerical implementation. In particular, the supplied period does not
cover the paper's 1950–2020 baseline. The two outputs isolate geometry differences
under the same convention; they do not reproduce the existing script verbatim.

Deliver:

- `indices.nc`: `box_temperature_c(variant,year,region)` and `western_v_c(variant,year)` in `degree_Celsius`; `nino34_z(year)`, `western_v_z(variant,year)` and `wvg(variant,year)` with units `1`. Variants are `paper_geometry,existing_geometry`; regions are `nino34,west_equatorial,west_north,west_south`; years cover 1981–2023 in order.
- `answer.json`: `index_correlation`, `mean_absolute_difference`, and `maximum_absolute_difference` between the two WVG series.
- `provenance.json`: follow the shared provenance contract; record the paper DOI and ERSST identifier from the source manifest, retained-file hashes, boxes, spatial and seasonal weights, baseline and standard deviation convention, and which settings were sourced or supplied as curator choices.
- `report.txt`: explain the geometry differences and the existing script's treatment of raw anomalies versus standardized temperatures. Distinguish an observed index audit from a forecast-skill replication; identify the missing data needed for the latter.
- A labelled `outlook.png` comparing both series, `handoff.txt`, and `execution.json` declaring an offline replay command following the shared replay contract. Retain its required inputs/workflow. Any supported CLI, library or language may be used; no script filename is required.

The shared provenance and replay contracts are supplied with the brief. File and
schema validity, source coverage and the information boundary are prerequisites;
the rubric scores four outcomes: index reconstruction, comparison, scientific
interpretation and reusable workflow.

Agreement or disagreement is not itself a pass criterion. The audit is complete
when calculations, source interpretation and limitations are correct. Neither
rainfall verification nor long-lead forecast skill can be inferred from these
observed SST series. No successor task is required.
