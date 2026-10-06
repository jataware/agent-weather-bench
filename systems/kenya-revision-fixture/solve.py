"""Control solution for certification: a third, plain xarray implementation.

`variant.json` beside this file switches on one deliberate deviation at a time.
With no variant file this is a known-correct solution.
"""
import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import xarray as xr

HERE = Path(__file__).resolve().parent
DAY = np.timedelta64(1, "D")


def weekly_means(inputs, issue, starts, box, variant):
    ds = xr.open_zarr(Path(inputs) / f"ECMWF_s2s_precip_{issue}.zarr", chunks=None, consolidated=False)
    lat, lon = ds.latitude, ds.longitude
    if variant.get("exclusive_boundary"):
        inside = (lat > box["south"]) & (lat < box["north"]) & (lon > box["west"]) & (lon < box["east"])
    else:
        inside = (lat >= box["south"]) & (lat <= box["north"]) & (lon >= box["west"]) & (lon <= box["east"])
    rain = ds.tp.astype("float64").where(inside, drop=True).swap_dims(step="valid_time")
    if variant.get("sum_cumulative"):
        daily = rain
    else:
        daily = rain.diff("valid_time")               # each value is labelled with the day it ends on
        if not variant.get("keep_negative"):
            daily = daily.clip(min=0)
    weeks = []
    for start in starts:
        first = np.datetime64(start, "ns") - (DAY if variant.get("shift_window") else 0 * DAY)
        weeks.append(daily.sel(valid_time=slice(first + DAY, first + 7 * DAY)).sum("valid_time").mean("number"))
    return xr.concat(weeks, "period")


def solve(inputs, variant):
    """(labelled arrays, the rest of the answer)."""
    params = variant.get("hardcode_instance") or json.loads((Path(inputs) / "instance.json").read_text())
    box, starts = params["rectangle"], [np.datetime64(s, "D") for s in params["period_start"]]
    gap = np.datetime64(params["issue_current"], "D") - np.datetime64(params["issue_previous"], "D")
    current = weekly_means(inputs, params["issue_current"], starts, box, variant)
    previous = weekly_means(inputs, params["issue_previous"], [s - gap for s in starts] if variant.get("same_lead") else starts, box, variant)
    change = current - previous
    if variant.get("unweighted"):
        regional = change.mean(("latitude", "longitude"))
    else:
        regional = change.weighted(np.cos(np.deg2rad(change.latitude))).mean(("latitude", "longitude"))
    named = {"current_mean_mm": current, "previous_mean_mm": previous, "change_mm": change, "regional_change_mm": regional}
    arrays = xr.Dataset({name: array.reset_coords(drop=True) for name, array in named.items()})     # keep only the dimension labels
    arrays = arrays.assign_coords(period=np.array(starts, dtype="datetime64[ns]"))
    if variant.get("rearranged"):                     # another order of dimensions and of labels holds the same information
        arrays = arrays.sortby("latitude").isel(period=slice(None, None, -1)).transpose("longitude", "latitude", "period")
    direction = {str(label)[:10]: "wetter" if value > 0 else "drier" for label, value in zip(arrays.period.values, arrays.regional_change_mm.values)}
    if variant.get("wrong_claims"):
        direction = {label: "drier" if value == "wetter" else "wetter" for label, value in direction.items()}
    return arrays, {"choices": {"negative daily increments": "kept" if variant.get("keep_negative") else "set to zero",
                                "regional mean": "plain mean" if variant.get("unweighted") else "cosine-latitude weights"},
                    "claims": {"direction": direction},
                    "run": {"argv": ["python", "solve.py", "--inputs", "{input_dir}", "--output", "{output_dir}"]}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    variant = json.loads((HERE / "variant.json").read_text()) if (HERE / "variant.json").is_file() else {}
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    arrays, answer = solve(args.inputs, variant)
    shutil.rmtree(output / "results.zarr", ignore_errors=True)
    arrays.to_zarr(output / "results.zarr", mode="w", zarr_format=3, consolidated=False)
    (output / "answer.json").write_text(json.dumps(answer, allow_nan=False) + "\n")
