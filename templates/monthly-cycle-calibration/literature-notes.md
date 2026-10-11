# Attributed methodological context and boundaries

Kharin, Merryfield, Boer and Lee(2017), *A Postprocessing Method for Seasonal
Forecasts Using Temporally and Spatially Smoothed Statistics*, Monthly Weather
Review145,3545–3561, [doi10.1175/MWR-D-16-0337.1](https://doi.org/10.1175/MWR-D-16-0337.1).
The publisher's abstract and introductory method description support the idea
that sharing adjustment information across neighboring seasons can reduce
sampling error. Their experiment uses CanSIPS seasonal hindcasts initialized in
all twelve months; their temporal filter is Gaussian and their reported scores
belong to that original experiment. We have not reproduced those scores or
downloaded its complete hindcast data. This task uses observed antecedent SST
and monthly rainfall, and its cyclic quadratic-penalty smoother is a curator
adaptation. It need not improve prediction here.

The public [AfricaS2S repository](https://github.com/ACMAD-Niamey/africas2s),
revision4f8526a32232f9c9af400a01e5a6f103a865c735, supplied additional
methodological context. This task's fixed adaptation is defined in algorithm.md;
no curator-selected library source excerpt or function guide is supplied.

Data context: [CHIRPSv3](https://chc.ucsb.edu/data/chirps3) and
[ERA5 monthly means](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-monthly-means).
Native weather arrays come from the existing source workflow and are hashed in
`source-material/original-files.json`. Rainfall legacy normalization is undone
before task supply. The predictor retrieval boxes are source boxes, not a claim
of exact standard DMI geometry. Retrospective public sources may already be known
to models. Controller-private outcomes are excluded from agent fitting but are
not pristine historical observations.
