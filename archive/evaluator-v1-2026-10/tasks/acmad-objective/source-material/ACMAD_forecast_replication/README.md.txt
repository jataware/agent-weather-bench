# ACMAD forecast replication

Reproductions of ACMAD's operational Africa seasonal rainfall outlook — the
component-equal objective built from three CCA experiments (observed-SST,
NMME-forecast-SST, NMME-forecast-precip) — plus **the combination step ACMAD's own
code does not include**, packaged so the objective can be produced, masked, plotted,
and compared consistently.

This mirrors `ICPAC_MAM_Replication`: a `reference/` side that uses ACMAD's real
CPT.x code, and an `example/` side that reconstructs the same forecast with the open
`rosetta` + `deepscale` libraries only.

## Layout

| Path | What |
|---|---|
| **`combination/`** | The consolidation step we add: component-equal objective (`deepscale.combine_terciles`) with configurable **dry mask** and **PC-skill mask**, and the standard plot set (member matrix, 3-components+objective, objective, 1:1 diffs). Shared by every run below. |
| **`reference/acmad_run/`** | ACMAD's own CPT outputs + our combination. All seasons × skill {0, 0.3, 0.4}, dry {100, 50} mm. |
| **`reference/acmad_rosetta/`** | ACMAD's CPT.x, but data loading swapped to `rosetta` (a rosetta→CPT-format bridge), for ACMAD's roster and the full rosetta model suite. |
| **`example/`** | **The closest-match reproduction** — `rosetta` + `deepscale`, fed ACMAD's **exact** operational inputs natively (no IRIDL): CAMS-OPI predictand + ACMAD's exact NMME roster from CPC's pre-formatted files + ERSSTv5, with ACMAD's confirmed procedure (Scree+North's-rule EOF mode selection, skill-mask-before-combine, equal-weight, dry 50 mm) and the normal-score transform. Objective agrees to **6.2 pp** (tilt corr 0.86); reproducing ACMAD's mode selection instead of a fixed 10/10/10 is the decisive lever (halves the MAE). The residual ~6 pp is the intrinsic deepscale-vs-CPT.x Student-t sharpness. See `example/FORECAST_DIFFERENCES.md`. |
| **`beaker/`** | The `example/` workflow driven by an AI agent in a [Beaker notebook](https://github.com/jataware/beaker-notebook): a context plus an `acmad-replication` Agent Skill, so the objective can be rebuilt, varied, and compared conversationally. See `beaker/README.md`. |
| **`OPEN_QUESTIONS.md`** | The assumptions we resolved (combination weighting, skill-mask stage, dry mask, predictand — now answered) and what remains open. |

## What we added

ACMAD's three repos emit one calibrated tercile forecast per
(experiment × model × predictor-domain × season) plus a per-member PC-skill map, but
**no step that consolidates them into the single objective**. `combination/` is that
step. The two masks are exposed as parameters, with the operational values since
confirmed by ACMAD — dry < **50 mm** 3-month cumulative, PC-skill masking **per member
before combining** (rendered at {0, 0.3, 0.4}). `combination/` also carries
`north_modes`, our reproduction of ACMAD's Scree + North's-rule EOF mode selection —
the single most consequential setting for matching their engine. See
`combination/README.md` for why the combination averages *probabilities*.

## Environment

Requires Python 3.12. Use either route.

pip:

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

conda:

```bash
conda env create -f environment.yml
conda activate acmad-replication
```

## Data

The runs read the sibling ACMAD operational repos and the shared `work/DATA/` tree
(CPT outputs under `../cpt-statistical-downscaling-longrange-forecast/Fig_CPT_EXP/`,
CAMSOPI monthly under `../work/DATA/camsopi/`). The `example`/`acmad_rosetta` sides
fetch predictors + predictand entirely from native public stores via `rosetta` — no
IRI Data Library, no credentials for the NMME/CCSR + PSL sources (the full model suite
additionally uses the C3S CDS).

## Libraries

Built on current `rosetta` and `deepscale`, which carry the products and functions this
workflow needs: rosetta's `obs/cams-opi` (native CPC CAMS-OPI), `cpc_nmme_predictor`
(CPC pre-formatted NMME CPT files — ACMAD's exact inputs), `obs_predictor`, `obs/cmap`,
`obs/tamsat`; deepscale's `seasonal_mme` CCA, `combine_terciles`, `TercileStyle`,
`plot_tercile_comparison`. The ACMAD-style EOF mode selection lives here as
`combination.core.north_modes` while it is upstreamed to deepscale
(`mode_selection="north"`, PR #119).
