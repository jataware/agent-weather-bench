Reproduce the specified CPT-inspired seasonal CCA adaptation in `algorithm.md`,
using the supplied real antecedent SST predictors and East African OND rainfall.
The target cells have been restricted to {region}. Produce expanding outer
hindcasts for {outer_start}–2019, compare climatology, fixed CCA and nested
configuration selection, then forecast 2020–2023 from the frozen 1993–2019 fit.

Deliver every named array, dimension and unit in the algorithm's submission
table, in `results.zarr`. Include the candidate losses and selected IDs, tercile
probabilities, pooled outer RPSS, and the explicitly labelled overlapping
full-fit diagnostics. EOF signs are arbitrary; reproduce predictions rather
than loadings.

In `answer.json`, give one-element claim lists `nested_beats_fixed` (`yes` or
`no`, according to the outer RPSS comparison) and `full_fit_is_independent`
(`yes` or `no`). Explain validation scope and source limitations in `report.md`.
Distinguish this specified adaptation from exact CPT binary parity. Retain code
that regenerates the complete experiment from supplied inputs.
