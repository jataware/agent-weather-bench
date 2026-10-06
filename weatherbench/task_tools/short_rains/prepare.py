"""Freeze compact real source data and independent controller references.

Initial construction: python -m weatherbench.task_tools.short_rains.prepare --source-root ..
Subsequent invocations verify existing bytes and recompute references; no source
checkout is needed once the compact inputs are present.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import xarray as xr

from .reference import CANDIDATES, build

TASK = "short-rains-workflow"
REGIONS = {"somalia": [-1.7, 12.0, 41.0, 51.4], "kenya": [-4.7, 5.0, 33.9, 41.9], "eastern-horn": [-4.5, 8.5, 38.0, 50.5]}
BOXES = ("nino34", "iod_w", "iod_e", "wpac", "wv")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_frozen(path, content):
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f"Frozen file differs: {path}; create a new task version")
    else:
        path.write_bytes(content)


def initial_sources(repo, source):
    inputs = repo / "var/private/tasks" / TASK / "agent-inputs"
    controller = inputs.parent / "controller"
    material = repo / "tasks" / TASK / "source-material"
    for d in (inputs, controller, material):
        d.mkdir(parents=True, exist_ok=True)
    source_data = source / "v4zeek/data"
    original = xr.open_dataset(source_data / "ea_precip_monthly.nc").precip
    series = []
    for name, (s, n, w, e) in REGIONS.items():
        crop = original.sel(lat=slice(s, n), lon=slice(w, e))
        # Independent audit computes explicit weighted sums and checks all months.
        ser = crop.weighted(np.cos(np.deg2rad(crop.lat))).mean(("lat", "lon"))
        series.append(ser.expand_dims(region=[name]))
    rainfall = xr.concat(series, dim="region").transpose("time", "region").rename("monthly_rainfall_scaled")
    rainfall.attrs = {"units": "legacy_scaled_monthly_total", "normalization": "native CHIRPS monthly total divided by 30.0 by old acquisition adapter; not a calendar-aware daily rate"}
    rainfall.sel(time=slice("1993-01-01", "2019-12-31")).to_dataset().to_netcdf(inputs / "rainfall.nc")
    private_rain = rainfall.sel(time=slice("2020-01-01", "2023-12-31")) * 30
    private_rain.attrs = {"units":"mm", "processing":"legacy normalized values multiplied by 30.0 to undo acquisition conversion"}
    private_rain.to_dataset(name="monthly_total").to_netcdf(controller / "private-targets.nc")
    ss = []
    for box in BOXES:
        da = xr.open_dataset(source_data / f"sst_{box}_monthly.nc").sst
        ser = da.weighted(np.cos(np.deg2rad(da.lat))).mean(("lat", "lon"))
        ss.append(ser.expand_dims(box=[box]))
    sst = xr.concat(ss, dim="box").transpose("time", "box").rename("sst")
    sst.attrs = {"units": "degree_Celsius", "processing": "cosine-weighted means over source retrieval boxes; raw, not anomalies; this task does not claim exact standard index geometry"}
    sst.to_dataset().to_netcdf(inputs / "sst.nc")
    gcm = xr.open_dataset(source_data / "gcm_iod_ond.nc").load()
    gcm.gcm_iod.attrs = {"units": "K", "initialization_month": 9, "target_months": "10,11,12", "processing": "raw west minus east SST, spatial, member and target-lead means; no anomaly correction"}
    gcm.to_netcdf(inputs / "forecast-index.nc")
    originals = {
        "starting-bench.py.txt": source / "v4zeek/bench.py",
        "starting-search.py.txt": source / "v4zeek/candidates/search.py",
        "fetch-fixtures.py.txt": source / "v4zeek/src/fetch_fixtures.py",
        "fetch-forecast-index.py.txt": source / "v4zeek/src/fetch_gcm_index.py",
        "old-normalize.py.txt": source / "archive/legacy-libraries/rosetta/src/rosetta/normalize.py",
    }
    for dest, original_path in originals.items():
        content = original_path.read_bytes()
        write_frozen(material / dest, content)
        write_frozen(inputs / dest, content)
    catalog = source / "archive/legacy-libraries/rosetta/src/rosetta/catalog.yaml"
    text = catalog.read_text()
    start = text.index("obs/chirps-v3-monthly:")
    end = text.index("# Preliminary", start)
    write_frozen(material / "old-chirps-catalog.yaml.txt", text[start:end].encode())
    write_frozen(inputs / "old-chirps-catalog.yaml.txt", text[start:end].encode())
    records = {p.name: {"original": str(p.relative_to(source)), "sha256": digest(p)} for p in [source_data / "ea_precip_monthly.nc", source_data / "gcm_iod_ond.nc", *[source_data / f"sst_{b}_monthly.nc" for b in BOXES]]}
    write_frozen(material / "original-files.json", (json.dumps(records, indent=2) + "\n").encode())
    specs = [{"id": i, "feature": f, "gap": g, "width": w, "transform": t} for i, (f, g, w, t) in enumerate(CANDIDATES)]
    write_frozen(inputs / "candidates.json", (json.dumps(specs, indent=2) + "\n").encode())
    manifest = {"sources": ["v4zeek-workflow", "legacy-chirps-normalization", "chirps3", "era5-sst", "cansips-reforecasts", "frozen-literature"]}
    write_frozen(inputs / "source-manifest.json", (json.dumps(manifest, indent=2) + "\n").encode())
    write_frozen(inputs / "literature-notes.txt", (material / "literature-notes.txt").read_bytes())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    root = repo / "var/private/tasks" / TASK
    if args.source_root:
        if (root / "agent-inputs/rainfall.nc").exists():
            raise ValueError("Initial construction refused: inputs already frozen")
        initial_sources(repo, args.source_root.resolve())
    if not (root / "agent-inputs/rainfall.nc").exists():
        raise ValueError("Missing frozen inputs; initial construction needs --source-root")
    for name, ds in zip(("seasonal.nc", "hindcasts.nc", "forecast.nc"), build(root / "agent-inputs")):
        path = root / "controller" / name
        if path.exists():
            with xr.open_dataset(path) as frozen:
                xr.testing.assert_allclose(ds, frozen, rtol=1e-12, atol=1e-12)
        else:
            ds.to_netcdf(path)
    print("Frozen short-rains data and reference outputs prepared")


if __name__ == "__main__":
    main()
