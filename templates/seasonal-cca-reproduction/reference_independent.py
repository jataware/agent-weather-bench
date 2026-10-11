"""Independent covariance-eigen implementation of the specified CCA experiment.

No primary code imports. Scalar fold construction, covariance eigendecomposition,
separate coefficient/leverage construction and explicit probability scoring.
"""
import math
from pathlib import Path

import numpy as np
import xarray as xr
from scipy.linalg import eigh, svd
from scipy.special import stdtr


def reference(inputs, params, conventions):
    with xr.open_dataset(Path(inputs) / "predictors.nc") as file:
        predictor = file.load()
    with xr.open_dataset(Path(inputs) / "targets.nc") as file:
        target = file.load()
    years = np.asarray(target.year)
    x, y = np.asarray(predictor.sst), np.asarray(target.rainfall)
    latitude_x, latitude_y = np.asarray(predictor.predictor_lat), np.asarray(target.target_lat)
    choices = [(a, b, c) for a in (1, 2, 3) for b in (1, 2, 3) for c in range(1, min(a, b) + 1)]
    weights = np.array([math.cos(math.radians(float(v))) for v in latitude_y])
    weights /= weights.sum()

    def fit(rows, modes):
        xx, yy = x[rows], y[rows]
        center_x, center_y = xx.mean(axis=0), yy.mean(axis=0)
        deviation_x, deviation_y = xx.std(axis=0, ddof=1), yy.std(axis=0, ddof=1)
        scale_x = np.sqrt(np.cos(np.deg2rad(latitude_x))) / deviation_x
        scale_y = np.sqrt(np.cos(np.deg2rad(latitude_y))) / deviation_y
        a, b = (xx - center_x) * scale_x, (yy - center_y) * scale_y
        def basis(matrix, count):
            eigenvalues, eigenvectors = eigh(matrix.T.dot(matrix))
            index = list(range(len(eigenvalues) - 1, len(eigenvalues) - count - 1, -1))
            loadings = eigenvectors[:, index]
            singular = np.sqrt(eigenvalues[index])
            return matrix.dot(loadings) / singular, loadings, singular
        ux, vx, sx = basis(a, modes[0])
        uy, vy, sy = basis(b, modes[1])
        left, strength, right_t = svd(ux.T.dot(uy), full_matrices=False, lapack_driver="gesvd")
        transform = (scale_x[:, None] * vx / sx).dot(left[:, :modes[2]])
        coefficient = (transform * strength[:modes[2]]).dot(right_t[:modes[2]]).dot(np.diag(sy)).dot(vy.T) / scale_y
        return center_x, center_y, coefficient, transform

    def predict(model, features):
        return (features - model[0]).dot(model[2]) + model[1]

    def thresholds(values):
        ordered = np.sort(values, axis=0)
        output = []
        for probability in (1 / 3, 2 / 3):
            rank = len(values) * probability + 0.5
            low = math.floor(rank)
            fraction = rank - low
            output.append(ordered[low - 1] * (1 - fraction) + ordered[low] * fraction)
        return np.array(output)

    def select(rows):
        losses = []
        for modes in choices:
            yearly = []
            for held in rows:
                if years[held] < 2001:
                    continue
                before = [i for i in rows if years[i] < years[held]]
                difference = (predict(fit(before, modes), x[held:held + 1])[0] - y[held]) / y[before].std(axis=0, ddof=1)
                yearly.append(float(np.dot(weights, difference ** 2)))
            losses.append(float(np.mean(yearly)))
        return int(np.argmin(losses)), np.array(losses)

    def distribution(rows, modes, features):
        model = fit(rows, modes)
        residuals = []
        for held in rows:
            others = [i for i in rows if i != held]
            residuals.append(y[held] - predict(fit(others, modes), x[held:held + 1])[0])
        degrees = len(rows) - modes[0] - 1
        variance = np.square(residuals).sum(axis=0) / degrees
        mean = predict(model, features)
        projections = (features - model[0]).dot(model[3])
        leverage = 1 / len(rows) + np.square(projections).sum(axis=1)
        scale = np.sqrt(variance[None, :] * (1 + leverage[:, None]))
        cuts = thresholds(y[rows])
        first = stdtr(degrees, (cuts[0] - mean) / scale)
        second = stdtr(degrees, (cuts[1] - mean) / scale)
        return np.stack((first, second - first, 1 - second), axis=-1), mean

    output = {"outer_year": np.arange(params["outer_start"], 2020), "forecast_year": np.arange(2020, 2024),
              "target": np.arange(len(latitude_y)), "system": np.arange(3), "category": np.arange(3), "boundary": np.arange(2), "candidate": np.arange(14)}
    means, probabilities, boundaries, selected, inner, losses = [], [], [], [], [], []
    for year in output["outer_year"]:
        held = int(np.where(years == year)[0][0])
        rows = list(range(len(years))) if conventions["training"] == "full_training" else [i for i in range(len(years)) if years[i] < year]
        winner, scores = select(rows)
        pp, mm = [np.full((len(latitude_y), 3), 1 / 3)], [y[rows].mean(axis=0)]
        for modes in ((1, 1, 1), choices[winner]):
            probability, mean = distribution(rows, modes, x[held:held + 1])
            pp.append(probability[0]); mm.append(mean[0])
        pp = np.array(pp)
        cuts = thresholds(y[rows])
        loss = np.empty((3, len(latitude_y)))
        for system in range(3):
            for cell in range(len(latitude_y)):
                below = float(y[held, cell] < cuts[0, cell])
                at_most_near = float(y[held, cell] < cuts[1, cell])
                loss[system, cell] = ((pp[system, cell, 0] - below) ** 2 + (pp[system, cell, :2].sum() - at_most_near) ** 2) / 2
        means.append(mm); probabilities.append(pp); boundaries.append(cuts); selected.append(winner); inner.append(scores); losses.append(loss)
    rows = list(range(len(years)))
    winner, scores = select(rows)
    features = x[len(years):]
    future_p = [np.full((4, len(latitude_y), 3), 1 / 3)]
    future_m = [np.broadcast_to(y.mean(axis=0), (4, len(latitude_y)))]
    for modes in ((1, 1, 1), choices[winner]):
        probability, mean = distribution(rows, modes, features)
        future_p.append(probability); future_m.append(mean)
    overlap = [int(np.where(years == year)[0][0]) for year in output["outer_year"]]
    full_p, full_m = distribution(rows, choices[winner], x[overlap])
    pooled = np.array(losses).mean(axis=0).dot(weights)
    output.update(hindcast_mean_mm=np.array(means), hindcast_probability=np.array(probabilities), hindcast_threshold_mm=np.array(boundaries),
                  selected_candidate=np.array(selected), inner_loss=np.array(inner), hindcast_rpss=1 - pooled / pooled[0],
                  forecast_mean_mm=np.array(future_m).transpose(1, 0, 2), forecast_probability=np.array(future_p).transpose(1, 0, 2, 3),
                  forecast_threshold_mm=thresholds(y), final_candidate=np.array(winner), final_inner_loss=scores,
                  full_fit_mean_mm=full_m, full_fit_probability=full_p)
    return output
