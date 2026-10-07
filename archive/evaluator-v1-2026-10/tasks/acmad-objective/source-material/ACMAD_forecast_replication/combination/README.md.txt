# combination — the objective consolidation step

The step ACMAD's pipeline does not include: consolidate the per-member tercile
forecasts into the single **component-equal objective**, with configurable masks, and
render the standard plot set. Shared by every run in this repo (`reference/acmad_run`,
`reference/acmad_rosetta`, `example`) so the combination and plotting are defined once.

## Modules
- **`core.py`** — the ACMAD member roster; loaders for CPT `for_prop`/`pc_skill_map`
  NetCDFs; the two masks; **`north_modes`** (ACMAD's Scree + North's-rule EOF mode
  selection — the decisive setting for matching their engine; see
  `../example/FORECAST_DIFFERENCES.md` §2–3; being upstreamed to deepscale as
  `mode_selection="north"`, PR #119); and `combine_masked` (component-equal via
  `deepscale.combine_terciles`). `build(...)` does a full reference build for one
  (season, skill threshold).
- **`plots.py`** — ACMAD-style renderers via `deepscale.plotting`, all map panels on a
  full cartopy continental basemap: `plot_matrix` (members), `plot_four_panel`
  (3 components + objective), `plot_objective`, the 1:1 comparison figures
  `plot_component_diffs` / `plot_member_diff_matrix`, `plot_member_mae` (per-member
  tercile-MAE bar chart, same metric as the component table), `plot_parity` (data-I/O
  parity rows: ACMAD stack / rosetta stack / difference), and `plot_workflows` (the
  side-by-side pipeline block diagram).

## Two levels of equal weighting
1. **Experiment MME** — average a model's forecasts over its predictor domains, then
   the models within the experiment (Exp-1 obs SST, Exp-2 NMME-fcst SST, Exp-3
   NMME-fcst precip). The pre-combined CPC `nmme` product is excluded.
2. **Objective** — ⅓ each of the three experiment MMEs.

## The two masks (parameters)
- **Skill mask** — blank each member where its cross-validated PC (Pearson) skill is
  ≤ `skill_threshold` (0 = off). Applied *per member before combining* (confirmed by
  ACMAD), so a cell survives where any member is skillful. ACMAD renders {0, 0.3, 0.4};
  the example compares at 0 (full domain) since ACMAD's skill maps are much sparser
  than deepscale's.
- **Dry mask** — blank cells whose 3-month climatological rainfall total is below
  `dry_mm`. ACMAD's operational threshold is **50 mm** (confirmed; the example default);
  the `dry_mask_camsopi` helper keeps 100 mm as its signature default for the historical
  reference runs, which render both.

Both remain configurable; the confirmations are recorded in `../OPEN_QUESTIONS.md`.

## Why average the probabilities, not the values
The combination is done in probability space — averaging each member's
P(below/normal/above) — not the underlying predicted rainfall values, because:

- **The product *is* a probabilistic outlook.** Each CPT run emits a calibrated
  tercile probability and the objective we want is a tercile probability; combining in
  the deliverable's own space is the coherent operation.
- **Probabilities are a common, climatology-relative scale.** The members use
  different predictors, models, domains, each calibrated against its own hindcast
  climatology; their raw values are not commensurable, but their tercile probabilities
  all live on the same unitless [0, 100] scale.
- **It preserves each member's skill and uncertainty.** Calibration has already made a
  skillful member sharp and an unskillful one near-climatology; averaging probabilities
  auto-downweights weak members, whereas averaging values would let one large
  unreliable anomaly dominate.
- **It is the WMO-standard MME consolidation**, and renormalizing keeps a valid simplex.
