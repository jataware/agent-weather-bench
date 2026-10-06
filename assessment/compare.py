"""Compare named results by value and by coordinate label, never by storage order."""
import numpy as np


class EnvelopeError(ValueError):
    """The submission does not contain the results in a usable form."""


def normalise(results_spec, raw):
    """Named results as float arrays, with the number of dimensions the spec states."""
    if not isinstance(raw, dict):
        raise EnvelopeError("results must be an object of named quantities")
    missing = sorted(set(results_spec) - set(raw))
    if missing:
        raise EnvelopeError("results lacks: " + ", ".join(missing))
    out = {}
    for name, row in results_spec.items():
        try:
            value = np.asarray(raw[name], dtype=float)
        except (TypeError, ValueError):
            raise EnvelopeError(f"{name} is not a rectangular array of numbers") from None
        expected = 1 if row.get("kind") == "coordinate" else len(row.get("dims", []))
        if value.ndim != expected:
            raise EnvelopeError(f"{name} has {value.ndim} dimensions; the brief asks for {expected}")
        if not np.isfinite(value).all():
            raise EnvelopeError(f"{name} contains missing or infinite values")
        out[name] = value
    for name, row in results_spec.items():
        for axis, dim in enumerate(row.get("dims", [])):
            if dim in out and out[name].shape[axis] != out[dim].shape[0]:
                raise EnvelopeError(f"{name} does not match the length of {dim}")
    return out


def _order(submitted, reference, atol):
    """Positions in `submitted` of each reference coordinate value, or None if the sets differ."""
    if submitted.shape != reference.shape:
        return None
    order, used = [], set()
    for value in reference:
        hits = [i for i in np.flatnonzero(np.abs(submitted - value) <= atol) if i not in used]
        if not hits:
            return None
        order.append(int(hits[0])); used.add(int(hits[0]))
    return order


def compare(results_spec, submitted, reference):
    """(all results agree, per-result detail). Arrays are realigned to the reference coordinates."""
    orders = {name: _order(submitted[name], reference[name], row["tolerance"]["atol"])
              for name, row in results_spec.items() if row.get("kind") == "coordinate"}
    detail, agree = {}, True
    for name, row in results_spec.items():
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
