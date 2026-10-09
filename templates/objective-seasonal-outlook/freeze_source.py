"""Freeze the acmadDL deliveries the objective seasonal outlook is built from.

Inputs come from a staging directory: NetCDF files written by `acmaddl.fetch` for the
NMME precipitation products and CFSv2 SST at both initializations, plus NetCDF
conversions of the acmadDL raw cache for CHIRPS v2.0 monthly (0.05 degree) and ERSST v5.
Nothing is downloaded here. The withheld year's months are removed from the two
observation files and kept controller-private. Values are otherwise unchanged.

    .venv/bin/python templates/objective-seasonal-outlook/freeze_source.py --staging DIR

An existing manifest (sources.json) is verified and never replaced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import xarray as xr

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DEST = ROOT / "var/private/templates/objective-seasonal-outlook"
WITHHELD_YEAR = 2015
LAYOUT = {  # staging file -> provider path
    "ccsm4-iri_precip_init{init}.nc": "models/ccsm4/precip_init{init}.nc",
    "geoss2s-hindcast_precip_init{init}.nc": "models/geoss2s/precip_init{init}.nc",
    "cansipsic4-hindcast_precip_init{init}.nc": "models/cansipsic4/precip_init{init}.nc",
    "cfsv2_precip_init{init}.nc": "models/cfsv2/precip_init{init}.nc",
    "cfsv2_sst_init{init}.nc": "sst/cfsv2/sst_init{init}.nc",
}
OBSERVATIONS = {"chirps-v2p0-monthly-0p05.nc": ("observations/chirps-v2p0-monthly-0p05.nc", "precip"),
                "ersst-v5-monthly.nc": ("observations/ersst-v5-monthly.nc", "sst")}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def describe(path):
    with xr.open_dataset(path) as ds:
        var = next(iter(ds.data_vars))
        out = {"variable": var, "sizes": dict(ds[var].sizes), "units": ds[var].attrs.get("units"), "coordinates": {}}
        for name in ds[var].dims:
            values = ds[name].values
            first, last = (str(values[0])[:10], str(values[-1])[:10]) if values.dtype.kind == "M" else (float(values[0]), float(values[-1]))
            out["coordinates"][name] = {"first": first, "last": last, "n": int(values.size)}
        values = ds[var].values
        finite = values[np.isfinite(values)]
        out["finite"], out["total"] = int(finite.size), int(values.size)
        out["min"], out["max"] = (float(finite.min()), float(finite.max())) if finite.size else (None, None)
    return out


def split_withheld_year(raw, variable, provider_path, private_path):
    with xr.open_dataset(raw) as ds:
        ds = ds.load()
    year = ds["time"].dt.year.values
    keep, drop = np.flatnonzero(year != WITHHELD_YEAR), np.flatnonzero(year == WITHHELD_YEAR)
    if len(drop) != 12:
        raise ValueError(f"Expected twelve withheld months, found {len(drop)}")
    encoding = {variable: {"zlib": True, "complevel": 4}}
    for subset, path, note in ((keep, provider_path, "removed"), (drop, private_path, "only")):
        part = ds.isel(time=subset)
        part.attrs = dict(ds.attrs, curator_note=f"Months of {WITHHELD_YEAR} {note}; values unchanged.")
        path.parent.mkdir(parents=True, exist_ok=True)
        part.to_netcdf(path, engine="netcdf4", encoding=encoding)
    return {"kept_months": int(len(keep)), "withheld_months": int(len(drop))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path)
    parser.add_argument("--dest", type=Path, default=DEST)
    args = parser.parse_args()
    manifest_path = HERE / "sources.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        for row in manifest["files"]:
            path = args.dest / row["file"]
            if not path.is_file() or digest(path) != row["sha256"]:
                raise ValueError(f"Frozen source changed or absent: {path}")
        print(f"Existing frozen source verified: {len(manifest['files'])} files unchanged.")
        return
    if args.staging is None:
        raise ValueError("Pass --staging with the acmadDL staging directory")
    dest, staging = args.dest, args.staging
    if dest.exists() and any(dest.iterdir()):
        raise ValueError(f"Refusing to write into a nonempty snapshot directory: {dest}")
    provider, private, records_dir = dest / "provider", dest / "private-targets", dest / "private-source-records"
    fetch_log = json.loads((staging / "fetch-log.json").read_text())
    convert_log = json.loads((staging / "convert-log.json").read_text())
    records = []
    for init in ("02", "08"):
        for pattern, target in LAYOUT.items():
            source = staging / pattern.format(init=init)
            if not source.is_file():
                raise ValueError(f"Staging lacks {source.name}")
            path = provider / target.format(init=init)
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, path)
            fetch = next((row for row in fetch_log if row["file"] == source.name), None)
            if fetch is None or fetch.get("status") != "ok":
                raise ValueError(f"No successful fetch record for {source.name}")
            records.append({"path": str(path.relative_to(provider)), "kind": "acmaddl_fetch", "product": fetch["product"], "variable": fetch["variable"],
                            "init_month": fetch["init_month"], "target": fetch["target"], "region": fetch["region"], "hindcast": fetch["hindcast"],
                            "sha256": digest(path), "decoded": describe(path)})
    for source_name, (target, variable) in OBSERVATIONS.items():
        source = staging / source_name
        served = provider / target
        withheld = private / source_name.replace(".nc", f"-{WITHHELD_YEAR}.nc")
        split = split_withheld_year(source, variable, served, withheld)
        key = "chirps" if "chirps" in source_name else "ersst"
        records.append({"path": target, "kind": "acmaddl_raw_cache_conversion", "cache": convert_log[key]["cache"].split("/_fetch_raw_cached/")[-1],
                        "cache_sha256": convert_log[key]["cache_sha256"], "withheld_file": str(withheld.relative_to(dest)), **split,
                        "sha256": digest(served), "decoded": describe(served), "withheld_decoded": describe(withheld)})
    records_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(staging / "fetch-log.json", records_dir / "fetch-log.json")
    shutil.copyfile(staging / "convert-log.json", records_dir / "convert-log.json")
    provenance = {
        "source_weather_is_synthetic": False,
        "delivery": "acmadDL deliveries: normalized NetCDF written by acmaddl.fetch for the NMME and CFSv2 SST products, and NetCDF conversions of acmadDL's raw cache for CHIRPS and ERSST. The withheld year's months are removed from the observation files; values are otherwise unchanged.",
        "withheld_year": WITHHELD_YEAR,
        "hindcast_issuance_years": [1993, 2016],
        "initialization_months": {"02": "February, target March-May", "08": "August, target October-December"},
        "model_precipitation": "NMME target-season precipitation per member on the model's 1-degree grid over 13S-23N 21-52E, in the units each delivery declares: CCSM4, GEOS-S2S and CanSIPS-IC4 as mean rates in mm/day; CFSv2 as season totals in mm (acmadDL's season-total conversion), with acmadDL uniting the IRI hindcast tree (to 2011) and realtime tree (2011-2016).",
        "model_sst": "NCEP CFSv2 target-season mean SST per member, 40S-40N 100E-100W, hindcast and realtime trees united by acmadDL.",
        "observed_precipitation": "CHIRPS v2.0 monthly totals, mm/month, 0.05-degree, 13S-16N 21-53E, 1993-2016 without the withheld year.",
        "observed_sst": "NOAA ERSST v5 monthly SST, 2-degree, 40S-40N 100E-100W, 1993-2016 without the withheld year.",
        "curator_steps": ["acmadDL normalization of provider responses (dimension names, target-season aggregation, region subset)",
                          "Withheld-year months removed from the observation files before serving",
                          "No value, unit or grid processing beyond acmadDL's own"],
        "limitations": ["Retrospective final-vintage archives; no claim these files were available as such at the historical issuance dates",
                        "CFSv2 is delivered as season totals in mm while the other centres are mean rates in mm/day; reading each file's units is part of the job"],
        "files": records,
    }
    (provider / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    resources = [{"path": str(p.relative_to(provider)), "sha256": digest(p), "bytes": p.stat().st_size}
                 for p in sorted(provider.rglob("*")) if p.is_file() and p.name != "catalog.json"]
    (provider / "catalog.json").write_text(json.dumps({"schema_version": 1,
        "description": "Frozen acmadDL deliveries: NMME seasonal precipitation for four centres, CFSv2 SST, CHIRPS 0.05-degree monthly rainfall and ERSST v5 monthly SST; the withheld year's observations are absent.",
        "resources": resources}, indent=2) + "\n")
    files = [{"file": str(p.relative_to(dest)), "sha256": digest(p), "bytes": p.stat().st_size,
              "visibility": "provider" if p.is_relative_to(provider) else "controller"}
             for p in sorted(dest.rglob("*")) if p.is_file()]
    manifest = {"schema_version": 1, "source_snapshot": str(dest.relative_to(ROOT)), "source_weather_is_synthetic": False,
                "scientific_approval": "pending", "redistribution_approval": "pending",
                "withheld_year": WITHHELD_YEAR, "files": files, "limitations": provenance["limitations"]}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    total = sum(row["bytes"] for row in files)
    print(f"Frozen {len(files)} files ({total / 1e6:.0f} MB) under {dest}")


if __name__ == "__main__":
    sys.exit(main())
