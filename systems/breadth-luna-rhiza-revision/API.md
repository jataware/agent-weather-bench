Rhiza provides installed weather skills under `/catalog/skills/weather-skills`. Read the relevant `SKILL.md` and script `--help`; run scripts with **python**, because dependencies are already installed and the runtime is offline.

For cumulative precipitation amounts on a forecast `step` axis, the documented deaccumulation entry point is:

```
python /catalog/skills/weather-skills/deaccumulate/scripts/deaccumulate.py --help
python /catalog/skills/weather-skills/deaccumulate/scripts/deaccumulate.py -i INPUT.zarr -o RATES.zarr -v tp
```

The installed skill calls the public core helper:

```python
from weather_skills_core.units import deaccumulate_along_step
rates = deaccumulate_along_step(dataset, names=["tp"])
```

This helper differences consecutive cumulative values along `step` and clips negative differences at zero. Precipitation amounts such as `kg m**-2`, `mm`, or `m` become **rates in mm day-1**, divided by each interval duration. The first step is dropped; remaining coordinates label the interval's ending step. Preserve the issue time when converting lead steps to valid times. A rate multiplied by its duration in days gives an interval amount in mm; a rate is not already an amount unless its interval is exactly one day. Read actual metadata rather than assuming native step spacing or units. Do not deaccumulate products that are already rates; the CLI rejects rate/flux metadata. The clipping behavior is part of this helper, so assess whether it matches the scientific job before choosing it.

The standalone CLI accepts Zarr inputs with either consolidated or ordinary metadata, stamps output history, and preserves the variable/dimension labels. The direct helper operates on an xarray Dataset; output schema and attributes should still be inspected. The generic `synthetic_deaccumulation.py` demonstrates irregular intervals, depth units and the clipping behavior on invented numbers. It contains no task inputs, regional calculations, forecasts or task answers.

Other skills such as aggregation and unit conversion have their own input contracts. Their presence does not imply that default window labels, bins or regional boundaries match a task. General scientific Python remains available for operations the selected skill does not cover.
