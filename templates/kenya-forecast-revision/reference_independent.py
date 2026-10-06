"""Implementation B of the Kenya forecast revision reference.

Shares no code with reference.py and takes a different route at each step: it reads
the stores with zarr (no xarray decoding), places periods by valid date instead of
lead arithmetic, forms totals from cumulative end points, and averages with explicit
loops. Agreement between A and B over every convention is a certification test.
"""
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import zarr

UNIT_SECONDS = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400}


def decode_times(array):
    """CF 'units since epoch' numbers -> naive UTC datetimes, without xarray."""
    unit, _, origin = array.attrs["units"].partition(" since ")
    base = datetime.fromisoformat(origin.strip().replace("Z", "+00:00"))
    if base.tzinfo is not None:
        base = base.astimezone(timezone.utc).replace(tzinfo=None)
    return [base + timedelta(seconds=float(value) * UNIT_SECONDS[unit.strip()]) for value in np.atleast_1d(array[...]).tolist()]


def open_store(inputs, issue):
    group = zarr.open_group(Path(inputs) / f"ECMWF_s2s_precip_{issue}.zarr", mode="r")
    tp = group["tp"]
    names = list(tp.metadata.dimension_names)
    cube = np.moveaxis(np.asarray(tp[...], dtype="float64"), [names.index(n) for n in ("number", "step", "latitude", "longitude")], [0, 1, 2, 3])
    valid = decode_times(group["valid_time"])
    if tp.attrs["units"] != "kg m**-2" or valid[0].date().isoformat() != issue:
        raise ValueError("Unexpected store")
    return cube, [moment.date() for moment in valid], [float(v) for v in group["latitude"][...]], [float(v) for v in group["longitude"][...]]


def week_total(cube, dates, first_day, conventions, strict):
    """Rain falling on the seven civil days from first_day, for each member and cell.

    Cumulative value at date d is the rain up to 00 UTC on d. Rain during day d is
    therefore cumulative(d + 1) - cumulative(d).
    """
    if conventions["window_labels"] == "shifted_one_day_early":
        first_day = first_day - timedelta(days=1)
    index = {date: position for position, date in enumerate(dates)}
    if conventions["rainfall_semantics"] != "differenced_cumulative":
        chosen = [index[first_day + timedelta(days=k)] for k in range(1, 8) if first_day + timedelta(days=k) in index]
        if not chosen:
            raise ValueError("Period lies outside the forecast")
        return sum(cube[:, position] for position in chosen)
    days = [k for k in range(7) if first_day + timedelta(days=k) in index and first_day + timedelta(days=k + 1) in index]
    if strict and len(days) != 7:
        raise ValueError("Period is not fully covered by the forecast")
    if not days:
        raise ValueError("Period lies outside the forecast")
    begin, end = index[first_day + timedelta(days=days[0])], index[first_day + timedelta(days=days[-1] + 1)]
    total = cube[:, end] - cube[:, begin]                          # telescoped sum of the daily increments
    if conventions["negative_increments"] == "clipped":
        for position in range(begin, end):                         # add back each decrease that clipping removes
            step = cube[:, position + 1] - cube[:, position]
            total = total - np.where(step < 0, step, 0.0)
    return total


def answer(inputs, params, conventions):
    new_cube, new_dates, lats, lons = open_store(inputs, params["issue_current"])
    old_cube, old_dates, old_lats, old_lons = open_store(inputs, params["issue_previous"])
    if (lats, lons) != (old_lats, old_lons):
        raise ValueError("The two issues are on different grids")
    box = params["rectangle"]
    if conventions["boundary"] == "inclusive":
        keep_rows = [i for i, v in enumerate(lats) if box["south"] <= v <= box["north"]]
        keep_cols = [j for j, v in enumerate(lons) if box["west"] <= v <= box["east"]]
    else:
        keep_rows = [i for i, v in enumerate(lats) if box["south"] < v < box["north"]]
        keep_cols = [j for j, v in enumerate(lons) if box["west"] < v < box["east"]]
    if not keep_rows or not keep_cols:
        raise ValueError("Rectangle selects no grid cells")
    members = new_cube.shape[0]
    usual_window = conventions["window_labels"] == "end_labelled"
    aligned = conventions["issue_alignment"] == "same_valid_period"
    issue_gap = datetime.fromisoformat(params["issue_current"]).date() - datetime.fromisoformat(params["issue_previous"]).date()
    current, previous, change, regional = [], [], [], []
    for text in params["period_start"]:
        first_day = datetime.fromisoformat(text).date()
        new_total = week_total(new_cube, new_dates, first_day, conventions, usual_window)
        old_first = first_day if aligned else first_day - issue_gap     # same lead reuses the earlier issue's own offsets
        old_total = week_total(old_cube, old_dates, old_first, conventions, usual_window and aligned)
        new_map = [[math.fsum(new_total[m, i, j] for m in range(members)) / members for j in keep_cols] for i in keep_rows]
        old_map = [[math.fsum(old_total[m, i, j] for m in range(members)) / members for j in keep_cols] for i in keep_rows]
        delta = [[a - b for a, b in zip(row_new, row_old)] for row_new, row_old in zip(new_map, old_map)]
        numerator = denominator = 0.0
        for row, i in zip(delta, keep_rows):
            weight = math.cos(math.radians(lats[i])) if conventions["area_weighting"] == "cos_latitude" else 1.0
            numerator += weight * math.fsum(row) / len(row)
            denominator += weight
        current.append(new_map); previous.append(old_map); change.append(delta); regional.append(numerator / denominator)
    return {"period": np.array([str(text) for text in params["period_start"]]),
            "latitude": np.array([lats[i] for i in keep_rows]), "longitude": np.array([lons[j] for j in keep_cols]),
            "current_mean_mm": np.array(current), "previous_mean_mm": np.array(previous),
            "change_mm": np.array(change), "regional_change_mm": np.array(regional)}
