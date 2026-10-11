Original portfolio entry #23 now has a working chronological forecasting prototype. Seven fixed comparator programs completed all fourteen development/final Docker streams. Fixed monthly climatology beat every updating comparator on both splits. This is a concrete negative result for adapting the current nine-cell rainfall fixture, not evidence that an agent failed or that adaptation cannot help elsewhere. No model calls were made.

The new controller sends one issue at a time to a persistent isolated program. Observations become available at issue+35 days: a fourteen-day lead, fourteen-day target window, and explicitly simulated seven-day publication lag. Future covariates and observations are never mounted into the program. Forecasts are immutable once returned. The development episode has 157 issues in 2012–2014; final has 359 issues in 2015–2021. Each episode starts with all observations released by its first issue, including available development observations for final initialization. The original 1,194-issue public historical archive is unchanged. Missing weekly issues remain missing. This is not a reconstruction of operational release vintages or a pristine holdout.

| Fixed comparator | Development RMSE, mm | Final RMSE, mm |
| --- | ---: | ---: |
| raw | 14.6809 | 14.8956 |
| monthly_climatology | 11.9315 | 13.1797 |
| monthly_static | 12.5420 | 13.8893 |
| expanding_shrinkage | 12.6055 | 13.8250 |
| rolling_seasonal_bias | 12.9531 | 14.2332 |
| adaptive_ridge | 12.2991 | 13.5923 |
| adaptive_ensemble | 12.3617 | 13.6286 |

Methods and parameters were frozen before their private scores. They were not retuned after seeing the result. All forecasts used the same chronological release contract. These seven methods are executable controls and local comparators, not a reproduced published state-of-the-art suite. Their results do not justify an achievable improvement target above climatology, so no actor trial or forced native-library comparison was launched.

Implementation includes [the controller](../assessment/sequential.py), [data builder](../experiments/sequential_forecast_data.py), [comparator programs](../experiments/sequential_controls.py), and [actor/development-feedback integration](../experiments/sequential_actor.py). A neutral program brief lives under `templates/weekly-updating-rainfall/`; it has no registered spec and is not counted as an eleventh completed/certified template. The program contract differs from the batch envelope because the controller must collect predictions after sequential observation release. Existing template contracts, submissions and assessments were not changed.

Forty-six targeted tests pass. Seven actual Docker fault/isolation episodes check private-file access, read-only submission, persistent state, wrong identifiers, negative predictions, missing output, timeout, chronological release and immutable earlier forecasts. Tests exposed an early Docker launch failure incorrectly classified as a model failure; this is fixed and covered by regression. The final controller replays the adaptive ensemble's 359 predictions exactly. The initial successful-control batch preceded transport-only fixes; both subsequent proof versions are preserved separately, without replacing original results. A reconstructed initial source copy is labelled as reconstructed, not an originally captured source hash.

Evidence: [data](../experiments/sequential-forecast-data-2026-10-08.json), [frozen comparator settings](../experiments/sequential-controls-plan-2026-10-08.json), [all comparator results](../experiments/sequential-controls-results-2026-10-08.json), [Docker fault controls](../experiments/sequential-fault-controls-2026-10-08.json), [final transport proof](../experiments/sequential-control-final-transport-proof-2-2026-10-08.json), and [actor integration tests](../experiments/sequential-actor-preflight-2026-10-08.json). No paid API spend or model tokens were incurred by this investigation.
