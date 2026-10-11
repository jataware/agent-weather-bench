"""Controller-only sensitivity analysis; never changes the benchmark score.

Resample paired consecutive issue blocks and retain every spatial cell together.
Intervals describe sensitivity to sampled issues, not uncertainty about other
regions, data vintages, repeated agent attempts or future climate conditions.
"""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment.compare import align, read_results
from assessment.spec import Template

RUN = "20261008T091951-weeks34-rainfall-final-2018-2021--all-cells-L1-checkpoint-astra-rhiza-d6653d"


def analyze():
    folder = ROOT / "var/template-runs" / RUN
    meta = json.loads((folder / "run.json").read_text())
    template = Template(meta["template"])
    if template.fingerprint() != meta["fingerprint"]:
        raise ValueError("Historical scoring contract changed")
    results, problems = read_results(template.spec["results"], folder / "frozen")
    if problems:
        raise ValueError(problems)
    results = align(template.spec["results"], results,
                    template.hooks.expected_coordinates(folder / "inputs", meta["instance"]))
    training, _, final = template.hooks.splits(template.private, meta["instance"])
    if not np.all(np.diff(final.issue_time.values) == np.timedelta64(7, "D")):
        raise ValueError("This diagnostic assumes weekly issues")
    truth = final.precipitation.values
    weights = np.cos(np.deg2rad(final.latitude.values))
    methods = {"agent": results["final_mm"], "raw_model": final.raw_cfsv2.values,
               "climatology": template.hooks.climatology(training, final.issue_time.values)}
    losses = {name: np.average((pred - truth) ** 2, axis=1, weights=weights)
              for name, pred in methods.items()}
    n, draws, seed = len(truth), 4000, 20261008
    rows = []
    for block in (4, 8, 13):
        rng = np.random.default_rng(seed + block)
        # Non-circular moving blocks: no artificial join between 2021 and 2018.
        starts = rng.integers(0, n - block + 1, size=(draws, int(np.ceil(n / block))))
        indices = (starts[..., None] + np.arange(block)).reshape(draws, -1)[:, :n]
        rmse = {name: np.sqrt(value[indices].mean(axis=1)) for name, value in losses.items()}
        for baseline in ("raw_model", "climatology"):
            skill = 1 - rmse["agent"] / rmse[baseline]
            rows.append({"block_weeks": block, "baseline": baseline,
                         "skill": float(1 - np.sqrt(losses["agent"].mean() / losses[baseline].mean())),
                         "percentile_95_interval": np.quantile(skill, [.025, .975]).tolist()})
    return {"run": RUN, "issues": n, "cells": int(final.sizes["location"]),
            "draws": draws, "seed": seed,
            "method": "Paired non-circular moving-block bootstrap; spatial cells retained together.",
            "limits": "Exploratory sampling sensitivity, not a model-ranking confidence interval. One submission, four historical years, public data; seasonal stationarity is not established.",
            "rows": rows}


if __name__ == "__main__":
    result = analyze()
    (ROOT / "experiments/checkpoint-skill-uncertainty-2026-10-08.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
