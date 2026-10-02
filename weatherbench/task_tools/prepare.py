"""Validate the internal data bundle and recompute numerical references, no agents."""
import hashlib
import json
from pathlib import Path

import numpy as np
import xarray as xr

from .references import (load, seasonal_training, acmad_objective, wvg_audit,
                         PAPER_BOXES, EXISTING_BOXES)

from weatherbench.storage import ROOT, PRIVATE, TASKS as PACKAGES, read
TASKS = ("seasonal-calibration", "acmad-objective", "wvg-definition-audit")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def independent_wvg(sst):
    """Separate xarray reduction for cross-checking the NumPy reference."""
    variants = []
    for boxes in (PAPER_BOXES, EXISTING_BOXES):
        regions = []
        for south, north, west, east in boxes:
            field = sst.sst.where((sst.lat >= south) & (sst.lat <= north)
                                  & (sst.lon >= west) & (sst.lon <= east), drop=True)
            monthly = field.weighted(np.cos(np.deg2rad(field.lat))).mean(("lat", "lon"))
            season = monthly.where(monthly.time.dt.month.isin([3, 4, 5]), drop=True).groupby("time.year").mean()
            regions.append(season)
        west = sum(regions[1:]) / 3
        nb, wb = regions[0].sel(year=slice(1981, 2010)), west.sel(year=slice(1981, 2010))
        variants.append((regions[0] - nb.mean()) / nb.std(ddof=1)
                        - (west - wb.mean()) / wb.std(ddof=1))
    return np.stack([v.values for v in variants])


def prepare():
    """Verify an installed internal data bundle and recompute its references.

    Published manifests and source snapshots are repository-owned. Data bundles
    are distributed separately; preparation never reads another checkout or
    changes a manifest to accept different input bytes.
    """
    from .checks import validate_packages
    validate_packages()
    base = PRIVATE / "seasonal-calibration"
    expected = seasonal_training(load(base / "agent-inputs/forecast-development.nc"),
                                 load(base / "agent-inputs/observations-development.nc"))
    frozen = load(base / "controller/training.nc")
    for name in ("forecast", "observed"):
        xr.testing.assert_allclose(expected[name], frozen[name], atol=1e-4, rtol=1e-6)

    base = PRIVATE / "acmad-objective"
    expected = acmad_objective([load(base / "agent-inputs" / name) for name in
                               ("observed-sst.nc", "forecast-sst.nc", "forecast-precip.nc")])
    frozen = load(base / "controller/objective.nc")
    for name in expected.data_vars:
        xr.testing.assert_allclose(expected[name], frozen[name], atol=1e-10, rtol=1e-10)

    base = PRIVATE / "wvg-definition-audit"
    sst = load(base / "agent-inputs/sst.nc")
    expected = wvg_audit(sst)
    np.testing.assert_allclose(expected.wvg.values, independent_wvg(sst), atol=1e-10, rtol=1e-10)
    frozen = load(base / "controller/indices.nc")
    for name in expected.data_vars:
        xr.testing.assert_allclose(expected[name], frozen[name], atol=1e-10, rtol=1e-10)
    provenance = read(base / "agent-inputs/ersst-provenance.json")
    if provenance["sha256"] != read(PACKAGES / "wvg-definition-audit/sources.yaml")["dataset"]["expected_source_sha256"]:
        raise ValueError("SST provenance does not match the task source record")
    return {"packages_prepared": list(TASKS), "references_recomputed": True,
            "model_calls": 0, "agent_attempts": 0}
