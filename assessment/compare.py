"""Read named results from a labelled array store, and compare them by coordinate label.

Arrays are delivered in a Zarr store with named dimensions and coordinate arrays.
The controller matches every array to its own by dimension name and by label, so
neither the order of the dimensions nor the order of the labels can be misread.
"""
import warnings
from pathlib import Path

import numpy as np

STORE = "results.zarr"
UNIT_ROUNDOFF = {"float32": 2.0 ** -24, "float64": 2.0 ** -53}


class EnvelopeError(ValueError):
    """The submission does not contain the results in a usable form."""


def tolerance(declared):
    """The absolute tolerance a spec declares for one result.

    Two correct implementations that each perform at most `operations` rounded
    operations, on quantities no larger than `magnitude`, in arithmetic of the
    stated `precision`, differ by at most 2 * gamma_n * magnitude, where
    gamma_n = n u / (1 - n u) and u is the unit roundoff. A difference inside that
    bound is no evidence of a different method; a larger one is.
    """
    if declared.get("exact") is True and len(declared) == 1:
        return 0.0
    precision, operations, magnitude = declared.get("precision"), declared.get("operations"), declared.get("magnitude")
    if precision not in UNIT_ROUNDOFF or type(operations) is not int or operations < 1 or not isinstance(magnitude, (int, float)) or magnitude <= 0:
        raise ValueError("A tolerance is {exact: true} or {precision: float32|float64, operations: n, magnitude: m}")
    n = operations * UNIT_ROUNDOFF[precision]
    return 2 * n / (1 - n) * magnitude


def _dates(values):
    """Date labels as YYYY-MM-DD text, from datetimes or from ISO text. None when they are neither."""
    values = np.asarray(values)
    if values.dtype.kind == "M":
        return np.datetime_as_string(values, unit="D").astype(str)
    if values.dtype.kind in "USOT":
        try:
            return np.datetime_as_string(np.array([np.datetime64(str(value)[:10], "D") for value in values.ravel()]), unit="D").astype(str)
        except ValueError:
            return None
    return None


def read_results(results_spec, folder, answer=None, store=None):
    """(named results as arrays in the spec's dimension order, {name: why a result is unusable}).

    Arrays come from `results.zarr` in `folder`, or from the store named; a result that
    is a single number may instead be given in the `results` section of answer.json.
    """
    import xarray as xr
    store = Path(folder) / STORE if store is None else Path(store)
    if not store.is_dir():
        raise EnvelopeError(f"There is no {STORE} store")
    if any(path.is_symlink() for path in store.rglob("*")):
        raise EnvelopeError(f"{STORE} contains links; it must hold its own files")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            dataset = xr.open_zarr(store, chunks=None).load()
    except Exception as error:                                     # any unreadable store is the submission's problem
        raise EnvelopeError(f"{STORE} cannot be opened as a labelled array store: {type(error).__name__}: {str(error)[:200]}") from None
    scalars = answer.get("results") if isinstance(answer, dict) and isinstance(answer.get("results"), dict) else {}
    raw, problems = {}, {}
    for name, row in results_spec.items():
        dims = [name] if row.get("kind") == "coordinate" else list(row.get("dims", []))
        if name not in dataset.variables:
            if not dims and name in scalars:
                raw[name] = scalars[name]
            elif not dims:
                problems[name] = f"{name} is missing from {STORE} and from the results section of answer.json"
            elif row.get("kind") == "coordinate":
                problems[name] = f"{STORE} has no coordinate array {name}"
            else:
                problems[name] = f"{name} is missing from {STORE}"
            continue
        variable = dataset[name]
        if set(variable.dims) != set(dims) or len(variable.dims) != len(dims):
            problems[name] = f"{name} has dimensions ({', '.join(map(str, variable.dims)) or 'none'}); the brief asks for ({', '.join(dims) or 'none'})"
            continue
        values = variable.transpose(*dims).values
        if row.get("dtype") == "date":
            values = _dates(values)
            if values is None:
                problems[name] = f"{name} must hold dates, as datetimes or as YYYY-MM-DD text"
                continue
        raw[name] = values
    out, more = usable(results_spec, raw)
    return out, {**more, **problems}


def usable(results_spec, raw):
    """(usable results as arrays, {name: why a result is unusable}). One bad result does not hide the others."""
    if not isinstance(raw, dict):
        raise EnvelopeError("results must be an object of named quantities")
    out, problems = {}, {}
    for name, row in results_spec.items():
        if name not in raw:
            problems[name] = f"{name} is missing"
        elif row.get("dtype") == "date":
            value = _dates(raw[name])
            if value is None or value.ndim != 1:
                problems[name] = f"{name} must be a list of dates"
            else:
                out[name] = value
        else:
            try:
                value = np.asarray(raw[name], dtype=float)
            except (TypeError, ValueError):
                problems[name] = f"{name} is not a rectangular array of numbers"
                continue
            expected = 1 if row.get("kind") == "coordinate" else len(row.get("dims", []))
            if value.ndim != expected:
                problems[name] = f"{name} has {value.ndim} dimensions; the brief asks for {expected}"
            elif not np.isfinite(value).all():
                problems[name] = f"{name} contains missing or infinite values"
            else:
                out[name] = value
    for name, row in results_spec.items():
        for axis, dim in enumerate(row.get("dims", [])):
            if name in out and dim in out and out[name].shape[axis] != out[dim].shape[0]:
                problems[name] = f"{name} does not match the length of {dim}"
                del out[name]
                break
    return out, problems


def normalise(results_spec, raw):
    """Every named result as an array, or an EnvelopeError naming the first that is unusable."""
    out, problems = usable(results_spec, raw)
    if problems:
        raise EnvelopeError("; ".join(problems[name] for name in results_spec if name in problems))
    return out


def summary(results_spec, results):
    """A short text description of the results, for a reader who cannot open the store."""
    lines = []
    for name, row in results_spec.items():
        if name not in results:
            lines.append(f"{name}: unusable")
            continue
        value = results[name]
        if row.get("kind") == "coordinate":
            shown = ", ".join(str(item) for item in value[:12]) + (", ..." if len(value) > 12 else "")
            lines.append(f"{name} (coordinate, {len(value)} labels): {shown}")
        elif value.ndim == 0:
            lines.append(f"{name}: {float(value):.6g}")
        else:
            lines.append(f"{name}[{', '.join(row['dims'])}] shape {tuple(value.shape)}: min {value.min():.6g}, mean {value.mean():.6g}, max {value.max():.6g}")
    return "\n".join(lines) + "\n"


def _order(submitted, reference, atol):
    """Positions in `submitted` of each reference coordinate value, or None if the sets differ."""
    if submitted.shape != reference.shape or (submitted.dtype.kind == "U") != (reference.dtype.kind == "U"):
        return None
    order, used = [], set()
    for value in reference:
        near = submitted == value if submitted.dtype.kind == "U" else np.abs(submitted - value) <= atol
        hits = [i for i in np.flatnonzero(near) if i not in used]
        if not hits:
            return None
        order.append(int(hits[0])); used.add(int(hits[0]))
    return order


def compare(results_spec, submitted, reference):
    """(all results agree, per-result detail). Arrays are realigned to the reference coordinates."""
    orders = {name: _order(submitted[name], reference[name], row.get("tolerance", {}).get("atol", 0)) if name in submitted else None
              for name, row in results_spec.items() if row.get("kind") == "coordinate" and name in reference}
    detail, agree = {}, True
    results_spec = {name: row for name, row in results_spec.items() if name in reference}
    for name, row in results_spec.items():
        if name not in submitted:                                  # an unusable result agrees with nothing
            detail[name] = {"agrees": False, "largest_difference": None}
            agree = False
            continue
        if row.get("kind") == "coordinate":
            ok, gap = orders[name] is not None, None
        else:
            value, ok, gap = submitted[name], True, None
            for axis, dim in enumerate(row.get("dims", [])):
                if dim in orders:
                    if orders[dim] is None:
                        ok = False
                        break
                    value = np.take(value, orders[dim], axis=axis)
            if ok and value.shape != reference[name].shape:
                ok = False
            if ok:
                gap = float(np.max(np.abs(value - reference[name]))) if value.size else 0.0
                ok = gap <= row["tolerance"]["atol"]
        detail[name] = {"agrees": ok, "largest_difference": gap}
        agree &= ok
    return agree, detail


def align(results_spec, submitted, frame):
    """The submitted arrays reordered to the expected coordinates, or an EnvelopeError naming the gap.

    `frame` holds the exact coordinate values a submission must cover. Used where
    there is no reference answer, only a required set of cases.
    """
    orders = {}
    for name, expected in frame.items():
        if name not in submitted:
            raise EnvelopeError(f"{name} is missing or unusable")
        order = _order(submitted[name], expected, results_spec[name].get("tolerance", {}).get("atol", 0))
        if order is None:
            raise EnvelopeError(f"{name} does not list exactly the {len(expected)} expected values (it has {len(submitted[name])})")
        orders[name] = order
    out = {name: frame[name] for name in frame}
    for name, row in results_spec.items():
        if name in frame or name not in submitted:
            continue
        value = submitted[name]
        for axis, dim in enumerate(row.get("dims", [])):
            if dim in orders:
                value = np.take(value, orders[dim], axis=axis)
        out[name] = value
    return out
