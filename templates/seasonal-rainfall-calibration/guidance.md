# Guidance: an objective seasonal forecast

The World Meteorological Organization describes an objective seasonal forecast
as one that follows these practices.

1. Follow a traceable, reproducible, and well-documented procedure, amenable to verification.
2. Use dynamical climate models, including multi-model ensembles.
3. Establish quality controlled observational databases for forecast verification.
4. Identify, assess and monitor drivers of predictable climate variability.
5. Follow forecast verification standards.
6. Provide forecast information together with historical performance.
7. Use non-technical language to communicate uncertainty.
8. Provide seasonal forecasts as well as regular updates on a fixed operational schedule.
9. Establish user feedback and product upgrade mechanisms.

## What conformance means for this task

- **Seasonal totals.** The October–December total is the sum of the three monthly totals. The observed total on the forecast grid is the area mean of the native observation cells whose centres fall inside each one-degree forecast cell.
- **Categories.** Below-, near- and above-normal are separated by the 1/3 and 2/3 quantiles (linear interpolation) of the observed totals at each cell. A total equal to a boundary is near-normal.
- **Cross-validation.** The historical forecast for a year must not use that year's observation anywhere: not in the calibration, and not in the category boundaries.
- **Historical performance.** Report the ranked probability skill score of the cross-validated forecasts against a climatological forecast, pooled over years and cells.
- **New years.** Forecast each new year from the fitted calibration and that year's model forecast alone.
- **Documentation.** State where your code performs the calibration and where it holds out a year, and describe the forecast's uncertainty in plain language in your report.

Practices 4, 8 and 9, and the multi-model part of practice 2, do not apply to a single forecast from one model.
