"""Trusted control solution: acquire the snapshot over HTTP, run every stage, plant one declared defect."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from urllib.request import urlopen

import numpy as np
import xarray as xr

import science


def acquire(inputs, destination, init):
    config = json.loads((Path(inputs) / "acquisition.json").read_text())
    base = config["base_url"].rstrip("/") + "/"
    with urlopen(base + config["catalog_path"], timeout=30) as response:
        catalogue = json.loads(response.read(1024 * 1024))
    resources = {row["path"]: row for row in catalogue["resources"]}
    needed = [f"models/{m}/precip_init{init:02d}.nc" for m in ("ccsm4", "geoss2s", "cansipsic4", "cfsv2")]
    needed += [f"sst/cfsv2/sst_init{init:02d}.nc"]
    needed += ["observations/chirps-v2p0-monthly-0p05.nc", "observations/ersst-v5-monthly.nc"]
    for name in needed:
        row = resources[name]
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or not 0 < row["bytes"] < 1024 * 1024 * 1024:
            raise ValueError("Invalid source catalogue resource")
        target = Path(destination) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(base + name, timeout=600) as response, target.open("wb") as out:
            digest, total = hashlib.sha256(), 0
            for block in iter(lambda: response.read(1024 * 1024), b""):
                digest.update(block); out.write(block); total += len(block)
        if total != row["bytes"] or digest.hexdigest() != row["sha256"]:
            raise ValueError("Downloaded object does not match provider catalogue")


def plant(ds, defect, params, provider):
    """Apply a declared defect to the correct result; faults that need different inputs are handled before compute."""
    n = ds.sizes["year"]
    if defect == "unequal_weights":
        weights = np.array([0.5, 0.3, 0.2])
        for part in ("hindcast", "forecast"):
            stacked = np.stack([ds[f"{s}_{part}_probability"].values for s in ("cca", "ereg", "wvg")])
            ds[f"combine_{part}_probability"].values[:] = np.tensordot(weights, stacked, axes=1)
        ds["issue_forecast_probability"].values[:] = ds["combine_forecast_probability"].values
        ds["issue_dominant_category"].values[:] = science.dominant(ds["combine_forecast_probability"].values) * ds["prepare_support"].values
        # the fault verifies its own (unequal) combination, so only the combination rule is broken
        support = ds["prepare_support"].values > 0
        categories = ds["prepare_observed_category"].values.astype(int)
        objective = science.rps(ds["combine_hindcast_probability"].values, categories).mean(0)
        ds["verify_objective_rps"].values[:] = objective * support
        ds["verify_objective_rpss"].values[()] = 1 - objective[support].mean() / ds["verify_climatology_rps"].values[support].mean()
    elif defect == "wrong_climatology_score":
        # the score against the training-frequency climatology instead of equal thirds
        support = ds["prepare_support"].values > 0
        categories = ds["prepare_observed_category"].values.astype(int)
        frequency = np.stack([(categories == k).mean(0) for k in range(3)])
        baseline = science.rps(np.broadcast_to(frequency, (n, 3, *frequency.shape[1:])), categories).mean(0)
        objective = science.rps(ds["combine_hindcast_probability"].values, categories).mean(0)
        ds["verify_climatology_rps"].values[:] = baseline * support
        ds["verify_objective_rpss"].values[()] = 1 - objective[support].mean() / baseline[support].mean()
    elif defect == "issue_mismatch":
        p = ds["issue_forecast_probability"].values
        ds["issue_forecast_probability"].values[:] = np.stack([p[2], p[1], p[0]])
    elif defect == "predictor_on_target_grid":
        # the interpolated model means delivered as the predictor fields, with the target grid under the model-grid coordinates
        ds = ds.drop_vars(["prepare_model_predictor_mm", "prepare_model_predictor_forecast_mm", "plat", "plon"])
        ds["prepare_model_predictor_mm"] = ds["prepare_model_hindcast_mean_mm"].rename({"lat": "plat", "lon": "plon"})
        ds["prepare_model_predictor_forecast_mm"] = ds["prepare_model_forecast_mean_mm"].rename({"lat": "plat", "lon": "plon"})
        ds = ds.assign_coords(plat=ds["lat"].values, plon=ds["lon"].values)
    return ds


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    variant = json.loads(Path("variant.json").read_text()) if Path("variant.json").is_file() else {}
    defect = variant.get("defect", "correct")
    if defect == "cached" and Path("cached-results.zarr").is_dir():
        shutil.copytree("cached-results.zarr", out / "results.zarr", dirs_exist_ok=True)
        shutil.copyfile("cached-answer.json", out / "answer.json")
        shutil.copyfile("cached-report.md", out / "report.md")
        return
    params = json.loads((Path(args.inputs) / "instance.json").read_text())
    init = int(params["init_month"])
    conventions = {}
    if defect == "thirty_days":
        conventions["month_lengths"] = "thirty_days"
    if defect == "full_record":
        conventions["thresholds"] = "full_record"
    if defect == "bilinear_residual":
        conventions.update(obs_regridding="bilinear", ereg_variance="residual")
    with tempfile.TemporaryDirectory(prefix="outlook-acquired-") as temporary:
        acquire(args.inputs, temporary, 8 if (defect == "wrong_initialization" and init == 2) else 2 if defect == "wrong_initialization" else init)
        if defect == "wrong_initialization":
            # the files of the other initialization are stored under this instance's names, so the pipeline runs on the wrong season
            other = 8 if init == 2 else 2
            for folder in ("models/ccsm4", "models/geoss2s", "models/cansipsic4", "models/cfsv2"):
                src = Path(temporary) / folder / f"precip_init{other:02d}.nc"
                with xr.open_dataset(src) as ds:
                    swapped = ds.load()
                swapped = swapped.assign_coords(init_time=[np.datetime64(f"{int(y)}-{init:02d}-01") for y in swapped["init_time"].dt.year.values])
                swapped.to_netcdf(Path(temporary) / folder / f"precip_init{init:02d}.nc")
            for folder in ("sst/cfsv2",):
                src = Path(temporary) / folder / f"sst_init{other:02d}.nc"
                with xr.open_dataset(src) as ds:
                    swapped = ds.load()
                swapped = swapped.assign_coords(init_time=[np.datetime64(f"{int(y)}-{init:02d}-01") for y in swapped["init_time"].dt.year.values])
                swapped.to_netcdf(Path(temporary) / folder / f"sst_init{init:02d}.nc")
        if defect == "independent":
            import reference_independent
            partial = reference_independent.compute(temporary, params, {}, stages=("prepare", "wvg", "ereg"))
            full = science.compute(temporary, params, {}, token=defect)
            for name in partial.data_vars:
                full[name].values[...] = partial[name].values
            result = full
        elif defect in ("wvg_leak", "ereg_no_cross_validation", "cca_future_training"):
            result = science.compute(temporary, params, conventions, token=defect, leak=defect)
        else:
            result = science.compute(temporary, params, conventions, token=defect)
    result = plant(result, defect, params, None)
    if defect == "reordered":
        result = result.isel(lat=slice(None, None, -1), lon=slice(None, None, -1), model=slice(None, None, -1)).transpose("lon", "category", "year", "model", "stream", "plat", "plon", "lat", missing_dims="ignore")
    result.to_zarr(out / "results.zarr", mode="w", zarr_format=3, consolidated=False)
    rpss = list(result["verify_stream_rpss"].values) + [float(result["verify_objective_rpss"].values)]
    claims = {"hindcast_skill": ["positive" if v > 1e-9 else "nonpositive" for v in rpss]}
    answer = {"run": {"argv": ["python", "solve.py", "--inputs", "{input_dir}", "--output", "{output_dir}"]}, "claims": claims,
              "choices": {"obs_regridding": conventions.get("obs_regridding", "conservative"), "ereg_variance": conventions.get("ereg_variance", "prediction_error")}}
    (out / "answer.json").write_text(json.dumps(answer, indent=2) + "\n")
    names = {2: "March–May", 8: "October–December"}[init]
    issued = result["issue_forecast_probability"].transpose("category", "lat", "lon").values
    share = issued[:, result["prepare_support"].transpose("lat", "lon").values > 0].mean(axis=1)
    (out / "report.md").write_text(
        f"# Objective {names} {params['forecast_year']} rainfall outlook\n\n"
        "The four NMME centres' seasonal-mean rates and CHIRPS monthly rainfall were retrieved through the task's frozen-source catalogue and hash-checked. "
        "Model fields were read in the units each delivery declares, mean rates converted to seasonal totals over the calendar length of the season, and averaged over members. "
        "CHIRPS totals were aggregated to the 0.5-degree working grid by an area-conservative mean; cells with any missing source cell are unsupported. "
        "Tercile boundaries are linear-interpolation terciles of the training years, recomputed without each year for its own hindcast.\n\n"
        "WVG: a per-cell logistic regression of below-normal occurrence on the Western-V-Gradient index (ERSST for training, CFSv2 forecast SST standardized against its own hindcasts for the forecast year); near normal is fixed at one third. "
        "eReg: per model and cell, ordinary least squares of observed on ensemble-mean rainfall with Gaussian prediction-error variance, averaged over models. "
        "CCA: per model, canonical correlation of the model rainfall field on the observed field with modes chosen by cross-validated correlation, Student-t tercile probabilities, averaged over models. "
        "The objective outlook is the equal-weight average of the three streams.\n\n"
        f"Cross-validated RPSS against equal-thirds climatology: CCA {rpss[0]:.4f}, eReg {rpss[1]:.4f}, WVG {rpss[2]:.4f}, objective {rpss[3]:.4f}. "
        f"Mean issued probabilities over supported cells (below, near, above): {share[0]:.3f}, {share[1]:.3f}, {share[2]:.3f}.\n\n"
        "Uncertainty: these are probabilities of three equally likely climatological outcomes; a 45 percent chance of above-normal rain means above-normal is the most likely of three outcomes, not a certainty, and more than half the time the season will fall in another category. "
        "Skill is modest and varies by location; the hindcast evidence covers the training years only, on this window, and the forecast year's observations were withheld.\n"
    )


if __name__ == "__main__":
    main()
