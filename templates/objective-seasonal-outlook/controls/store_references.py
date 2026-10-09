"""Regenerate the stored reference arrays and summary under the default accepted readings."""
import json, time, shutil, importlib.util
from pathlib import Path
import numpy as np, xarray as xr
ROOT = Path("/Users/ezekielbarnett/Developer/ACCORD/agent-weather-bench")
T = ROOT / "templates/objective-seasonal-outlook"
spec = importlib.util.spec_from_file_location("science", T / "science.py"); science = importlib.util.module_from_spec(spec); spec.loader.exec_module(science)
provider = ROOT / "var/private/templates/objective-seasonal-outlook/provider"
store = ROOT / "var/private/templates/objective-seasonal-outlook/references"
summary = {"conventions": dict(science.DEFAULT), "fingerprint_note": "reference arrays under the default accepted readings; category rule: a total within 1e-6 mm of a boundary is near normal", "instances": {}}
for name, init in (("gha--mam-2015", 2), ("gha--ond-2015", 8)):
    params = {"init_month": init, "forecast_year": 2015, "training_years": [y for y in range(1993, 2017) if y != 2015]}
    t0 = time.time(); ds = science.compute(provider, params, {}); seconds = round(time.time() - t0, 1)
    target = store / name / "results.zarr"; shutil.rmtree(target, ignore_errors=True); ds.to_zarr(target, zarr_format=3)
    support = ds["prepare_support"].values > 0
    members = {}
    for model in science.MODELS:
        for f in science.provider_files(provider, model, init):
            with xr.open_dataset(f) as m: members.setdefault(model, {})[Path(f).name] = int(m.sizes["member"])
    summary["instances"][name] = {
        "seconds": seconds, "supported_cells": int(support.sum()),
        "cca_modes_selected_forecast": ds["cca_modes_selected"].values.tolist(),
        "cv_rpss": {**{s: float(v) for s, v in zip(science.STREAMS, ds["verify_stream_rpss"].values)}, "objective": float(ds["verify_objective_rpss"].values)},
        "sst_index_forecast": float(ds["prepare_sst_index_forecast"].values),
        "issued_mean_probability": ds["issue_forecast_probability"].values[:, support].mean(axis=1).tolist(),
        "members": str(members)}
    print(name, json.dumps(summary["instances"][name]))
(store / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
