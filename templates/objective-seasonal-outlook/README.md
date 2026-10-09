# Objective seasonal outlook: a long-horizon composition task

The agent receives a forecaster's job (`brief.md`), the centre's practice in words (`practice.md`), a target grid and a frozen source service, and must deliver every stage of the regional objective seasonal rainfall outlook: acquire, prepare, WVG, eReg, CCA, combine, verify, issue. The design record is `designs/objective-seasonal-outlook.md`.

- Source snapshot: acmadDL deliveries (NMME seasonal precipitation for four centres, CFSv2 SST, CHIRPS 0.05-degree monthly, ERSST v5), frozen by `freeze_source.py` from the local acmadDL cache and small acmadDL fetches. The withheld year's observations are controller-private.
- Deciding implementation: `science.py` (NumPy, SciPy, xarray). Independent implementation: `reference_independent.py`. Neither imports a forecasting library.
- Stage arrays carry their stage prefix. `prepare_*`, `wvg_*` and `ereg_*` are reference-matched; `cca_*`, `combine_*`, `verify_*` and `issue_*` are free and are checked by invariants that recompute them from the submission's own upstream arrays (the local verdict) and, for CCA, by agreement with the controller's CCA.

Start with the known-correct control:

```
.venv/bin/python -m assessment assess objective-seasonal-outlook gha--mam-2015 --control correct --local-trusted
```
