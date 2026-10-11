"""Regression for the equivalent edge formula discovered in real attempts."""
import numpy as np

from assessment.compare import compare
from assessment.spec import Template


def test_equivalent_pixel_edges_pass_but_wrong_radius_does_not():
    template = Template("rainfall-downscaling")
    spec = {n: template.spec["results"][n] for n in ("latitude", "longitude", "area_m2")}
    lat = np.arange(40, dtype=float) * .05 + .525
    lon = np.arange(40, dtype=float) * .05 + 36.525
    strip = (np.sin(np.deg2rad(lat + .025)) - np.sin(np.deg2rad(lat - .025)))[:, None]
    radius = 6371000.
    reference = {"latitude": lat, "longitude": lon,
                 "area_m2": radius**2 * strip * np.full((1, len(lon)), np.deg2rad(.05))}
    for width in (np.deg2rad((lon + .025) - (lon - .025)),
                  np.deg2rad(lon + .025) - np.deg2rad(lon - .025)):
        submitted = {**reference, "area_m2": radius**2 * strip * width[None, :]}
        # This exceeds the old final-magnitude bound on real-scale coordinates.
        assert np.max(np.abs(submitted["area_m2"] - reference["area_m2"])) > 3.6e-7
        assert compare(spec, submitted, reference)[0]
    assert spec["area_m2"]["tolerance"]["atol"] < 1e-3
    wrong = {**reference, "area_m2": (radius + 1)**2 * strip * np.full((1, len(lon)), np.deg2rad(.05))}
    assert not compare(spec, wrong, reference)[0]
