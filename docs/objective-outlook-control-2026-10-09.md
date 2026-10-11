# The objective seasonal outlook: snapshot, control and planted faults

Status: 9 October 2026, step 2 of the [roadmap](roadmap.md). The task record is
[designs/objective-seasonal-outlook.md](../designs/objective-seasonal-outlook.md);
the template is `templates/objective-seasonal-outlook/`. No model attempt has run.
Docker was unavailable on the build machine, so every result below comes from the
host-trusted executor on the controller's own control solutions; certification
with the Docker executor and the per-stage rubric (step 3) are still to come.

## The snapshot holds acmadDL deliveries, not raw provider trees

A first attempt pulled raw NMME trees from the IRI Data Library and was stopped
after 52 MB: hundreds of megabytes per model over the internet before any
control could run. The snapshot now holds what `acmaddl.fetch` returns for each
product, plus NetCDF conversions of the acmadDL raw cache already on disk.

| Resource | Source | Size |
| --- | --- | --- |
| CCSM4, GEOS-S2S, CanSIPS-IC4, CFSv2 target-season precipitation, February and August issuances 1993–2016, every member, 1° over 13S–23N 21–52E | 8 `acmaddl.fetch` calls, 0.4–3.6 MB each | 15 MB |
| CFSv2 target-season forecast SST, both issuances, 40S–40N 100E–100W | 2 `acmaddl.fetch` calls | 31 MB |
| CHIRPS v2.0 monthly, 0.05°, 1993–2016, 13S–16N 21–53E | acmadDL raw cache, converted | 242 MB |
| ERSST v5 monthly, 2°, 1993–2016, 100E–100W | acmadDL raw cache, converted | 2 MB |

The withheld year 2015 is removed from both observation files and kept
controller-private. `sources.json` records every file's hash; `provenance.json`
records each fetch's product, parameters and the cache keys of the conversions.

The genuine data trap is not stitching, which acmadDL already does for CFSv2's
two IRI trees, but units: acmadDL delivers CFSv2 as season totals in mm and the
other three centres as mean rates in mm/day, with different coordinate dtypes.
The practice document says only "in the units each file declares".

## The reference computes all eight stages in twenty seconds

`science.py` (NumPy, SciPy, xarray) implements prepare, WVG, eReg, CCA, combine,
verify and issue on the 58 by 62 target grid (2627 supported land cells).
`reference_independent.py` implements prepare, WVG and eReg separately (netCDF4
reads, explicit loops, Fisher scoring, hand-written quantiles) and agrees with
the deciding implementation to 1.4e-12 mm on totals and 3e-14 on probabilities.

Two spreads were measured and set bounds:

- **WVG solver spread.** The vectorised Newton fit against scipy's L-BFGS-B on
  599 supported cells: maximum gap 5.0e-6, 99th percentile 2.4e-6
  (`var/validation/objective-seasonal-outlook/wvg-solver-spread-mam.json`). The
  spec bound is 2.2e-5.
- **CCA engine spread.** africaS2S's CPT-parity CCA on the same prepared arrays
  (window-5 cross-validation, Kendall-tau mode selection, with and without the
  empirical transform) correlates with the nested reference CCA at 0.64–0.90 per
  category on the MAM hindcasts and 0.75–0.91 on OND, 0.70–0.98 on the
  forecasts, with a mean absolute probability gap of 0.04–0.05, and scores up to
  0.061 (MAM) and 0.067 (OND) RPSS below it (`cca-engine-spread-mam-nested.json`,
  `cca-engine-spread-ond.json`). The gate therefore uses a correlation floor of
  0.6 and an RPSS margin of 0.08; the floor is tight against the measured 0.642.
  The task record's 0.85 floor, decided before the measurement, would have
  rejected africaS2S's own CCA and is superseded.

The CCA stage selects modes inside each hindcast fold (an inner leave-one-year-out
over the other years) and takes the residual variance from those inner
predictions, so nothing about a hindcast year touches its own observation. The
first build selected modes once on all years, as CPT does, and the held-out-year
probe failed on the correct control; the practice document already required
fold-local fitting, so the reference changed, not the probe. One SVD pair per
fold serves all 120 candidate mode choices, and each pair of years is factored
once, which keeps the stage at about fifteen seconds per instance.

## The correct control passes every computed check on both instances

| Instance | Computed checks | Assessment time | Hindcast RPSS (CCA, eReg, WVG, objective) | Withheld 2015 RPSS |
| --- | --- | --- | --- | --- |
| `gha--mam-2015` | 13 of 13 pass | 2 min 56 s | −0.009, 0.021, −0.021, 0.022 | 0.044 |
| `gha--ond-2015` | 13 of 13 pass | 2 min 55 s | 0.060, 0.047, −0.012, 0.056 | 0.165 |

The two prose questions stay unresolved because no judge was run. The reference
arrays for both instances under the default readings are stored under
`var/private/templates/objective-seasonal-outlook/references/`. The OND 2015
outlook puts a 50 percent mean probability on above-normal rainfall over the
supported cells, consistent with the 2015 El Niño; the MAM outlook is near
climatology. These are descriptive, not a skill claim.

## Planted faults, one per stage

| Stage | Control | Checks expected to fail | Stage rows |
| --- | --- | --- | --- |
| acquire | `wrong_initialization`: the other season's files under this season's names | CCA-agreement invariant; variant and changed-data probe unresolved (no reading matches) | `stage.cca` fails; `stage.prepare`, `stage.wvg`, `stage.ereg` unresolved (no reading fits) |
| prepare | `thirty_days`: ninety-day season | variant | `stage.prepare` fails |
| WVG | `wvg_leak`: each year's fit includes that year | held-out probe and its WVG part; WVG-from-own-prepare invariant; variant and changed-data probe unresolved | `stage.wvg` fails |
| eReg | `ereg_no_cross_validation` | held-out probe and its eReg part; eReg-from-own-prepare invariant; variant and changed-data probe unresolved | `stage.ereg` fails |
| CCA | `cca_future_training`: hindcasts from a fit on all years | held-out probe and its CCA part | `stage.cca` fails |
| combine | `unequal_weights` (its verification recomputed from its own combination) | equal-stream-combination invariant | `stage.combine` fails |
| verify | `wrong_climatology_score`: training-frequency baseline | score-identity invariant | `stage.verify` fails |
| issue | `issue_mismatch`: categories reversed in the issued array | issue-identity invariant | `stage.issue` fails |

Also `full_record` (the thresholds pitfall), `cached` (stale results on changed
data), `reordered` and `bilinear_residual` (accepted alternatives) and
`independent`.

- `full_record` fails `stage.wvg`, `stage.ereg` and `stage.cca` and passes
  `stage.prepare`. A year's own category is the same whether or not that year
  sits in the boundary sample (zero differing cell-years on both instances),
  so the pitfall shows only in the labels of the other years inside each
  fold, which the streams use and the prepare arrays do not. The first
  certification under the stage rubric expected `stage.prepare` to fail and
  was corrected.
- `cached` fails the changed-data probe and `stage.prepare`, `stage.wvg` and
  `stage.ereg`, whose absolute verdicts include the per-stage changed-data test.

## Certification: the four automatic tests pass on both instances under the stage rubric

Record: `templates/objective-seasonal-outlook/certification.json` (local trusted
executor, spec version 2, started 9 October 2026; the machine slept during the
run, and the running time projected from its control pace is about 85 minutes). An earlier run
under spec version 1 (before the stage rubric) also passed all four tests.

| Test | Result |
| --- | --- |
| 1 reference implementations agree | 36 reading combinations on 2 instances, 72 comparisons, largest difference 1.4e-12 |
| 2 known-correct solutions pass | `correct`, `independent`, `reordered`, `bilinear_residual` pass every computed check, including all eight `stage.*` rows, on both instances |
| 3 incorrect solutions are caught | all 10 faulty controls fail with exactly the expected checks and stage rows on both instances (table above) |
| 4 separability | all 6 reading pairs separated by the numbers on every instance |
| 5 model attempts | pending (needs Docker; the daemon does not answer on this machine) |

The first run under the stage rubric failed test 3 on one expectation only:
`full_record` was expected to fail `stage.prepare` and passed it. The
expectation was wrong (see the fault list above) and was corrected; the
grader was not changed.
