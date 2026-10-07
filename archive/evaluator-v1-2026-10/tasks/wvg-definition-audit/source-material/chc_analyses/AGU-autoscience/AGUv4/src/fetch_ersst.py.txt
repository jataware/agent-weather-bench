"""fetch_ersst.py — build the ERSSTv5 fixture once, through rosetta.

legacy/contracts/SPEC.md §1.2 pins this fixture by sha256. Nothing downstream ever touches the
network, so the fixture must be built here and only here.

Two environment facts are handled, neither of which is a change to rosetta:

  - This machine's IPv6 route to www.ncei.noaa.gov is dead, and urllib has no
    Happy-Eyeballs fallback the way curl does. Measured on 2026-08-06: one
    168 KB monthly file takes 0.85 s over IPv4 and ~180 s when IPv6 is tried
    first. Over 516 months that is the difference between one minute and a
    day, so getaddrinfo is filtered to IPv4 for this process only. It is a
    property of this network, not of the product, which is why it lives here
    and not in rosetta's http adapter.

  - ERSST files carry a size-1 `lev` dimension. It is squeezed here, matching
    AGUv3's `squeeze("zlev")`, so the fixture is a plain (time, lat, lon) field.

A third fact is a genuine data hazard and is handled with verification rather
than with an assumption. ERSST v5's monthly files do NOT share a time encoding:
older files declare `minutes since <that month> 00:00` on a **360_day** calendar
and decode to day 1, newer files declare `days since 1854-01-15` on a
**gregorian** calendar and decode to day 15. Concatenating them yields a time
axis that mixes cftime.Datetime360Day with pandas.Timestamp, which cannot even
be differenced. Both encodings do identify the correct (year, month), so the
axis is rebuilt as the first of each month — but the rebuild is checked, not
trusted: the sequence must be exactly 1981-01 … 2023-12, strictly increasing,
with no gaps and no duplicates, or nothing is written.

Writes data/ersst_v5_monthly.nc and prints the JSON provenance block that
legacy/contracts/SPEC.md §1.2 and outputs/env.json record.

Run: rx run exec -e e:N -- conda run -n pycpt python src/fetch_ersst.py
"""
from __future__ import annotations

import hashlib
import json
import socket
import subprocess
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

# IPv4 preference must be installed before rosetta opens any connection.
_orig_getaddrinfo = socket.getaddrinfo
socket.getaddrinfo = lambda *a, **k: (
    [r for r in _orig_getaddrinfo(*a, **k) if r[0] == socket.AF_INET]
    or _orig_getaddrinfo(*a, **k)
)

import numpy as np
import xarray as xr
import rosetta

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
OUT = DATA / "ersst_v5_monthly.nc"

PRODUCT = "sst/ersst-v5"
BELT = [-40.0, 40.0, 0.0, 360.0]      # the AGUv0 tropical belt, 0-360 longitude
YEARS = (1981, 2023)

# Every index box of legacy/contracts/SPEC.md §7 must fall inside the fetched belt.
INDEX_BOXES = {
    "nino34": (-5, 5, 190, 240),
    "iod_w": (-10, 10, 50, 70),
    "iod_e": (-10, 0, 90, 110),
    "wpac": (-5, 5, 130, 150),
    "wv": (5, 20, 130, 170),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_sha(repo: Path) -> str:
    return subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"],
                                   text=True).strip()


def _rebuild_time_axis(da):
    """Normalise ERSST's two incompatible time encodings to one monthly axis.

    Both cftime.Datetime360Day and pandas.Timestamp expose .year and .month, and
    both agree on which month a file represents; only the day-of-month and the
    calendar differ. So (year, month) is read off each element and the axis is
    rebuilt at the first of each month. Every property that could silently go
    wrong is then asserted rather than assumed.
    """
    import pandas as pd

    vals = da["time"].values
    kinds = {}
    ym = []
    for v in vals:
        kinds[type(v).__name__] = kinds.get(type(v).__name__, 0) + 1
        ym.append((int(v.year), int(v.month)))
    print(f"  time encodings seen: {kinds}", flush=True)

    idx = pd.DatetimeIndex([pd.Timestamp(y, m, 1) for y, m in ym])
    order = np.argsort(idx.values)
    idx, da = idx[order], da.isel(time=order)

    expect = pd.date_range(f"{YEARS[0]}-01-01", f"{YEARS[1]}-12-01", freq="MS")
    if len(idx) != len(expect):
        raise SystemExit(f"REFUSING TO WRITE: {len(idx)} months, expected {len(expect)}")
    if idx.duplicated().any():
        dups = sorted({str(d)[:7] for d in idx[idx.duplicated()]})
        raise SystemExit(f"REFUSING TO WRITE: duplicate months {dups}")
    if not idx.equals(expect):
        bad = [str(a)[:7] for a, b in zip(idx, expect) if a != b][:5]
        raise SystemExit(f"REFUSING TO WRITE: month sequence not {YEARS[0]}-01..{YEARS[1]}-12; "
                         f"first mismatches {bad}")
    print(f"  time axis verified: {len(idx)} months, {idx[0].date()}..{idx[-1].date()}, "
          "strictly increasing, no gaps, no duplicates", flush=True)
    return da.assign_coords(time=idx)


def main():
    if OUT.exists():
        print(f"[skip] {OUT.name} exists", flush=True)
    else:
        n_months = (YEARS[1] - YEARS[0] + 1) * 12
        print(f"[fetch] {PRODUCT} sst, belt {BELT}, {YEARS} ({n_months} monthly files)",
              flush=True)
        t0 = time.time()
        ds = rosetta.fetch(product=PRODUCT, variable="sst", region=BELT,
                           hindcast=YEARS, verbose=True, progress=True)
        print(f"  fetched in {time.time() - t0:.0f}s", flush=True)

        if not hasattr(ds, "data_vars"):
            ds = ds.to_dataset(name="sst")
        da = ds["sst"]
        for d in ("lev", "zlev"):
            if d in da.dims and da.sizes[d] == 1:
                da = da.squeeze(d, drop=True)
        da = _rebuild_time_axis(da)
        for c in list(da.coords):
            if c not in ("lat", "lon", "time"):
                da = da.drop_vars(c)
        da.attrs, da.encoding = {}, {}
        out = da.to_dataset(name="sst")
        for c in list(out.coords):
            out[c].attrs, out[c].encoding = {}, {}

        # Refuse to write anything degenerate, and refuse to write anything that
        # does not actually contain every index box the analysis needs.
        v = out["sst"].values
        finite = float(np.isfinite(v).mean())
        if finite < 0.3:
            raise SystemExit(f"REFUSING TO WRITE: only {finite:.1%} finite")
        if np.nanmax(v) == np.nanmin(v):
            raise SystemExit("REFUSING TO WRITE: constant field")
        lat, lon = out.lat.values, out.lon.values
        for name, (s, n, w, e) in INDEX_BOXES.items():
            if not (((lat >= s) & (lat <= n)).any() and ((lon >= w) & (lon <= e)).any()):
                raise SystemExit(f"REFUSING TO WRITE: index box {name} not covered")
        out.to_netcdf(OUT, engine="netcdf4")
        print(f"  wrote {OUT.name} ({OUT.stat().st_size / 1e6:.1f} MB)", flush=True)

    ds = xr.open_dataset(OUT)
    da = ds["sst"]
    yrs = np.unique(da["time.year"].values)
    months = {int(y): int((da["time.year"].values == y).sum()) for y in yrs}
    short = {y: m for y, m in months.items() if m != 12}

    prov = {
        "product": PRODUCT,
        "belt": BELT,
        "years": list(YEARS),
        "file": str(OUT.relative_to(ROOT)),
        "bytes": OUT.stat().st_size,
        "sha256": sha256(OUT),
        "dims": {k: int(v) for k, v in da.sizes.items()},
        "lat_range": [float(da.lat.min()), float(da.lat.max())],
        "lon_range": [float(da.lon.min()), float(da.lon.max())],
        "n_months": int(da.sizes["time"]),
        "incomplete_years": short,
        "finite_fraction": round(float(np.isfinite(da.values).mean()), 4),
        "units": "C",
        "rosetta_git_sha": git_sha(Path(rosetta.__file__).resolve().parents[2]),
        "rosetta_catalog_sha256": sha256(Path(rosetta.__file__).parent / "catalog.yaml"),
    }
    print("\nPROVENANCE")
    print(json.dumps(prov, indent=2))
    (ROOT / "outputs").mkdir(exist_ok=True)
    (ROOT / "outputs" / "ersst_provenance.json").write_text(json.dumps(prov, indent=2) + "\n")
    print(f"\nwrote {ROOT / 'outputs' / 'ersst_provenance.json'}")


if __name__ == "__main__":
    sys.exit(main())
