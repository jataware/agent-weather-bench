# Combine probability forecasts

Run `python /substrate/synthetic_combination.py` for a small offline example
using invented data. It demonstrates the installed public API, not a task solver.

```python
from africas2s import combine_terciles

equal = combine_terciles(components, missing="drop", renormalize=True)
weighted = combine_terciles(components, weights=weights,
                            missing="drop", renormalize=True)
```

`components` is a list or name-to-DataArray dictionary. Each array contains
fractional probabilities with dimensions `tercile, lat, lon` and tercile labels
`[0, 1, 2]` for below, normal, above. Convert percentages to fractions first.
The helper combines complete distributions, renormalizes weights among components
present at each cell, and normalizes the final tercile vector. A partially NaN
distribution is absent as a whole. Clean other nonfinite values before calling.
Explicit weights may be a list or a dictionary matching the component names.

All-absent cells return NaN, meaning no forecast. Preserve that distinction.
If a delivery format needs finite storage fills, retain a separate support mask
or count and fill only unsupported cells; interpret those fills through the mask.
The helper does not calculate support counts or component disagreement for you.
Its default target grid is the first component's grid; check coordinate alignment
and avoid unintended interpolation when a task requires preserving a source grid.

Use the returned fields in your submitted calculation and cite the call sites
in `report.md`. Retrieval, metadata interpretation, additional diagnostics and
artifact packaging remain your work. Use serial scientific file I/O.
