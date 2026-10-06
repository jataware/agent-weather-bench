"""Implementation B of the weeks 3-4 rainfall metric and climatology baseline.

Shares no code with reference.py: it reads the source with netCDF4, selects the
splits with Python dates, fits the climatology through the normal equations one
cell at a time, and accumulates the weighted error in scalar loops.
"""
import math
from datetime import date, timedelta
from pathlib import Path

import netCDF4
import numpy as np


def _dates(variable):
    unit, _, origin = variable.units.partition(" since ")
    base = date.fromisoformat(origin.strip()[:10])
    step = {"days": 1.0, "hours": 1 / 24, "seconds": 1 / 86400}[unit.strip()]
    return [base + timedelta(days=round(float(value) * step)) for value in variable[:]]


def _design(day):
    angle = 2 * math.pi * (day.timetuple().tm_yday + 14) / 365.25
    return [1.0, math.sin(angle), math.cos(angle), math.sin(2 * angle), math.cos(2 * angle)]


def score(results, params, private, split="final"):
    with netCDF4.Dataset(Path(private) / "source-subset.nc") as nc:
        issues, starts = _dates(nc["issue_time"]), _dates(nc["target_start"])
        lat, lon = [float(v) for v in nc["latitude"][:]], [float(v) for v in nc["longitude"][:]]
        rain, model = np.asarray(nc["precipitation"][:], dtype="float64"), np.asarray(nc["raw_cfsv2"][:], dtype="float64")
    cells = [j for j in range(len(lat)) if params["longitude_limit"] is None or lon[j] <= params["longitude_limit"]]
    first, second, third = (date.fromisoformat(params[key]) for key in ("training_boundary", "development_boundary", "final_boundary"))
    closes = [start + timedelta(days=14) for start in starts]
    train_rows = [i for i in range(len(issues)) if closes[i] < first]
    if split == "development":
        rows = [i for i in range(len(issues)) if issues[i] >= first and closes[i] < second]
    else:
        rows = [i for i in range(len(issues)) if second <= issues[i] < third]
    forecast = np.asarray(results[f"{split}_mm"], dtype="float64")
    if forecast.shape != (len(rows), len(cells)):
        raise ValueError("Forecast does not cover the split")
    design = np.array([_design(issues[i]) for i in train_rows])
    gram = design.T @ design
    totals = {"forecast": 0.0, "raw": 0.0, "climatology": 0.0}
    weight_sum = 0.0
    for column, j in enumerate(cells):
        weight = math.cos(math.radians(lat[j]))
        weight_sum += weight
        beta = np.linalg.solve(gram, design.T @ rain[train_rows, j])
        for row, i in enumerate(rows):
            seasonal = max(float(np.dot(_design(issues[i]), beta)), 0.0)
            truth = rain[i, j]
            totals["forecast"] += weight * (forecast[row, column] - truth) ** 2
            totals["raw"] += weight * (model[i, j] - truth) ** 2
            totals["climatology"] += weight * (seasonal - truth) ** 2
    rmse = {name: math.sqrt(value / (len(rows) * weight_sum)) for name, value in totals.items()}
    return {"split": split, "rmse_mm": rmse["forecast"], "raw_model_rmse_mm": rmse["raw"], "climatology_rmse_mm": rmse["climatology"],
            "skill_vs_raw_model": 1 - rmse["forecast"] / rmse["raw"], "skill_vs_climatology": 1 - rmse["forecast"] / rmse["climatology"],
            "issues": len(rows), "cells": len(cells), "observations_are_public_history": True}
