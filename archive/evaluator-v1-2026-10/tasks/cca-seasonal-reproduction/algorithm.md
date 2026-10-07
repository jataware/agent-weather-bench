# Frozen curator algorithm: a bounded CPT-inspired method adaptation

This reconstructs the training-only multivariate EOF/CCA component on new real
East African OND rainfall and antecedent SST data. It does not reproduce a
published skill result, a complete centre outlook, or exact CPT binary output.
The cited code's claims of parity are source claims, not our independent evidence.

Inputs: 27 SST grid cells, June–August arithmetic monthly means, 1993–2023;
12 native land rainfall cells, true OND totals in mm, 1993–2019. September30 is
the notional issue, observed SST cutoff August31. Supplied final-vintage reanalysis
and CHIRPS imply retrospective forecasting, not strict historical real-time data
availability. Four 2020–2023 targets remain controller-only.

For every fit use only that fit's training years. Center each column, divide by
sample standard deviation (ddof1), then multiply by sqrt(cos(latitude)). Thin
SVD gives A=Ux diag(sx) Vx.T, B=Uy diag(sy) Vy.T. Retain a predictor EOFs and b
target EOFs. Canonical SVD of Ux.T Uy = Q diag(rho) R.T retains c components.
A new weighted/standardized predictor row z predicts target anomalies as
(z Vx / sx) Q_c diag(rho_c) R_c.T diag(sy) Vy.T; undo target latitude weights
and sample standard deviation, add training mean. No clipping or detrending.
EOF/canonical signs and equivalent rotations are arbitrary; compare resulting
predictions and probabilities, not loadings. Never borrow an EOF basis from an
outer target or its future.

Candidate configurations enumerate a=1,2,3; b=1,2,3; c=1..min(a,b) in that order,
IDs starting0 (14 candidates). For an outer held year2005..2019, train1993 through
previous year. For each candidate, inner expanding holdouts2001 through last
training year fit all earlier years, recomputing all transforms. Score each case
by target-cell MSE standardized using that inner training target sample std,
weighted by normalized cos(target latitude); average equally over inner years.
Choose minimum loss, ties smallest ID. Final selection uses1993–2019 with inner
holdouts2001–2019. The fixed comparator is(1,1,1).

For probability uncertainty, refit the selected configuration leaving out each
training year; squared deterministic residuals sum per target, divided by
n-a-1. These are training-local LOO residuals, not claimed unbiased nested outer
scores. Fit selected configuration on the complete available training set.
Leverage is 1/n + SUM OF SQUARED retained canonical projections, before rho;
projections are (z Vx / sx) Q_c. This rotation-invariant convention deliberately
differs from the cited CPT squared SUM and is a curator adaptation. Scale is
sqrt(residual variance*(1+leverage)), Student-t df=n-a-1. This is a specified
working predictive model, not a proof of calibrated probabilities.

Thresholds at p1/3 and2/3 use sorted training targets, rank r=n*p+.5. Let j=floor(r),
f=r-j: interpolate (1-f)*sorted[j-1]+f*sorted[j] with zero-based indexing.
All current n ensure interior ranks. Pbelow=tCDF((threshold1-mean)/scale);
Pnear=CDF2-CDF1; Pabove=1-CDF2. Climatology uses probabilities1/3 and training
mean predictions. RPS is mean squared cumulative probability error across the
first two boundaries, observations strictly less than thresholds. Near includes
exact threshold1; above includes exact threshold2. Report pooled RPSS =
1 - sum_year,target(coslat*model RPS)/sum_year,target(coslat*climatology RPS).

Finally fit all1993–2019 years. Predict2020–2023 with this frozen fitted state.
Also apply that production nested model to2005–2019 and export explicitly named
full_fit_prediction/full_fit_probability diagnostic arrays. These overlap fit
and must not be presented as cross-validated skill. The PyCPT excerpt shows why
a deterministic CV field alone does not establish independence of its separate
probabilistic route. Discuss the difference using actual supplied source lines.
