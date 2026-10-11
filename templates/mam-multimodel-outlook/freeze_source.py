"""Freeze native-schema monthly caches without unpickling on the host.

The host branch uses only the standard library. Scientific decoding runs in a
digest-pinned, offline, read-only Docker container with exact-file cache mounts.
NetCDF is a curator serialization of already decoded provider data, not an
original provider GRIB download. Existing frozen manifests are verified only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

IMAGE = "sha256:cfbde79dea2813f21e192e9671a56f7de77ccc1c768d378675850ca3569b837a"
MODELS = {"ecmwf": ("ecmwf-monthly", 25), "cmcc": ("cmcc", 40),
          "ukmo": ("ukmo", 28), "meteofrance": ("meteofrance", 31)}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def container_main(mode):
    # Import order avoids the pinned runtime's PROJ/backend-discovery issue.
    import pyproj  # noqa: F401
    import pickle
    import numpy as np
    import xarray as xr

    class ClimateCacheUnpickler(pickle.Unpickler):
        """Block unrelated executable globals in addition to Docker isolation."""
        globals_seen = set()

        def find_class(self, module, name):
            self.globals_seen.add((module, name))
            prefixes = ("numpy", "xarray", "pandas", "rasterio", "rioxarray")
            scalar_modules = {"collections", "collections.abc", "datetime",
                              "copyreg", "builtins"}
            if not (module.split(".")[0] in prefixes or module in scalar_modules):
                raise pickle.UnpicklingError(f"Unsupported cache global: {module}.{name}")
            if module == "builtins" and name not in {
                    "slice", "set", "frozenset", "complex", "str", "bytes",
                    "list", "dict", "tuple", "int", "float", "bool", "object"}:
                raise pickle.UnpicklingError(f"Disallowed builtin: {name}")
            return super().find_class(module, name)

    def safe_json(value):
        if isinstance(value, dict):
            return {str(k): safe_json(v) for k, v in value.items()}
        if isinstance(value, (tuple, list)):
            return [safe_json(v) for v in value]
        if isinstance(value, np.ndarray):
            return safe_json(value.tolist())
        if isinstance(value, np.generic):
            return safe_json(value.item())
        if isinstance(value, float) and not np.isfinite(value):
            return str(value)
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    def load_cache(name):
        with open(f"/input/{name}.pkl", "rb") as handle:
            obj = ClimateCacheUnpickler(handle).load()
        if isinstance(obj, xr.DataArray):
            obj = obj.to_dataset(name=obj.name or "precip")
        if not isinstance(obj, xr.Dataset):
            raise TypeError(f"{name}: expected xarray Dataset, got {type(obj)}")
        return obj.load()

    def array_digest(values):
        arr = np.ascontiguousarray(values)
        if arr.dtype.hasobject:
            payload = json.dumps(safe_json(arr), sort_keys=True).encode()
        else:
            payload = memoryview(arr.reshape(-1).view(np.uint8))
        return hashlib.sha256(payload).hexdigest()

    def report(ds):
        out = {"sizes": dict(ds.sizes), "attrs": safe_json(ds.attrs),
               "coordinates": {}, "variables": {}}
        for key, a in ds.coords.items():
            values = a.values
            vals = (np.datetime_as_string(values, unit="s").tolist()
                    if np.issubdtype(values.dtype, np.datetime64) else safe_json(values))
            out["coordinates"][key] = {"dims": list(a.dims), "dtype": str(a.dtype),
                                       "data_sha256": array_digest(values),
                                       "values": vals, "attrs": safe_json(a.attrs)}
        for key, a in ds.data_vars.items():
            values = np.asarray(a.values)
            row = {"dims": list(a.dims), "dtype": str(a.dtype),
                   "data_sha256": array_digest(values),
                   "attrs": safe_json(a.attrs)}
            if np.issubdtype(values.dtype, np.number):
                finite = values[np.isfinite(values)]
                row.update(finite=int(finite.size), total=int(values.size),
                           negative=int((finite < 0).sum()),
                           min=float(finite.min()) if finite.size else None,
                           median=float(np.median(finite)) if finite.size else None,
                           max=float(finite.max()) if finite.size else None)
            out["variables"][key] = row
        # A portable decoded-content identity: dtype/dimensions/attributes and
        # array byte digests, not a hash of xarray's mutable Python object graph.
        identity = {"sizes": out["sizes"], "attrs": out["attrs"],
                    "coordinates": out["coordinates"],
                    "variables": {k: {f: v[f] for f in ("dims", "dtype", "attrs", "data_sha256")}
                                  for k, v in out["variables"].items()}}
        out["decoded_dataset_sha256"] = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return out

    models = {}
    result = {"models": {}, "observations": {}, "pickle_globals": []}
    for name, (_, members) in MODELS.items():
        ds = load_cache(name)
        time = "indexing_time" if name == "ukmo" else "forecast_reference_time"
        if dict(ds.sizes) != {"number": members, time: 24, "forecastMonth": 3,
                             "latitude": 6, "longitude": 6}:
            raise ValueError(f"Unexpected native {name} schema: {dict(ds.sizes)}")
        dates = ds[time].values.astype("datetime64[D]")
        expected = np.array([f"{year}-02-01" for year in range(1993, 2017)],
                            dtype="datetime64[D]")
        if not np.array_equal(dates, expected):
            raise ValueError(f"Unexpected {name} issuance dates: {dates}")
        if not np.array_equal(ds.forecastMonth.values, [2, 3, 4]):
            raise ValueError(f"Unexpected {name} forecastMonth: {ds.forecastMonth.values}")
        if "tprate" not in ds or ds.tprate.attrs.get("units") != "m s**-1":
            raise ValueError(f"Unexpected {name} precipitation variable/units")
        vals = ds.tprate.values
        if not np.all(np.isfinite(vals)) or np.any(vals < 0) or np.max(vals) > 1e-5:
            raise ValueError(f"Unexpected {name} precipitation values")
        result["models"][name] = report(ds)
        models[name] = ds
    first = models["ecmwf"]
    for name, ds in models.items():
        for coord in ("latitude", "longitude"):
            if not np.array_equal(ds[coord].values, first[coord].values):
                raise ValueError(f"Native model grids differ: {name} {coord}")

    obs = load_cache("chirps")
    result["observations"]["full_cache"] = report(obs)
    # Crop only, retaining native monthly totals and a generous interpolation
    # margin. Actual coordinate names are deliberately checked, never guessed.
    if not {"time", "latitude", "longitude"} <= set(obs.dims):
        raise ValueError(f"Unexpected CHIRPS dimensions: {dict(obs.sizes)}")
    lat, lon = first.latitude.values, first.longitude.values
    margin = 0.10
    keep_lat = (obs.latitude >= min(lat) - margin) & (obs.latitude <= max(lat) + margin)
    keep_lon = (obs.longitude >= min(lon) - margin) & (obs.longitude <= max(lon) + margin)
    obs = obs.isel(latitude=np.flatnonzero(keep_lat), longitude=np.flatnonzero(keep_lon))
    months = obs.time.dt.month.values
    obs = obs.isel(time=np.flatnonzero(np.isin(months, [3, 4, 5])))
    expected_obs = np.array([f"{y}-{m:02}-01" for y in range(1993, 2017)
                             for m in (3, 4, 5)], dtype="datetime64[D]")
    if not np.array_equal(obs.time.values.astype("datetime64[D]"), expected_obs):
        raise ValueError("CHIRPS monthly coverage is incomplete or misaligned")
    if not (obs.latitude.min() < min(lat) and obs.latitude.max() > max(lat)
            and obs.longitude.min() < min(lon) and obs.longitude.max() > max(lon)):
        raise ValueError("CHIRPS subset does not bracket native model grid")
    result["observations"]["spatial_temporal_subset"] = report(obs)
    sampled = obs.precip.interp(latitude=first.latitude, longitude=first.longitude)
    complete = np.isfinite(sampled.values).all(axis=0)
    result["observation_grid_coverage"] = {
        "method": "Bilinear interpolation diagnostic only; source fields unchanged",
        "latitude": first.latitude.values.tolist(),
        "longitude": first.longitude.values.tolist(),
        "all_72_mam_months_finite": complete.tolist(),
        "complete_cells": int(complete.sum()),
        "inland_first_three_longitudes_complete": bool(complete[:, :3].all()),
    }
    result["pickle_globals"] = sorted([list(v) for v in ClimateCacheUnpickler.globals_seen])
    Path("/output/decoded-metadata.json").write_text(json.dumps(result, indent=2) + "\n")
    if mode == "inspect":
        return
    if not complete[:, :3].all():
        raise ValueError("Incomplete CHIRPS support at inland service grid")

    shipping = Path("/output/shipping")
    provider = shipping/"provider"
    private = shipping/"private-targets"
    (provider/"models").mkdir(parents=True)
    (provider/"observations").mkdir(parents=True)
    private.mkdir(parents=True)
    result["serialization_checks"] = {}

    def serialize(ds, path):
        # Clear only backend/file encodings. The decoded values, coordinate
        # names/order, dtypes, and native attributes must survive exactly.
        serial = ds.copy(deep=False)
        serial.encoding = {}
        for var in serial.variables:
            serial[var].encoding = {}
        serial.to_netcdf(path, engine="h5netcdf")
        with xr.open_dataset(path, engine="h5netcdf", chunks=None) as restored:
            restored.load()
            xr.testing.assert_identical(serial, restored)
        result["serialization_checks"][str(path.relative_to(shipping))] = {
            "decoded_arrays_coordinates_dtypes_attributes_identical": True,
            "sha256": digest(path), "bytes": path.stat().st_size,
            "decoded_dataset_sha256": report(serial)["decoded_dataset_sha256"],
        }

    for name, ds in models.items():
        serialize(ds, provider/"models"/f"{name}.nc")
    # The COG/xarray cache omitted units. This annotation is supplied from the
    # CHIRPS monthly product contract; NO value conversion or rescaling occurs.
    obs = obs.copy(deep=False)
    obs.precip.attrs = dict(obs.precip.attrs, units="mm/month",
                           curator_units_annotation="Native CHIRPS v2 monthly accumulated rainfall; original decoded cache omitted units. No rescaling.")
    before = obs.isel(time=np.flatnonzero(obs.time.dt.year.values <= 2015))
    target = obs.isel(time=np.flatnonzero(obs.time.dt.year.values == 2016))
    serialize(before, provider/"observations/chirps-monthly-pre2016.nc")
    serialize(target, private/"chirps-monthly-2016.nc")
    result["observations"]["public_training"] = report(before)
    result["observations"]["private_target"] = report(target)
    Path("/output/decoded-metadata.json").write_text(json.dumps(result, indent=2) + "\n")


def host_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, default=Path.home()/".nuthatch/rosetta/rosetta/_fetch_raw_cached")
    parser.add_argument("--image", default=IMAGE)
    parser.add_argument("--inspect", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    dest = root/"var/private/templates/mam-multimodel-outlook"
    manifest_path = Path(__file__).with_name("sources.json")
    if manifest_path.exists() and not args.inspect:
        manifest = json.loads(manifest_path.read_text())
        for row in manifest["files"]:
            path = dest/row["file"]
            if not path.is_file() or digest(path) != row["sha256"]:
                raise ValueError(f"Frozen source changed or absent: {path}")
        print("Existing frozen source verified; no bytes changed.")
        return
    sources = {name: args.cache_root/"1993_2016_None_2_c3s"/f"{product}_-3.0_3.0_36.0_42.0_precip.pkl"
               for name, (product, _) in MODELS.items()}
    sources["chirps"] = args.cache_root/"1993_2016_None_obs"/"chirps-v2-monthly_-12.0_15.0_22.0_52.0_precip.pkl"
    records = {}
    for name, source in sources.items():
        if not source.is_file() or source.is_symlink():
            raise ValueError(f"Missing or symbolic-link raw cache: {source}")
        records[name] = {"cache_path": str(source), "sha256": digest(source),
                         "cache_key": str(source.relative_to(args.cache_root)),
                         "bytes": source.stat().st_size}
    review = root/"var/review/mam-source-decode"
    review.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mam-native-freeze-", dir=root/"var/private") as temp:
        out = Path(temp)
        cmd = ["docker", "run", "--rm", "--network", "none", "--read-only",
               "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
               "--pids-limit", "128", "--memory", "3g", "--cpus", "1",
               "--user", f"{os.getuid()}:{os.getgid()}", "--tmpfs", "/tmp:rw,size=512m",
               "-e", "OMP_NUM_THREADS=1", "-e", "OPENBLAS_NUM_THREADS=1",
               "-e", "MKL_NUM_THREADS=1", "-e", "NUMEXPR_NUM_THREADS=1",
               "-e", "HOME=/tmp", "-e", "PYTHONDONTWRITEBYTECODE=1",
               "--mount", f"type=bind,src={Path(__file__).resolve()},dst=/freeze_source.py,readonly",
               "--mount", f"type=bind,src={out},dst=/output"]
        for name, path in sources.items():
            cmd += ["--mount", f"type=bind,src={path.resolve()},dst=/input/{name}.pkl,readonly"]
        cmd += [args.image, "python", "/freeze_source.py", "--_container", "inspect" if args.inspect else "freeze"]
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=240)
        (review/"decoder.stdout").write_text(proc.stdout)
        (review/"decoder.stderr").write_text(proc.stderr)
        (review/"raw-cache-records.json").write_text(json.dumps(records, indent=2) + "\n")
        if proc.returncode:
            raise RuntimeError(f"Isolated decoder failed ({proc.returncode}):\n{proc.stderr[-5000:]}")
        import shutil
        for path in out.iterdir():
            if path.is_file():
                shutil.copy2(path, review/path.name)
        if args.inspect:
            print(f"Inspected native source metadata: {review/'decoded-metadata.json'}")
            return
        decoded = json.loads((out/"decoded-metadata.json").read_text())
        image = subprocess.run(["docker", "image", "inspect", args.image,
                                "--format", "{{.Id}}"], text=True,
                               capture_output=True, check=True).stdout.strip()
        provenance = {
            "source_weather_is_synthetic": False,
            "delivery": "Curator NetCDF serialization of provider-native-schema decoded xarray cache. Not original GRIB/COG bytes.",
            "source_catalogue": "https://cds.climate.copernicus.eu/datasets/seasonal-monthly-single-levels",
            "retrospective_only": True,
            "real_time_archive_vintage_claim": False,
            "model_request": {"variable": "total_precipitation", "product_type": "monthly_mean",
                              "years": [1993, 2016], "init_month": 2,
                              "leadtime_month": [2, 3, 4], "target": "MAM",
                              "region_bbox_latlon": [-3.0, 3.0, 36.0, 42.0]},
            "models": {},
            "observations": {
                "product": "CHIRPS v2.0 monthly accumulated rainfall",
                "source_url_pattern": "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/cogs/chirps-v2.0.{year}.{month:02d}.cog",
                "cache_record": {k: v for k, v in records["chirps"].items() if k != "cache_path"},
                "public_dates": ["1993-03-01", "2015-05-01"],
                "public_months": [3, 4, 5], "public_count": 69,
                "native_units": "mm/month", "units_annotation_by_curator": True,
                "decoded_cache_original_units_attribute": None,
                "processing": ["Crop to native coordinates bracketing the full model grid by at least 0.075 degrees",
                               "Retain March/April/May records", "Exclude every 2016 record from provider resources",
                               "Annotate omitted monthly-total units without changing values",
                               "Serialize NetCDF retaining float32 values, coordinate names/order and native attributes"],
                "native_raster_metadata_limit": "TIFF tags retained by the aggregated xarray cache describe its first source raster; coordinate arrays define the cropped NetCDF grid.",
                "latitude": {"count": 104, "first": 2.5749992933124304, "last": -2.5750007834285498},
                "longitude": {"count": 104, "first": 36.42500322498381, "last": 41.57500330172479},
            },
            "service_grid": {"latitude": [-2.5, -1.5, -0.5, 0.5, 1.5, 2.5],
                             "longitude": [36.5, 37.5, 38.5],
                             "all_training_and_target_months_have_bilinear_support": True},
            "serialization": {"script": "templates/mam-multimodel-outlook/freeze_source.py",
                              "image": image, "network": "none", "scientific_threads": 1,
                              "pickle_decoding": "Restricted climate-object globals inside exact-file-mount offline nonroot read-only container"},
            "limitations": ["No claim that these reforecasts or observations were available as final data at historical issuance dates",
                            "Source GRIB/COG downloads are not retained here; cache hashes and native decoding history establish the available lineage",
                            "Model grid and 1993–2016 overlap are a small Kenya service window, not a country-wide or global product"],
        }
        for name, data in decoded["models"].items():
            provenance["models"][name] = {
                "file": f"models/{name}.nc",
                "cache_record": {k: v for k, v in records[name].items() if k != "cache_path"},
                "decoded_dataset_sha256": data["decoded_dataset_sha256"],
                "sizes": data["sizes"], "global_attributes": data["attrs"],
                "precipitation_attributes": data["variables"]["tprate"]["attrs"],
                "coordinates": data["coordinates"],
                "serialization_array_parity": True,
            }
        shipping = out/"shipping"
        (shipping/"provider/provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
        resources = [{"path": str(p.relative_to(shipping/"provider")),
                      "sha256": digest(p), "bytes": p.stat().st_size}
                     for p in sorted((shipping/"provider").rglob("*")) if p.is_file()]
        (shipping/"provider/catalog.json").write_text(json.dumps({"schema_version": 1,
            "description": "Frozen retrospective C3S MAM predictors and preforecast CHIRPS monthly observations; no withheld target observations.",
            "resources": resources}, indent=2) + "\n")
        diagnostics = shipping/"private-source-records"
        diagnostics.mkdir()
        shutil.copy2(out/"decoded-metadata.json", diagnostics/"decoded-metadata.json")
        (diagnostics/"raw-cache-records.json").write_text(json.dumps(records, indent=2) + "\n")
        files = [{"file": str(p.relative_to(shipping)), "sha256": digest(p),
                  "bytes": p.stat().st_size,
                  "visibility": "provider" if p.is_relative_to(shipping/"provider") else "controller"}
                 for p in sorted(shipping.rglob("*")) if p.is_file()]
        manifest = {"schema_version": 1, "source_snapshot": str(dest.relative_to(root)),
                    "source_weather_is_synthetic": False,
                    "scientific_approval": "pending", "redistribution_approval": "pending",
                    "decoder_image": image, "files": files,
                    "raw_cache_records": {k: {f: v[f] for f in ("cache_key", "sha256", "bytes")}
                                          for k, v in records.items()},
                    "limitations": provenance["limitations"]}
        if manifest_path.exists():
            raise ValueError("A frozen manifest appeared during decoding; refusing replacement")
        for p in sorted(shipping.rglob("*")):
            relative = p.relative_to(shipping)
            if p.is_file():
                target_path = dest/relative
                if target_path.exists():
                    raise ValueError(f"Refusing to overwrite existing source: {target_path}")
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, target_path)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"Frozen {len(files)} source/metadata files under {dest}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--_container":
        container_main(sys.argv[2])
    else:
        host_main()
