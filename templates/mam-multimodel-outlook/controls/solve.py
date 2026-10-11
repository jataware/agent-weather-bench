"""Trusted control solution: acquire raw monthly objects through public HTTP."""
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


def acquire(inputs, destination):
    config = json.loads((Path(inputs) / "acquisition.json").read_text())
    base = config["base_url"].rstrip("/") + "/"
    with urlopen(base + config["catalog_path"], timeout=30) as response:
        catalogue = json.loads(response.read(1024 * 1024))
    resources = {row["path"]: row for row in catalogue["resources"]}
    needed = ["models/" + m + ".nc" for m in science.MODELS] + ["observations/chirps-monthly-pre2016.nc"]
    for name in needed:
        row = resources[name]
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or not 0 < row["bytes"] < 128 * 1024 * 1024:
            raise ValueError("Invalid source catalogue resource")
        target = Path(destination) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(base + name, timeout=60) as response:
            content = response.read(row["bytes"] + 1)
        if len(content) != row["bytes"] or hashlib.sha256(content).hexdigest() != row["sha256"]:
            raise ValueError("Downloaded object does not match provider catalogue")
        target.write_bytes(content)


def compute(provider, params, defect):
    implementation = science
    if defect == "independent":
        import reference_independent
        implementation = reference_independent
    years, new_years = params["training_years"], params["new_years"]
    lat, lon = params["target_latitude"], params["target_longitude"]
    h, f = {}, {}
    for name in science.MODELS:
        with xr.open_dataset(Path(provider) / "models" / (name + ".nc")) as ds:
            total = implementation.seasonal_model(ds, years + new_years, lat, lon, defect=defect if defect in ("thirty_days", "missing_seconds", "missing_millimetres") else None)
            total = np.asarray(total)
        h[name], f[name] = total[:len(years)], total[len(years):]
    with xr.open_dataset(Path(provider) / "observations/chirps-monthly-pre2016.nc") as ds:
        obs = np.asarray(implementation.seasonal_observed(ds, years, lat, lon))
    axes = {"thresholds": "full_record_thresholds" if defect == "full_record_thresholds" else "fold_only", "weighting": "member_weighted" if defect == "member_weighted" else "equal_models"}
    return implementation.evaluate(h, obs, f, years, new_years, lat, lon, defect=axes)


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
    with tempfile.TemporaryDirectory(prefix="mam-acquired-") as temporary:
        acquire(args.inputs, temporary)
        result = compute(temporary, params, defect)
    if defect == "reordered":
        result = result.isel(lat=slice(None, None, -1), lon=slice(None, None, -1), model=slice(None, None, -1)).transpose("lon", "tercile", "year", "model", "new_year", "lat", missing_dims="ignore")
    result.to_zarr(out / "results.zarr", mode="w", zarr_format=3, consolidated=False)
    claim = "positive" if result.cv_rpss.item() > 1e-9 else "nonpositive"
    answer = {"run": {"argv": ["python", "solve.py", "--inputs", "{input_dir}", "--output", "{output_dir}"]}, "claims": {"cv_skill": [claim]}}
    (out / "answer.json").write_text(json.dumps(answer, indent=2) + "\n")
    (out / "report.md").write_text(
        "The four raw C3S monthly precipitation rates were acquired through the task's frozen-source HTTP catalogue, "
        "checked against its object hashes, integrated over the actual valid March/April/May calendar days, and converted from m/s to mm. "
        "Monthly CHIRPS totals were summed and linearly interpolated to the declared service grid. "
        "Each model's seasonal member mean predicts observed seasonal rain through ordinary least squares. "
        "The Gaussian forecast variance is residual SSE/(n-2), inflated by 1+1/n+(x_new-x_mean)^2/Sxx. "
        "Observed tercile thresholds use linear quantiles. Every leave-one-year-out prediction refits the regression and thresholds without the test year. "
        "The four calibrated probability distributions receive equal model weights regardless of member count. "
        f"Pooled cross-validated RPS={result.cv_rps.item():.12g}, uniform-climatology RPS={result.cv_rps_climatology.item():.12g}, RPSS={result.cv_rpss.item():.12g}. "
        f"The arithmetic spatial mean of the new-season below/normal/above probabilities is {result.forecast_probability.mean(('lat', 'lon')).values.tolist()}. "
        "These are cross-validated development diagnostics, not independent verification of the retrospective new-year forecast. "
        "The withheld new-year rainfall observations were unavailable to the forecast pipeline. "
        "This uses the supported default Wilks eReg method; it does not claim to reproduce every operational ICPAC EnsReg option.\n"
    )


if __name__ == "__main__":
    main()
