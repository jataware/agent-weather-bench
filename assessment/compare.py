"""Compare named results by value and by coordinate label, never by storage order."""
import numpy as np


class EnvelopeError(ValueError):
    """The submission does not contain the results in a usable form."""


def regroup(results_spec, raw, dim, labels):
    """Accept results grouped by the labels of their leading dimension, and return them as arrays.

    A brief may ask for `change_mm[period][latitude][longitude]`. An answer that gives
    `{"2026-10-04": {"change_mm": [[...]]}, ...}`, at the top level or under `periods`,
    holds the same information and is read as the same thing. Anything else is left alone.
    """
    if dim is None or not isinstance(raw, dict):
        return raw, False
    grouped = raw.get(dim + "s") if isinstance(raw.get(dim + "s"), dict) else raw
    if not labels or not all(isinstance(grouped.get(label), dict) for label in labels):
        return raw, False
    out = {key: value for key, value in raw.items() if key not in labels and key != dim + "s"}
    for name, row in results_spec.items():
        if name not in out and (row.get("dims") or [None])[0] == dim and all(name in grouped[label] for label in labels):
            out[name] = [grouped[label][name] for label in labels]
    return out, True


def usable(results_spec, raw):
    """(usable results as arrays, {name: why a result is unusable}). One bad result does not hide the others."""
    if not isinstance(raw, dict):
        raise EnvelopeError("results must be an object of named quantities")
    out, problems = {}, {}
    for name, row in results_spec.items():
        if name not in raw:
            problems[name] = f"{name} is missing"
        elif row.get("dtype") == "string":
            if isinstance(raw[name], list) and all(isinstance(item, str) for item in raw[name]):
                out[name] = np.array(raw[name], dtype=str)
            else:
                problems[name] = f"{name} must be a list of strings"
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
    """Every named result as a float array, or an EnvelopeError naming the first that is unusable."""
    out, problems = usable(results_spec, raw)
    if problems:
        raise EnvelopeError("; ".join(problems[name] for name in results_spec if name in problems))
    return out


def _order(submitted, reference, atol):
    """Positions in `submitted` of each reference coordinate value, or None if the sets differ."""
    if submitted.shape != reference.shape:
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
                tolerance = row["tolerance"]
                gap = float(np.max(np.abs(value - reference[name]))) if value.size else 0.0
                ok = bool(np.allclose(value, reference[name], atol=tolerance["atol"], rtol=tolerance.get("rtol", 0)))
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
