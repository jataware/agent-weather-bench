"""Fetch only explicitly selected public Zarr v2 chunks, recording every byte.

No cloud credentials, fsspec, or full global store download are needed. Source
chunks remain controller-only; the agent receives compact NetCDF subsets.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import urllib.request

import numcodecs
import numpy as np
import xarray as xr

REVISION = "d2c6a1553a0c532332d4c2d3be285508c514bfc2"
STORES = {
    "hres": "hres/2016-2022-0012-64x32_equiangular_conservative.zarr",
    "era5": "era5/1959-2022-6h-64x32_equiangular_conservative.zarr",
    "climatology": "era5-hourly-climatology/1990-2019_6h_64x32_equiangular_conservative.zarr",
}
BASE = "https://storage.googleapis.com/weatherbench2/datasets/"


class Store:
    def __init__(self, name, cache):
        self.name, self.cache = name, Path(cache) / name
        self.cache.mkdir(parents=True, exist_ok=True)
        self.records = []
        self.metadata = json.loads(self.get(".zmetadata"))["metadata"]

    def get(self, key):
        path = self.cache / key
        url = BASE + STORES[self.name] + "/" + key
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(url, timeout=60) as response:
                data = response.read()
                path.write_bytes(data)
        else:
            data = path.read_bytes()
        self.records.append({"url": url, "file": str(path), "bytes": len(data),
                             "sha256": hashlib.sha256(data).hexdigest()})
        return data

    def array(self, name, selections=None):
        spec = self.metadata[name + "/.zarray"]
        shape, chunks = spec["shape"], spec["chunks"]
        selections = selections or [np.arange(n) for n in shape]
        selected = [np.asarray(v, dtype=int) for v in selections]
        output = np.empty(tuple(len(v) for v in selected), dtype=np.dtype(spec["dtype"]))
        codec = numcodecs.get_codec(spec["compressor"]) if spec["compressor"] else None
        for indices in itertools.product(*[np.unique(v // c) for v, c in zip(selected, chunks)]):
            key = name + "/" + ".".join(map(str, indices))
            raw = self.get(key)
            data = codec.decode(raw) if codec else raw
            block = np.frombuffer(data, dtype=np.dtype(spec["dtype"])).reshape(chunks, order=spec["order"])
            outids = [np.flatnonzero(v // c == i) for v, c, i in zip(selected, chunks, indices)]
            local = [v[o] % c for v, o, c in zip(selected, outids, chunks)]
            output[np.ix_(*outids)] = block[np.ix_(*local)]
        return output

    def coordinate(self, name):
        data = self.array(name)
        attrs = dict(self.metadata[name + "/.zattrs"])
        attrs.pop("_ARRAY_DIMENSIONS", None)
        ds = xr.decode_cf(xr.Dataset(coords={name: (name, data, attrs)}))
        return ds[name].values


def freeze(repo):
    repo = Path(repo)
    root = repo / "var/private/tasks/weatherbench-verification"
    inputs, controller = root / "agent-inputs", root / "controller"
    inputs.mkdir(parents=True, exist_ok=True)
    controller.mkdir(parents=True, exist_ok=True)
    if (inputs / "hres.nc").exists():
        raise ValueError("Inputs already frozen; refusing overwrite")
    stores = {name: Store(name, controller / "source-cache") for name in STORES}
    hres, era, clim = [stores[k] for k in ("hres", "era5", "climatology")]
    issues = np.arange(np.datetime64("2020-01-01"), np.datetime64("2020-01-21"), np.timedelta64(1, "D")).astype("datetime64[ns]")
    leads = np.array([24, 72, 120, 168], dtype="timedelta64[h]")
    valid = issues[:, None] + leads[None, :]
    ht, hl = hres.coordinate("time"), hres.coordinate("prediction_timedelta")
    et = era.coordinate("time")
    lat, lon = hres.coordinate("latitude"), hres.coordinate("longitude")
    for store in (era, clim):
        np.testing.assert_array_equal(lat, store.coordinate("latitude"))
        np.testing.assert_array_equal(lon, store.coordinate("longitude"))
    def positions(values, requested):
        lookup = {x: i for i, x in enumerate(values)}
        return np.array([lookup[x] for x in requested], dtype=int)
    hi, li = positions(ht, issues), positions(hl.astype("timedelta64[h]"), leads)
    times = np.unique(np.r_[issues, valid.ravel()])
    ei = positions(et, times)
    fields = hres.array("2m_temperature", [hi, li, np.arange(64), np.arange(32)]).transpose(0, 1, 3, 2)
    ds = xr.Dataset({"temperature": (("init_time", "lead_time", "latitude", "longitude"), fields)},
                    coords={"init_time": issues, "lead_time": leads, "latitude": lat, "longitude": lon,
                            "valid_time": (("init_time", "lead_time"), valid)})
    ds.temperature.attrs = {"units": "K", "source_variable": "2m_temperature", "source_product": STORES["hres"]}
    ds.to_netcdf(inputs / "hres.nc")
    ef = era.array("2m_temperature", [ei, np.arange(64), np.arange(32)]).transpose(0, 2, 1)
    ds = xr.Dataset({"temperature": (("time", "latitude", "longitude"), ef)},
                    coords={"time": times, "latitude": lat, "longitude": lon})
    ds.temperature.attrs = {"units": "K", "source_variable": "2m_temperature", "source_product": STORES["era5"]}
    ds.to_netcdf(inputs / "era5.nc")
    hours, days = clim.coordinate("hour"), clim.coordinate("dayofyear")
    cf = clim.array("2m_temperature").transpose(0, 1, 3, 2)
    ds = xr.Dataset({"temperature": (("hour", "dayofyear", "latitude", "longitude"), cf)},
                    coords={"hour": hours, "dayofyear": days, "latitude": lat, "longitude": lon})
    ds.temperature.attrs = {"units": "K", "baseline": "1990-2019"}
    ds.to_netcdf(inputs / "climatology.nc")
    # Explicit comparison-availability stress test, not missing native weather.
    mask = np.ones((3, 20, 4, 32, 64), dtype=np.int8)
    mask[0, 10:, :, lat > 50, :] = 0
    mask[1, :5, :, lat < -50, :] = 0
    xr.Dataset({"available": (("system", "init_time", "lead_time", "latitude", "longitude"), mask)},
               coords={"system": ["hres", "persistence", "climatology"], "init_time": issues,
                       "lead_time": leads, "latitude": lat, "longitude": lon},
               attrs={"construction": "Curator-imposed availability dropout; source fields untouched."}).to_netcdf(inputs / "availability.nc")
    material = repo / "tasks/weatherbench-verification/source-material"
    material.mkdir(parents=True, exist_ok=True)
    for filename in ("metrics.py", "LICENSE"):
        url = f"https://raw.githubusercontent.com/google-research/weatherbench2/{REVISION}/" + ("weatherbench2/" if filename == "metrics.py" else "") + filename
        data = urllib.request.urlopen(url, timeout=60).read()
        (material / ("upstream-" + filename)).write_bytes(data)
    records = [r for s in stores.values() for r in s.records]
    unique = {r["url"]: r for r in records}
    audit = {"retrieved_at": datetime.now(timezone.utc).isoformat(), "source_revision": REVISION,
             "objects": list(unique.values()), "downloaded_unique_bytes": sum(r["bytes"] for r in unique.values()),
             "source_weather_is_synthetic": False, "native_grid_verified_equal": True,
             "native_nonfinite_counts": {"hres": int((~np.isfinite(fields)).sum()), "era5": int((~np.isfinite(ef)).sum()), "climatology": int((~np.isfinite(cf)).sum())}}
    (controller / "source-audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps({k: v for k, v in audit.items() if k != "objects"}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    freeze(parser.parse_args().repo)
