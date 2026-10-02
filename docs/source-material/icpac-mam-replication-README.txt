# ICPAC GHACOF Objective Forecast — MAM 2026, faithful replication

A clean, runnable execution of **ICPAC's own** three-component seasonal
precipitation forecast for **MAM (Mar–Apr–May) 2026 from January initialization**
over the Greater Horn of Africa. The goal is that you can see, at a glance, that
this is your workflow and your code — run faithfully — with our few necessary
substitutions clearly isolated and explained.

The objective forecast is the equal-weight combination of three per-model
components:

1. **eREG** — ensemble regression of GCM precipitation against CHIRPS (R)
2. **Logit** — logistic regression on SST indices (Niño3.4, 3-box WVG) (R)
3. **CCA / PyCPT** — canonical correlation analysis via CPT (Python + CPT.x)

## Forecast output

**Objective tercile forecast — MAM 2026 (equal-weight 3-component MME):**

![Objective tercile forecast, MAM 2026](output/plots/objective_dominant_tercile.png)

**The three components and the combined objective:**

![GHACOF objective components — eREG, Logit/WVG, CCA, objective](output/plots/components_comparison.png)

Colours follow the GHACOF outlook style — greens = above-normal (wetter), pale
cyan = near-normal, yellows = below-normal (drier); grey = dry-season mask, blue =
lakes, clipped to the 11 ICPAC/IGAD member states. (Per-component maps are also in
`output/plots/`.)

## Directory layout — what is whose

```
icpac_original/     ICPAC's code, VERBATIM (NCL, eREG/Logit R, PyCPT engine)
icpac_configured/   ICPAC's R drivers with config-only edits (see CHANGES.md)
jataware/           our code: data replicas, auth, PyCPT runner, combine, plots
output/             results — netcdf/ (component MMEs + objective) and plots/
run_all.sh          one orchestrator that runs the whole pipeline
PROVENANCE.md       per-file provenance (verbatim / +config / ours)
CHANGES.md          the exact diff of every line changed in ICPAC's drivers
```

`PROVENANCE.md` and `CHANGES.md` are the place to confirm fidelity: the eREG and
Logit **statistics are byte-identical** to what you sent, the PyCPT engine is
unmodified, and the only edits to your drivers are season, local paths, model
range, and one filename typo fix.

## How faithfully it runs your code

- **eREG / Logit statistics:** your R, unmodified.
- **eREG / Logit drivers:** your R, only configuration changed (CHANGES.md).
- **PyCPT engine:** your `pycpt_functions_seasonal.py` / `pycpt_dictionary.py`, unmodified.
- **Data download:** your **NCL** runs unmodified for the 5 NMME models; the 6
  C3S models use a Python replica that is a line-for-line port of your SST/precip
  NCL (the C3S IRI endpoints sit behind a Copernicus login that NCL's OPeNDAP
  client cannot pass — see PROVENANCE.md).
- **Ours only where you have no code to run:** the multi-model combination /
  objective (you do this manually) and the out-of-Jupyter PyCPT runner.

## Requirements

Four toolchains (ICPAC's Linux servers already have all of these):

| Tool | Used for | Packages |
|------|----------|----------|
| Python ≥3.10 | replicas, auth, PyCPT runner, combine, plots | `numpy scipy netCDF4 requests xarray pandas matplotlib cartopy` (see `environment.yml`) |
| R | eREG, Logit | `foreach doParallel RNetCDF ncdf4` |
| NCL | NMME precip download (optional — replica covers it otherwise) | `ncl` |
| CPT | PyCPT/CCA | `CPT.x` (IRI Climate Predictability Tool, e.g. `cptbin`) |

## Running

```bash
export IRI_EMAIL="you@example.com"      # IRI Data Library login
export IRI_PASSWORD="..."

# point the orchestrator at your tools (examples):
export PYTHON=python
export RSCRIPT=Rscript
export NCL_BIN=/path/to/ncl/bin          # omit to use the replica for NMME too
export CPT_BIN_DIR=/path/to/cpt/bin      # dir containing CPT.x

./run_all.sh
```

Outputs land in `output/netcdf/` (EnsReg/Logit/PyCPT MMEs + the objective) and
`output/plots/` (per-component and objective tercile maps, dry-masked).

## Status of the bundled outputs

The bundled `output/` is the **full three-component objective** (eREG + Logit +
CCA/PyCPT), produced end-to-end on an Apple-Silicon Mac.

**One environment gotcha worth flagging:** `cptbin 17.8.3` fails with "Problem
reading labels file" when conda installs the current `libgfortran5` (14.x) — its
Fortran I/O runtime is incompatible. Pinning **`libgfortran5=12`** fixes it (see
`environment.yml`). This is purely an environment pin, not a workflow change.

## Open questions (same set as our exchange notes)

Combination weighting (assumed equal-weight 1/3, per WMO), the PyCPT NextGen MME
step, CPT version (you use 16.5.9; conda ships 17.8.3), and dry-mask threshold
(50 mm MAM climatology here) are documented assumptions — happy to align these
with your operational choices.
