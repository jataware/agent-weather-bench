# Frozen monthly-cycle curator algorithm

This is statistical monthly rainfall forecasting from prior observed SST,
inspired by seasonal-cycle information sharing. It is not dynamical-hindcast
postprocessing or replication of Kharin's CanSIPS experiment. We deliberately use
standardized slopes and a cyclic quadratic penalty rather than the source paper's
Gaussian filter on its forecast adjustment coefficients. All curator choices are
fixed below; do not infer undocumented paper equivalence.

Input targets: three actual cosine-weighted CHIRPS regional monthly totals, mm, all calendar
months for complete years 1993–2019. Input predictor: raw west-minus-east SST
retrieval-box means, degree Celsius, from the previous calendar month for every
target month 1993–2023. January uses previous December. These are already supplied;
no unavailable target-month SST or observed rainfall is a predictor. The monthly
issue is day1 of the target month in this retrospective experiment. Final-vintage
ERA5 prior-month averages may not have been published by that historical issue;
this is a retrospective availability assumption, not strict real-time fidelity.

For each fit, take only its complete training-year blocks. Compute per-calendar-
month predictor means/sample standard deviations and per-month, per-region target
means/sample standard deviations (ddof1). Standardize both. A monthly independent
slope is raw_beta[m,t] = sum_training(zx[year,m]*zy[year,m,t])/(n-1).
For lambda in[0,.25,1,4,16,64], solve

    (I + lambda*L) beta = raw_beta
    L[m,m]=2; L[m,(m-1)mod12]=-1; L[m,(m+1)mod12]=-1.

This minimizes sum_training,months((zy-beta*zx)^2)/(n-1) +
lambda*sum_months((beta[m]-beta[m-1])^2), separately for each target region.
January and December are adjacent. No smoothing of targets, future climatology,
spatial neighbors or fitted target means is permitted. Lambda0 reproduces
independent monthly slopes. The constant comparator uses mean_month(raw_beta),
which is also the pooled slope of standardized monthly samples (equal years per
month), not a pooled physical-unit slope. Prediction is training_ymean[m,t] +
training_ystd[m,t]*beta[m,t]*(new_x[m]-training_xmean[m])/training_xstd[m].
Physical coefficient is beta*ystd/xstd; never clip negative predicted rainfall.
Negative predictions are a limitation to discuss, not a reason to silently alter
the prescribed forecast model.

Outer forecasts hold out entire target years 2005–2019 and fit years 1993 through
previous year. For every lambda, inner complete-year holdouts2001 through the
last outer training year each fit all earlier years. Recompute every mean,
scale, slope and smoother in each inner fold. Inner loss: squared forecast error
divided by that inner-fit target variance, average over twelve months and inner
years, and equal average over the three target regions.
One global lambda is chosen for the whole twelve-month/target-region field.
Candidate IDs follow the listed lambda order; ties choose smallest ID.
Production selects with training1993–2019, inner holds2001–2019, then fits all
1993–2019 once. Saved inference predicts2020–2023 without target observations,
refitting or new selection. Both fixed comparators use the same fit-only moments.

Systems in fixed order: climatology, independent-month, constant-slope,
nested-cyclic. Climatology predicts the training-only month/region mean.
Squared error is physical mm². Monthly MSSS =1 - equally region-weighted summed model squared
error / corresponding climatology error, summed across outer years and regions.
Overall MSSS uses all months as well, with equal month/year weights and
equal region weights. Thus rainy months can dominate overall physical-error
skill; report monthly skill alongside it. Positive improvement is not required.
Zero climatology skill follows exactly. Use paired whole-year uncertainty if
reporting inference;36 month-region cases per year are not independent samples.
