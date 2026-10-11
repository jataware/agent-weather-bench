# The objective seasonal outlook: review before any model call

Roadmap step 4. The task was reviewed as the agent sees it, row by row, before
any model attempt, so that the first attempt measures the agent and not the
contract. Two readings were made on 11 October 2026: the author's pass against
the reference (`science.py`), and a cold read by a context-free agent that saw
only the rendered brief, `practice.md` and the served files, and was told to
list every point where two careful implementers would produce different
numbers. The cold reader did not see the reference, the spec or the controls.

## What was reviewed

| Item | As reviewed |
| --- | --- |
| Brief | `python -m assessment brief objective-seasonal-outlook gha--mam-2015`: 600 words before the review, 693 after |
| Practice sheet | `practice.md`, supplied in the input directory |
| Rubric | 30 instrument rows (`python -m assessment rubric`): envelope, coverage, variant, 9 invariants, 6 probe rows, 1 claim, 8 stage rows, 2 prose reviews, skill |
| Controls | 14: 2 known-correct, 2 accepted alternatives, 10 faulty (one per stage, plus `full_record` and `cached`) |
| Budget | none declared before the review |
| Served data | 13 resources, 275 MB; no missing ensemble members; CHIRPS missing over the ocean only; SST missing over land only |

## Findings on the brief and practice sheet

Each row names the array affected, what was open, what the reference does, and
the disposition. "Pinned" means the practice sheet or brief now states the
reference's convention. Nothing in the grader changed.

| # | Array | What was open | Reference | Disposition |
| --- | --- | --- | --- | --- |
| 1 | `prepare_model_*_mean_mm` | How model fields reach the target grid (undefined anywhere) | bilinear from the served points to the target centres | pinned |
| 2 | `prepare_observed_mm` | Weights of the "area-conservative mean" | cosine of each source cell's centre latitude | pinned |
| 3 | `prepare_observed_mm`, `prepare_support` | Which source cells are "inside" a target cell | the hundred whose centres lie within a quarter degree | pinned (CHIRPS centres never fall on an edge, so inclusive and exclusive agree) |
| 4 | `prepare_sst_index*` | Box edges on grid points: inclusive or exclusive | inclusive; on the CFSv2 one-degree grid every edge is a grid line, so the two readings differ by 120 to 150 cells per box | pinned |
| 5 | `prepare_sst_index*` | Divisor of the standard deviation | n−1 | pinned |
| 6 | `wvg_*` | Standardization per fold or once | once over the training years | pinned |
| 7 | `prepare_sst_index` | Seasonal SST mean: plain or day-weighted | plain mean of the monthly fields | pinned |
| 8 | `prepare_sst_index_forecast` | Climatology of the forecast index: ensemble-mean series or members; forecast year in or out | ensemble-mean series over the training years, forecast year excluded | pinned |
| 9 | `wvg_*` | Labels of the fitting years inside a fold | the fold's own boundaries, from the fitting years | pinned |
| 10 | `wvg_*` | A fold with no below-normal year (occurs on the data: at least one supported cell has none in any fold) | the class frequency: zero | pinned |
| 11 | `ereg_*` | Residual divisor; inflation formula | n−2; s²(1 + 1/n + (x₀−x̄)²/Σ(x−x̄)²) | pinned |
| 12 | `cca_*` | One selection of modes on all years contradicts "no year's observation enters its own hindcast"; `cca_modes_selected` is one integer per model | nested inner leave-one-year-out per historical year; the forecast's selection is the reported count | pinned (the arrays stay free; the gate stays at correlation 0.6 and RPSS margin 0.08) |
| 13 | `cca_*` | Student-t degrees of freedom and inflation | n − predictor modes − 1; (1 + 1/n) | pinned as the reference's choice; the stream stays open |
| 14 | every per-cell array | Fill on unsupported cells was stated for probabilities and totals only; categories, counts and scores were not covered, and the dominant category of an all-zero cell would be near normal by the brief's own tie rule where the reference holds zero | zero everywhere | pinned in both texts |
| 15 | all fixed arrays | Precision: CHIRPS and three models are served in float32; summing in float32 exceeds the 2.2e-6 mm bound on totals near 1000 mm | float64 from the first read | stated in both texts |
| 16 | `combine_available_streams`, `cca_hindcast_mean_mm` | Listed without a definition | 3 on supported cells, 0 elsewhere; the equal-weight mean of the models' cross-validated CCA predictions | defined in the brief |
| 17 | `prepare_tercile_*` | Quantile definition | Hyndman and Fan type 7 (NumPy `linear`) | named |
| 18 | `issue_dominant_category` | Tie: exact or tolerance | exact | pinned |
| 19 | CFSv2 SST | The delivery is labelled kelvin and holds degrees Celsius (confirmed: Nino 3.4 ensemble mean 27.6) | standardization removes the unit | stated in the practice sheet; the frozen delivery is unchanged |

Three findings of the cold reader were checked and found not to apply:

- Support at the edge of CHIRPS coverage: the target grid (58 × 62 cells,
  12.75S to 15.75N, 21.25E to 51.75E) lies inside the CHIRPS window, so no
  target cell is empty of source cells. `target-grid.nc` is written into the
  input directory at staging time; it is not in the repository.
- Perfect separation in the logistic fit: 1 of 60,421 fold-cells on MAM; the
  stated midpoint rule covers it.
- Days in the season: 92 for both windows in every year, so the calendar rule
  cannot fork on these instances; the `thirty_days` pitfall (90) still differs.

## Findings on the rubric

- Every row is decided by a stated procedure (confirmed from the rubric
  contract): 27 rows by computation, 2 by the judge, 1 reported number.
- The bulletin review `interpretation.bulletin_support` asks whether every
  number the bulletin states appears in the arrays. The judge sees text only:
  the brief, the report, `answer.json`, the code and a per-array summary of
  shape, minimum, mean and maximum. Area shares and regional probabilities,
  which bulletins state, were not derivable from that summary, so the question
  was not decidable as written. Fixed: an optional template hook
  `judge_summary` appends the area share of each dominant category, the
  issued probability's mean, minimum and maximum per category over the
  supported window, and the four skill scores. On the MAM reference this reads:
  above normal dominant on 80.9% of supported cells, mean 0.413; objective
  RPSS 0.0216.
- The stage rows carry completion; the whole-submission match and the probes
  are evidence. A result that fits no listed reading leaves the variant match
  and the changed-data probe unresolved and the stage rows say which stage is
  at fault (certified on all ten faulty controls).
- The skill row is descriptive: one withheld season per instance, ranking
  disabled. The brief says so.

## Findings on the controls

- The 14 controls obtain their data through the same HTTP catalogue as an
  agent and run the reference with a declared defect, so each exercises the
  acquisition path (confirmed).
- Each planted fault fires in its own stage row and nowhere else; the two
  accepted alternatives (reordered dimensions; bilinear observations with the
  residual-variance eReg) pass every row (certification of 9 and 10 October,
  and the re-certification below).
- What no control exercises: a solution that passes every fixed array and
  fails only the bulletin review; a CCA that is sound but outside the gate.
  The first is the judge's calibration cases' territory; the second is what
  the gate's margin is for, and the first agent attempts will show whether
  0.6 and 0.08 are right.

## Budget and cost

- Tier, now declared in the spec: 4 hours of wall time, 600 tool calls, 30
  minutes per run of the submitted command, 4 million tokens, 6 GB of memory,
  2 CPUs. The reference computes all eight stages in about 20 seconds; the
  memory follows from CHIRPS (410 MB in float32, twice that in float64) plus
  intermediate copies.
- The cold reader's difficulty estimate: 6 to 10 hours of agent work, CCA the
  hardest stage (3 to 5 hours), then the one-class logistic cell, the
  regridding method and the box edges as the likeliest failures; the first
  three of those are now pinned.
- Cost per attempt at the tier (guess): an Opus-class backbone 20 to 40
  dollars; a Sonnet-class backbone about a third. Recorded per attempt.

## What this review did not do

- No domain scientist read the brief. The cold reader is a model with no task
  context, which tests the text's completeness and not the centre's practice.
- The CCA stream's open choices (skill measure of the selection, gamma
  transformation) remain open by design; the gate, not a match, decides it.
- The judge's two questions have not been run on a real bulletin for this
  task; the judge's own calibration cases are generic.

## Re-certification

Pinning the conventions changed `practice.md`, `brief.md`, `spec.yaml` and
`reference.py`, and the judge hook changed a deciding module, so every
template's fingerprint moved. The runs finished on 11 October 2026.

- The outlook template passed automatic tests 1 to 4 under the pinned brief
  (`certified_at` 20261011T100200, spec version 2, executor
  `local-trusted-snapshot`). Test 1 compared 36 convention combinations on
  both instances (72 comparisons; largest difference 1.4e-12). Test 2 passed
  all 8 known-correct and accepted-alternative controls (`correct`,
  `independent`, `reordered`, `bilinear_residual` on MAM and OND 2015).
  Test 3 caught all 20 incorrect and pitfall controls, including the corrected
  `full_record` expectation. Test 4 separated all 6 convention pairs by the
  numbers on every instance with no known ambiguity. Test 5 stays `null`
  because no agent attempt exists yet (Docker).
- The five locked templates (kenya-forecast-revision, weeks34-rainfall,
  seasonal-rainfall-calibration, rainfall-downscaling,
  seasonal-cca-reproduction) re-certified under the new fingerprint with
  automatic tests passing and records current.
- The pins did not change any reference value: the known-correct controls'
  skill scores are unchanged from the step-3 record (MAM 2015 RPSS 0.0437,
  OND 2015 RPSS 0.1645 over 2627 cells).
