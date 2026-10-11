"""Trusted control; its scientific implementation is shipped as science.py."""
import argparse
import json
from pathlib import Path

import xarray as xr

import science


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    variant_path = Path(__file__).with_name("variant.json")
    variant = json.loads(variant_path.read_text()) if variant_path.exists() else {}
    forecast, hindcast, state = science.build(args.inputs, variant.get("defect"))
    coords = {"train_year": hindcast.year.values, "forecast_year": forecast.year.values, "latitude": forecast.lat.values,
              "longitude": forecast.lon.values, "coarse_cell": forecast.coarse_cell.values}
    data = xr.Dataset({
        "hindcast_mm": (("train_year", "latitude", "longitude"), hindcast.rainfall_mm.values),
        "hindcast_coarse_mm": (("train_year", "coarse_cell"), hindcast.mapped_coarse_mm.values),
        "forecast_mm": (("forecast_year", "latitude", "longitude"), forecast.rainfall_mm.values),
        "forecast_coarse_mm": (("forecast_year", "coarse_cell"), forecast.mapped_coarse_mm.values),
        "area_m2": (("latitude", "longitude"), forecast.area_m2.values),
        "coarse_cell_id": (("latitude", "longitude"), forecast.coarse_cell_id.values)}, coords=coords)
    if variant.get("defect") == "break_conservation":
        data["forecast_mm"] *= 1.2
    if variant.get("defect") == "negative":
        data["forecast_mm"] *= -1
    data.to_zarr(output / "results.zarr", mode="w", zarr_format=3, consolidated=False)
    answer = {"run": {"argv": ["python", "solve.py", "--inputs", "{input_dir}", "--output", "{output_dir}"]},
              "claims": {"raw_unit_status": ["unresolved_source_scale"], "conservation_definition": ["mapped_coarse_area_mean"]}}
    if variant.get("defect") == "false_claim":
        answer["claims"]["raw_unit_status"] = ["verified_daily_rate"]
    (output / "answer.json").write_text(json.dumps(answer) + "\n")
    (output / "model.json").write_text(json.dumps(state) + "\n")
    (output / "report.md").write_text("Raw predictor units are unresolved; native mm/day metadata conflicts with source magnitudes. I used these as monotonic calibration predictors, without a day-count conversion. Fine CHIRPS data supply physical mm. The mapped coarse area mean is conserved. Rank mapping clamps tails. Hindcasts exclude their year from both fits, retrospectively; they are not historical real-time forecasts. This is a regional adaptation, not Wood et al.'s hydrological experiment.\n")
