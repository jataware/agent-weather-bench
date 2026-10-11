"""Independent scalar implementation: no imports from the primary science code.

Uses explicit pixel membership, scalar spherical areas, Python sorted pairs and
bisect interpolation. Training exclusion is rebuilt separately for every year.
"""
import bisect
import math
from pathlib import Path

import numpy as np
import xarray as xr


def reference(inputs, params, conventions):
    with xr.open_dataset(Path(inputs) / "fine-training.nc") as file:
        data = file.load()
    with xr.open_dataset(Path(inputs) / "coarse-forecast.nc") as file:
        model = file.load()
    lat, lon, years = data.lat.values, data.lon.values, data.year.values
    observations = np.asarray(data.seasonal_total, dtype=float)
    area = np.empty((len(lat), len(lon)))
    membership = np.empty(area.shape, dtype=int)
    pixels = [[] for _ in range(4)]
    for i, latitude in enumerate(lat):
        for j, longitude in enumerate(lon):
            area[i, j] = 6371000.0 ** 2 * math.radians(0.05) * (math.sin(math.radians(latitude + 0.025)) - math.sin(math.radians(latitude - 0.025)))
            cell = (0 if latitude < 1.5 else 2) + (0 if longitude < 37.5 else 1)
            membership[i, j] = cell
            pixels[cell].append((i, j))
    coarse = np.empty((len(years), 4))
    for c, support in enumerate(pixels):
        denominator = sum(area[i, j] for i, j in support)
        for t in range(len(years)):
            coarse[t, c] = sum(observations[t, i, j] * area[i, j] for i, j in support) / denominator
    raw = np.asarray(model.raw_predictor.sel(year=years))

    def prediction(keep, new):
        climatology = observations[keep].mean(axis=0)
        mapped = np.empty((len(new), 4))
        fine = np.empty((len(new), len(lat), len(lon)))
        for c, support in enumerate(pixels):
            ordered_x = sorted(float(v) for v in raw[keep, c])
            ordered_y = sorted(float(v) for v in coarse[keep, c])
            unique, targets = [], []
            start = 0
            while start < len(ordered_x):
                stop = start + 1
                while stop < len(ordered_x) and ordered_x[stop] == ordered_x[start]:
                    stop += 1
                unique.append(ordered_x[start])
                targets.append(sum(ordered_y[start:stop]) / (stop - start))
                start = stop
            mean = sum(climatology[i, j] * area[i, j] for i, j in support) / sum(area[i, j] for i, j in support)
            for t in range(len(new)):
                value = float(new[t, c])
                index = bisect.bisect_right(unique, value)
                if index == 0:
                    mapped[t, c] = targets[0]
                elif index == len(unique):
                    mapped[t, c] = targets[-1]
                else:
                    fraction = (value - unique[index - 1]) / (unique[index] - unique[index - 1])
                    mapped[t, c] = targets[index - 1] + fraction * (targets[index] - targets[index - 1])
                for i, j in support:
                    fine[t, i, j] = mapped[t, c] * climatology[i, j] / mean
        return fine, mapped

    hindcast, hindcoarse = [], []
    for t in range(len(years)):
        keep = list(range(len(years))) if conventions["validation"] == "full_training" else [i for i in range(len(years)) if i != t]
        fine, mapped = prediction(keep, raw[t:t + 1])
        hindcast.append(fine[0]); hindcoarse.append(mapped[0])
    forecast, forecast_coarse = prediction(list(range(len(years))), np.asarray(model.raw_predictor.sel(year=params["forecast_years"])))
    return {"train_year": years, "forecast_year": np.array(params["forecast_years"]), "latitude": lat, "longitude": lon, "coarse_cell": np.arange(4),
            "hindcast_mm": np.array(hindcast), "hindcast_coarse_mm": np.array(hindcoarse), "forecast_mm": forecast, "forecast_coarse_mm": forecast_coarse,
            "area_m2": area, "coarse_cell_id": membership}
