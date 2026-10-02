# Consolidate and audit an ACMAD objective outlook

A centre has produced three calibrated component probability products and needs
an objective outlook with an audit of how support and combination choices affect
it. Reconstruct the final consolidation step using the supplied ASO 2026 outputs
from the local ACMAD replication, then explain its sensitivity to unequal weighting.
You are not asked to refit CCA or reproduce forecaster consensus adjustments.

`inputs/observed-sst.nc`, `forecast-sst.nc`, and `forecast-precip.nc` are the three
component MMEs. Each has `below`, `normal`, and `above` on an identical `lat,lon`
grid, expressed in percent. Their inherited member skill mask uses threshold 0.3;
their inherited dry-season mask uses 50 mm. Do not reapply these masks or replace
missing values with climatology. Preserve the provided grid.

At each grid cell, a component supplies a distribution only when all three
categories are finite. Average available component distributions with equal
component weights, then renormalize to sum to one. If none is available, leave
the probability vector missing. Record how many components contribute at each
cell; distinguish full support from an objective based on only one component.

Also calculate a declared sensitivity case using nominal weights `2,8,8` for
observed SST, forecast SST and forecast precipitation, renormalized over available
components at each cell. These weights reflect nominal upstream contributor
counts. This is a sensitivity calculation, **not** reconstruction of the actual
member-pooled objective: per-cell surviving member counts are not supplied.

For each category and cell, compute component disagreement as the maximum minus
minimum available component probability, in percentage points. A single component
has zero disagreement; a cell with no component has missing disagreement.

Deliver:

- `objective.nc`: `probability(tercile,lat,lon)`, `nominal_weighted_probability(tercile,lat,lon)` as fractions with units `1`; `available_components(lat,lon)` as integer counts; `disagreement_pp(tercile,lat,lon)` with units `percentage_points`. Tercile labels are `below,near,above`, mapping source `normal` to `near`.
- `answer.json`: `supported_cells`, `fully_supported_cells`, `single_component_cells`, and `maximum_weighting_difference_pp`.
- `provenance.json`: follow the shared provenance contract; record source identifiers from `inputs/source-manifest.json`, retained input hashes, category mapping, missingness and normalization rules, and the interpretation of the sensitivity case.
- `report.txt` and a labelled `outlook.png`: show the objective, support and sensitivity; explain how missing components and weighting affect interpretation. Do not claim observed forecast skill from these products alone.
- `execution.json` and retained inputs/workflow: declare a command to regenerate the numerical artifacts and required answer fields in a clean offline runtime, following the shared replay contract. Any supported CLI, library or language may be used; there is no required script filename.
- `handoff.txt`: explain the runnable workflow and reusable artifacts.

The shared provenance and replay contracts are supplied with the brief. Basic
validity checks cover deliverables, schemas, source coverage and the information
boundary. Four scored outcomes assess the objective, its audit, scientific
interpretation and reusable workflow.

Do not optimize toward a hidden reference image or identify this reconstruction
as the full published consensus outlook. Runtime, budget and permitted tools are
supplied by the experiment. No successor task is part of this contract.
