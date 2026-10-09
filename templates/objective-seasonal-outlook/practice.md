# The centre's objective seasonal forecast practice

This document names the practice. It gives no code, no formulas beyond definitions, and no worked example. Where it names a choice as open, the choice is yours; record it in `answer.json` under `choices`.

## Inputs

- **Models.** Four NMME centres: CCSM4, GEOS-S2S, CanSIPS-IC4 and CFSv2, each as served: the target-season precipitation per member for every initialization year of the training period, on the model's own one-degree grid, in the units each file declares.
- **Observations.** CHIRPS v2.0 monthly rainfall at 0.05 degrees. Seasonal totals are the sum of the target months. The centre works on the 0.5-degree grid in `target-grid.nc`; a target cell is supported when every CHIRPS cell inside it is observed in every training season. Aggregating the 0.05-degree field to the target grid is open: an area-conservative mean and a bilinear interpolation at the cell centre are both the centre's practice; sampling a single source cell is not.
- **Sea-surface temperature.** ERSST v5 monthly SST for the training index; the CFSv2 ensemble-mean forecast SST for the target season, from the same initialization, for the forecast-year index.
- **Seasonal totals.** Where a model is served as a seasonal-mean rate, its seasonal total is that rate times the number of days in the season, using the calendar; where it is served as a season total, it is used as such.

## Categories

- Tercile boundaries per cell are the one-third and two-thirds quantiles of the training-year observed seasonal totals, by linear interpolation of the ordered sample. An observation within one millionth of a millimetre (1e-6 mm) of a boundary is near normal; the centre adopted this margin because CHIRPS repeats identical seasonal totals across years in dry cells, so boundaries often fall exactly on observed values.
- For any historical year the boundaries, and every fitted quantity, are computed without that year's observation (leave-one-year-out). The forecast year uses all training years.

## Stream 1: WVG

- The Western-V Gradient index is the standardized Nino 3.4 mean minus the average of the standardized West North Pacific and West Equatorial Pacific means. The boxes are Nino 3.4: 5S–5N, 190–240E; WNP: 20–35N, 160–210E; WEP: 15S–20N, 120–160E. A box mean is the plain mean of the ocean grid cells inside the box. Each box mean is standardized over the training years.
- Training index: the observed target-season mean SST per training year. Forecast-year index: the CFSv2 ensemble-mean forecast SST for the target season, standardized against CFSv2's own hindcast climatology of the same box, initialization and season over the training years.
- Per cell, the probability of below-normal rainfall is a logistic regression of the below-normal indicator on the index, fitted by unpenalized maximum likelihood. Where the index perfectly separates the below-normal years from the others, the probability is the limiting step function with its step midway between the nearest years of each class.
- The centre fixes the near-normal probability at one third and gives the remainder to above normal; when below normal exceeds two thirds the remainder goes to near normal instead.

## Stream 2: eReg

- Per model and cell, observed seasonal rainfall is regressed on the model's ensemble-mean seasonal total by ordinary least squares with an intercept. The forecast distribution is Gaussian about the fitted value with the residual variance; whether the variance is inflated for the uncertainty of the fitted line (prediction-error variance) or left as the residual variance is open.
- Tercile probabilities come from that distribution at the cell's boundaries. The models' probabilities are averaged with equal weight.

## Stream 3: CCA

- Per model, a canonical correlation analysis relates the model's ensemble-mean seasonal rainfall field over the served domain (predictor) to the observed seasonal rainfall on the supported target cells (predictand). Fields are centred, standardized per grid point and weighted by the square root of the cosine of latitude.
- The numbers of predictor EOF modes (one to eight), predictand EOF modes (one to six) and canonical modes (one to three) are chosen per model by cross-validated skill over the training years; the selection rule's skill measure is open. The centre's CPT configuration applies a gamma transformation to the predictand; applying it is open.
- Forecast uncertainty per cell is a Student-t distribution about the predicted value with the cross-validated residual variance, inflated for the prediction, and degrees of freedom reduced by the predictor modes. Tercile probabilities come from that distribution. The models' probabilities are averaged with equal weight.

## Combination, verification and issue

- The objective forecast is the equal-weight average of the three streams' probabilities at every supported cell.
- Verification uses the ranked probability score of the leave-one-year-out hindcasts against the observed categories, per stream and for the objective, and the skill score against the equal-thirds climatology, averaged without weights over supported cells.
- The issued outlook is the objective forecast for the forecast year; the dominant category is the most probable one, with ties to near normal.
