# A stronger subseasonal forecasting challenge

The next scientific stretch should extend the existing subseasonal optimization
family: improve weeks 3–4 precipitation forecasts across the native CONUS grid,
against independently reproduced adaptive bias correction, under chronological
observation availability. The challenge is useful forecasting improvement across
different climates and years. More files or less algorithm assistance would not
establish that improvement.

This is an implementation proposal with a small local reference prototype, **not
a registered eleventh task or an established frontier ceiling**. Astra completed
the supplied CCA reconstruction and the current regional optimization science
checks. Those results motivate stronger baselines and a wider weather problem;
they do not show that the larger instance will defeat frontier models.

## Scientific target and source boundary

Use the [SubseasonalClimateUSA dataset](https://arxiv.org/abs/2109.10399) and the
[Adaptive Bias Correction paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC10272189/).
The latter combines adaptive dynamical correction, climatology and persistence;
its methods use past observations and evaluate forecasts over 2018–2021. Its
published results concern anomaly correlation and several dynamical systems.
Our proposed primary metric below is an RMSE adaptation, so paper skill gains or
an original leaderboard rank would remain unsupported claims.

Pin [the authors' toolkit](https://github.com/microsoft/subseasonal_toolkit/tree/cff00fc81798c5af59d4e9ce26b5fa26bee86abe)
at `cff00fc81798c5af59d4e9ce26b5fa26bee86abe`. A small inspected source pack and
hash manifest are retained in
`var/staging/frontier-challenge-next/source-pack/` and `source-audit.json`.
Notebook code and Markdown cells are retained; outputs and the 150 MB checkout
were removed to conserve disk. The toolkit's ABC entry point depends on component
forecast generation and tuning; the package also brings substantial unrelated
deep learning dependencies. Do not present the supplied harmonic regression as
an independently reproduced ABC baseline.

The exact public forecast source is
`iri-cfsv2-precip-all-us1_5-ensembled.h5`; the target source is
`gt-us_precip_1.5x1.5-14d.h5`, documented by the
[pinned data repository](https://github.com/microsoft/subseasonal_data/blob/29307bbd9f511f251ca0f0975bdd9e1b3d68c421/DATA.md).
Existing acquisition evidence records source lengths of 477,628,552 and
84,198,696 bytes and Azure ETags. Current inputs preserve nine native cells,
already summed 14-day millimetre totals, and Sunday issues. They expose one
CFSv2 lead column. They are insufficient for the toolkit's complete issuance and
lead averaging or recent-observation features.

Full-grid packaging would preserve the source's native 376-location ordering,
subject to an actual coordinate and coverage audit, rather than interpolate to
a new grid. That count comes from the inspected extraction implementation;
complete forecast and observation coverage for all 376 cells has **not** been
verified. No expanded data were downloaded after disk pressure was reported.

## A fixed chronological experiment

The proposed issue schedule is weekly Sundays from 1999 through 2021. Training
history starts in 1999; source-available earlier CPC observations may support a
declared climatology, but must be separately manifested. Use 2012–2014 for curator
baseline checks, 2015–2017 for bounded agent development feedback, and 2018–2021
for final evaluation. Target windows begin at issue plus 14 days and cover
`[target_start, target_start + 14 days)`.

For the initial history, require target windows to end before 2015-01-01.
Development targets must end before 2018-01-01. Remove crossing cases before any
comparison of methods. Within every rolling fit, a target becomes eligible only
after its complete window and a declared release delay. The prototype assumes
one additional day: `target_start + 15 days <= issue_time`. This is a conservative
curator availability rule, **not evidence of actual CPC publication times**.
Original forecast issuance and reanalysis vintages need the same explicit audit;
otherwise the experiment must be called retrospective availability simulation.

The algorithm may update using observations released during the final period.
That is legitimate online forecasting, but requires chronological execution.
Freeze code, initial state and an update rule before final evaluation; run it
without the agent present, supplying only the current issue's forecast features
and previously released observations. Save each prediction and state transition
before releasing later history. No final score feedback reaches the agent.

**Do not deliver all final lagged-observation feature rows in one agent-visible
file.** A later row can reveal an earlier target, making a batch submission leak
even when each individual row was forecast-time valid. The existing static
prediction-file feedback tool does not enforce this sequential boundary. A new
version needs a controller-owned sequential replay, with the frozen program
scored on development periods under exactly the final execution rules. Five
development program submissions would retain the current search allowance.

Fix support from forecast/observation availability, without inspecting any
method's error. Publish the issue list, grid coordinates, masks, removal reasons
and counts before launch. Require predictions on every scored pair. Missing
predictions make a submission inadmissible; they cannot shrink the denominator.
If full support is infeasible, freeze a transparent reduced support mask and
label the benchmark adaptation accordingly.

## Baselines and a meaningful achievement target

Independently reproduce raw CFSv2, a declared climatology, the existing harmonic
affine starter, and the authors' CFSv2 ABC components and their uniform ensemble.
Check daily/lead averaging, tuning history, leap-day handling, climatology vintage
and availability against the pinned implementation. Restrict all methods to the
same information and support. If the toolkit cannot be reproduced, publish a
clearly named adaptation and keep official ABC parity as an open readiness item.

Before exposing any new solver output, select the strongest admissible baseline
using the 2012–2014 curator period, freeze its configuration or causal tuning
rule, and hash its implementation and predictions. Baseline selection cannot use
the final period. Keep all baseline scores visible in the final report, including
the ABC ensemble even if a simpler baseline wins the earlier comparison.

The proposed primary metric remains pooled cosine-latitude-weighted RMSE:

`sqrt(sum_case,cell(w_cell * error²) / sum_case,cell(w_cell))`.

The denominator includes the complete frozen support. Compute the same metric
separately by final year and predeclared broad climate regions. Add the source
paper's anomaly correlation only after freezing its precise climatology,
centering, spatial support and temporal aggregation. Do not replace an RMSE
failure with a favorable secondary score.

A concrete **proposed** achievement tier is at least 1% lower final RMSE than
the preselected strong baseline, with no more than 2% RMSE degradation in at
least three of the four final years. Those thresholds are curator choices, not
paper results or calibrated difficulty. Freeze them before any stronger-instance
solver pilot; do not retune them to make a particular model fail. Keep correct
scientific completion separate from this performance tier: a well-supported
negative result can complete the workflow without achieving improvement.

Report paired moving-block uncertainty using identical sampled issue blocks for
the candidate and baseline; a proposed default is eight weekly issues per block,
with four- and thirteen-issue sensitivity checks. Spatial cells must remain
together within an issue. Four final years provide limited evidence about future
climate regimes, so intervals do not establish general operational superiority.

## Assistance and practical limits

The main condition supplies the papers, pinned component sources, an executable
verified strong baseline, metric code, availability calendar and data dictionary.
It leaves forecasting methods open. A separate source-only condition can measure
method reconstruction, with its assistance level clearly recorded. Removing a
necessary formula or hiding units would assess a different problem.

Proposed limits are two CPU hours, four cores, 8 GB RAM, five development
submissions, and separately logged agent tokens and wall time. These are **not
measured full-grid runtimes**. Measure the frozen baseline first; if it cannot
finish within the same compute allowance, revise the instance before launch.
No GPU, cloud allocation or additional paid API call is needed for reference work.

Keep the frozen compact arrays once. A projected 1,194 weekly issues × 376 cells
× 30 float32 lead values is about 54 MB before metadata; the corresponding
one-variable targets are about 1.8 MB. Complete daily issuance history required
by faithful lead averaging is larger, and source HDF5 metadata/range alignment
adds transfer overhead. The two complete source blobs total about 562 MB. A
future extractor should cap transfer and disk explicitly, pin ETags, verify
coordinates/calendars for every selected row, and report actual bytes. Extraction
is currently paused because of disk pressure; these arithmetic estimates do not
prove data completeness or permission to redistribute it.

## Independent checks and current readiness

Use a second scalar-loop metric implementation with hand-worked fixtures. Compare
the reference component predictions to the pinned toolkit on a small audited
period, then use alternate linear algebra and direct climatology calculations
to check mathematical invariants. Preserve rotation equivalence for any spatial
dimension reduction. Source code agreement alone is insufficient independence.

Required failure controls include unresolved target windows, future release
rows, later final lag features, all-year tuning, erroneous ×14 precipitation
rescaling, latitude-weight normalization, silently omitted arid cells, stale
saved state and labels opened during inference. Perturb unreleased labels and
future features and require earlier forecasts and states to remain identical.
Change a legitimately released observation and confirm an updating method uses
the new history without changing earlier predictions. Score cached-prediction
controls on changed inputs as well as original replay.

The staged [prototype](../var/staging/frontier-challenge-next/rolling_reference_prototype.py)
uses only existing training inputs and 153 issues from 2012–2014 across nine
cells. It exercised six simple causal references in about 0.4 seconds. A
second metric agreed within 3.6e-14 mm, and modifying every observation unavailable
at the first query left that forecast unchanged for all six methods. Harmonic
affine RMSE was 11.55 mm, versus raw CFSv2 14.53 mm, on this **predevelopment
regional reference experiment**. These are not agent results, final outcomes,
ABC parity evidence or a full-grid timing measurement. Results and source hashes
are in `var/staging/frontier-challenge-next/prototype-results.json`.

Before launch, still required are full-grid acquisition and coverage, faithful
strong-baseline reproduction, sequential controller isolation, independent
availability/metric controls, a frozen threshold and compute allowance, and a
new versioned package. Source/data rights review remains separate from internal
development. The first frontier pilot would establish whether improvement is
within reach under declared assistance; it cannot be assumed in advance.
