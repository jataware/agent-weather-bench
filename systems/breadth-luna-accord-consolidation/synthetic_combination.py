"""Public probability-combination API on invented fields; no benchmark data."""
import json

import numpy as np
import xarray as xr
from africas2s import combine_terciles


def example():
    # Ordinary, partial-vector, and all-absent cells, supplied in percent.
    coordinates = {"tercile": [0, 1, 2], "lat": [0.0], "lon": [10.0, 11.0, 12.0]}
    first = xr.DataArray(np.array([[60, 30, 10], [20, 30, 50],
                                  [np.nan, np.nan, np.nan]]).T[:, None, :],
                         dims=("tercile", "lat", "lon"), coords=coordinates) / 100
    second = xr.DataArray(np.array([[20, 30, 50], [90, np.nan, 10],
                                   [np.nan, np.nan, np.nan]]).T[:, None, :],
                          dims=first.dims, coords=coordinates) / 100
    components = {"first": first, "second": second}
    equal = combine_terciles(components, missing="drop")
    weighted = combine_terciles(components, weights={"first": 1, "second": 3},
                                missing="drop")
    np.testing.assert_allclose(equal[:, 0, 0], [.4, .3, .3])
    np.testing.assert_allclose(weighted[:, 0, 0], [.3, .3, .4])
    np.testing.assert_allclose(equal[:, 0, 1], [.2, .3, .5])
    np.testing.assert_allclose(weighted[:, 0, 1], [.2, .3, .5])
    assert bool(equal[:, 0, 2].isnull().all())
    support = sum(np.isfinite(part).all("tercile") for part in components.values())
    encoded = equal.where(support > 0, 0.0)
    np.testing.assert_array_equal(support, [[2, 1, 0]])
    np.testing.assert_array_equal(encoded[:, 0, 2], [0, 0, 0])
    np.testing.assert_allclose(encoded.where(support > 0), equal, equal_nan=True)
    return {"synthetic_only": True, "dimensions": list(equal.dims),
            "support": support.values.tolist(), "checks": "passed"}


if __name__ == "__main__":
    print(json.dumps(example()))
