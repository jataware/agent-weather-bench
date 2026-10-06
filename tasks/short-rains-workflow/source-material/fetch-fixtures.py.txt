"""fetch_fixtures.py — pull every input v4zeek scores against, through rosetta, once.

Everything downstream reads the NetCDFs written here. No scored run ever touches the
network, so the benchmark's inputs are byte-identical across every submission.

Stage 0 needs exactly two things:
  - California monthly rainfall            obs/chirps-v3-monthly  ->  ca_precip_monthly.nc
  - the Nino-3.4 ocean-temperature box     obs/era5 (sst)         ->  sst_<box>_monthly.nc

Later stages add boxes and regions here; they do not change the harness.

Longitude convention is NOT assumed. Each fetch prints the coordinate ranges it got
back so the convention is observed, not guessed (the AGUv0 notes record a real bug from
assuming it). Anything written here is verified non-empty and non-degenerate first.

Run:  conda run -n pycpt python src/fetch_fixtures.py [chirps|sst|all]
"""
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import rosetta

DATA = Path(__file__).resolve().parents[1] / "data"
DATA.mkdir(exist_ok=True)

YEARS = (1981, 2023)

# ── predictand regions: [lat_s, lat_n, lon_w, lon_e] ───────────────────────────
# California with a small margin. Stage 0 uses the whole box as one area-mean;
# Stage 1 subdivides it; Stage 3 discovers the subdivision.
REGIONS = {
    "ca": dict(bbox=[32.0, 42.5, -125.0, -114.0], file="ca_precip_monthly.nc"),
    # Eastern Horn of Africa: Kenya, Somalia, southern Ethiopia. This is the BETTER
    # positive control. California was chosen as one and turned out empty (f:9); the
    # prior program's own strongest and most defensible result was the East African
    # October-December short rains, so if any signal exists in this problem family it
    # is here. It is also the one target where v4zeek and AGUv0-v3 measure the same
    # thing, which makes it a direct comparison rather than an analogy.
    "ea": dict(bbox=[-5.0, 12.0, 33.0, 52.0], file="ea_precip_monthly.nc"),
}

# ── predictor boxes: standard ocean-temperature index boxes, 0-360 longitude ───
# Stage 0 uses nino34 only. The rest are here so Stage 1 needs no refetch.
SST_BOXES = {
    "nino34": [-6.0, 6.0, 189.0, 241.0],      # 5S-5N, 170W-120W (+1 deg margin)
    "iod_w":  [-11.0, 11.0, 49.0, 71.0],      # Indian Ocean Dipole, west pole
    "iod_e":  [-11.0, 1.0, 89.0, 111.0],      # Indian Ocean Dipole, east pole
    "wpac":   [-6.0, 6.0, 129.0, 151.0],      # west Pacific
    "wv":     [4.0, 21.0, 129.0, 171.0],      # "Western V"
}


def _clean(ds, var):
    """Strip bounds vars and inherited encodings that collide on netCDF write."""
    import xarray as xr

    da = ds[var] if hasattr(ds, "data_vars") and var in ds.data_vars else ds
    if hasattr(da, "data_vars"):
        cands = [v for v in da.data_vars if not any(
            k in str(v).lower() for k in ("bnds", "bounds", "spatial_ref"))]
        da = da[cands[0]]
    for c in list(da.coords):
        if c not in ("lat", "lon", "time"):
            da = da.drop_vars(c)
    da.attrs, da.encoding = {}, {}
    out = da.to_dataset(name=var)
    for c in list(out.coords):
        out[c].attrs, out[c].encoding = {}, {}
    return out


def _report(ds, var, label):
    """Print what actually came back and refuse to write anything degenerate."""
    da = ds[var]
    print(f"  {label}: dims={dict(da.sizes)}")
    for c in ("time", "lat", "lon"):
        if c in da.coords:
            v = da[c].values
            print(f"    {c}: {len(v)} from {v.min()} to {v.max()}")
    finite = np.isfinite(da.values)
    frac = float(finite.mean())
    print(f"    finite: {frac:.1%}   min={np.nanmin(da.values):.4g} max={np.nanmax(da.values):.4g}")
    if frac < 0.01:
        raise SystemExit(f"REFUSING TO WRITE {label}: {frac:.2%} finite — fetch returned empty")
    if np.nanmax(da.values) == np.nanmin(da.values):
        raise SystemExit(f"REFUSING TO WRITE {label}: constant field — fetch returned fill values")
    return frac


def fetch_chirps(only=None):
    for name, spec in REGIONS.items():
        if only and name not in only:
            continue
        out = DATA / spec["file"]
        if out.exists():
            print(f"[skip] {out.name} exists", flush=True)
            continue
        print(f"[fetch] CHIRPS v3 monthly, region {name} {spec['bbox']}, {YEARS}", flush=True)
        t0 = time.time()
        ds = rosetta.fetch(
            product="obs/chirps-v3-monthly",
            variable="precip",
            region=spec["bbox"],
            hindcast=YEARS,
            request_interval=0.3,
        )
        if not hasattr(ds, "data_vars"):
            ds = ds.to_dataset(name="precip")
        ds = _clean(ds, "precip")
        _report(ds, "precip", f"chirps/{name}")
        ds.to_netcdf(out, engine="netcdf4")
        print(f"  wrote {out.name} ({out.stat().st_size / 1e6:.1f} MB) in {time.time() - t0:.0f}s",
              flush=True)


def fetch_sst(only=None, years=None, prefix="sst_"):
    for name, bbox in SST_BOXES.items():
        if only and name not in only:
            continue
        out = DATA / f"{prefix}{name}_monthly.nc"
        if out.exists():
            print(f"[skip] {out.name} exists", flush=True)
            continue
        yr = years or YEARS
        print(f"[fetch] ERA5 sst, box {name} {bbox}, {yr} -> {prefix}", flush=True)
        t0 = time.time()
        ds = rosetta.fetch(
            product="obs/era5",
            variable="sst",
            region=bbox,
            hindcast=yr,
        )
        if not hasattr(ds, "data_vars"):
            ds = ds.to_dataset(name="sst")
        ds = _clean(ds, "sst")
        _report(ds, "sst", f"era5/{name}")
        ds.to_netcdf(out, engine="netcdf4")
        print(f"  wrote {out.name} ({out.stat().st_size / 1e6:.1f} MB) in {time.time() - t0:.0f}s",
              flush=True)


def fetch_era5_precip(region="ca", out_name="ca_precip_era5_monthly.nc"):
    """A LONGER California rainfall record.

    The binding constraint on every result so far is n = 42. CHIRPS starts in 1981 and
    that is not negotiable. ERA5 is in the same rosetta catalog and reaches back to 1940,
    which doubles the sample to n = 84. Doubling n shrinks the noise floor by roughly
    sqrt(2) and is worth more than any amount of further configuration search.

    Caveat to carry with any result from it: ERA5 is a reanalysis, so its precipitation
    is model output constrained by assimilated observations, not a gauge/satellite
    product like CHIRPS. Skill measured against it is skill against a different
    predictand. That is why it is a SEPARATE fixture and a SEPARATE benchmark rather
    than a drop-in replacement - the two are compared, never pooled.
    """
    out = DATA / out_name
    if out.exists():
        print(f"[skip] {out.name} exists", flush=True)
        return
    bbox = REGIONS[region]["bbox"]
    years = (1940, 2023)
    print(f"[fetch] ERA5 precip, {region} {bbox}, {years}", flush=True)
    t0 = time.time()
    ds = rosetta.fetch(product="obs/era5", variable="precip", region=bbox, hindcast=years)
    if not hasattr(ds, "data_vars"):
        ds = ds.to_dataset(name="precip")
    ds = _clean(ds, "precip")
    _report(ds, "precip", f"era5/{region}")
    ds.to_netcdf(out, engine="netcdf4")
    print(f"  wrote {out.name} ({out.stat().st_size / 1e6:.1f} MB) in {time.time() - t0:.0f}s",
          flush=True)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what == "ea":
        fetch_chirps(only=["ea"])
        print("fixtures done")
        raise SystemExit(0)
    if what == "ea_era5":
        fetch_era5_precip(region="ea", out_name="ea_precip_era5_monthly.nc")
        print("fixtures done")
        raise SystemExit(0)
    if what == "sstlong":
        fetch_sst(years=(1940, 2023), prefix="sstlong_")
        print("fixtures done")
        raise SystemExit(0)
    if what == "era5precip":
        fetch_era5_precip()
        print("fixtures done")
        raise SystemExit(0)
    if what in ("chirps", "all"):
        fetch_chirps()
    if what in ("sst", "all"):
        fetch_sst(only=["nino34"] if what == "sst0" else None)
    if what == "sst0":
        fetch_sst(only=["nino34"])
    print("fixtures done")
