"""Bounded, read-only array evidence; these diagnostics never grade a task.

Only required NetCDF outputs with a same-name controller reference are compared.
Differences are positional and remain useful when units or coordinates disagree;
they are not a scientific tolerance policy or a replacement for task checks.
"""
from contextlib import ExitStack
from pathlib import Path, PurePosixPath

import numpy as np
import xarray as xr


MAX_FIELDS = 80
MAX_VALUES = 2_000_000
MAX_FILE_VALUES = 4_000_000
MAX_ARRAY_BYTES = 32_000_000


def _open(path):
    # Disable time decoding too: CF decoding can read an untrusted time vector
    # while opening. Equal stored time coordinates include their CF metadata.
    with path.open("rb") as stream:
        engine = "scipy" if stream.read(3) == b"CDF" else "h5netcdf"
    return xr.open_dataset(path, engine=engine, create_default_indexes=False,
                           decode_times=False, decode_timedelta=False, cache=False)


def _error(exc):
    return {"type": type(exc).__name__, "detail": str(exc)[:250]}


def _attribute(value):
    """Small JSON-safe unit attributes; never return array data."""
    if value is None or isinstance(value, (str, bool, int)):
        return value[:250] if isinstance(value, str) else value
    if isinstance(value, np.generic):
        return _attribute(value.item())
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    return {"unsupported_attribute_type": type(value).__name__}


def _finite_float(value):
    with np.errstate(over="ignore", invalid="ignore"):
        result = float(value)
    return result if np.isfinite(result) else None


def _attributes_agree(actual, expected):
    """Compare complete scalar attributes before truncating display strings."""
    if isinstance(actual, np.generic):
        actual = actual.item()
    if isinstance(expected, np.generic):
        expected = expected.item()
    if not isinstance(actual, (str, bool, int, float, type(None))) or not isinstance(
            expected, (str, bool, int, float, type(None))):
        return False
    return actual == expected


def _absolute_errors(actual, expected):
    # longdouble is float64 on Apple silicon. Subtract integer magnitudes in
    # uint64 before floating conversion, preserving small int64 differences.
    # Opposite signs require addition; floating conversion cannot cancel them.
    if actual.dtype.kind in "biu" and expected.dtype.kind in "biu":
        negative_a, negative_b = actual < 0, expected < 0
        unsigned_a, unsigned_b = actual.astype(np.uint64), expected.astype(np.uint64)
        magnitude_a = np.where(negative_a, np.negative(unsigned_a), unsigned_a)
        magnitude_b = np.where(negative_b, np.negative(unsigned_b), unsigned_b)
        errors = (np.maximum(magnitude_a, magnitude_b)
                  - np.minimum(magnitude_a, magnitude_b)).astype(np.longdouble)
        opposite = negative_a != negative_b
        if np.any(opposite):
            errors[opposite] = (magnitude_a[opposite].astype(np.longdouble)
                                + magnitude_b[opposite].astype(np.longdouble))
        return errors
    return np.abs(actual.astype(np.longdouble) - expected.astype(np.longdouble))


def _metadata(array):
    return {"dimensions": list(array.dims), "shape": list(array.shape),
            "dtype": str(array.dtype)}


def _small(array):
    return (array.size <= MAX_VALUES
            and array.size * array.dtype.itemsize <= MAX_ARRAY_BYTES)


def _coordinates(actual, expected):
    names = sorted(expected.coords)
    result = {"fields": {}, "truncated_count": max(0, len(names) - MAX_FIELDS),
              "unexpected": sorted(set(actual.coords) - set(names))[:MAX_FIELDS],
              "unexpected_truncated_count": max(
                  0, len(set(actual.coords) - set(names)) - MAX_FIELDS)}
    for name in names[:MAX_FIELDS]:
        reference = expected.coords[name]
        row = {"present": name in actual.coords, "reference": _metadata(reference),
               "agrees": None}
        result["fields"][name] = row
        if not row["present"]:
            row["status"] = "missing"
            row["agrees"] = False
            continue
        submitted = actual.coords[name]
        row["actual"] = _metadata(submitted)
        if submitted.dims != reference.dims or submitted.shape != reference.shape:
            row.update(status="incompatible_dimensions_or_shape", agrees=False)
            continue
        if (not _small(reference) or not _small(submitted)
                or reference.dtype.kind not in "biufSUMm"
                or submitted.dtype.kind not in "biufSUMm"):
            row["status"] = "unsupported_or_oversized"
            continue
        try:
            a, b = submitted.values, reference.values
            values_agree = bool(np.array_equal(a, b, equal_nan=True)) if (
                a.dtype.kind in "biuf" and b.dtype.kind in "biuf") else bool(np.array_equal(a, b))
            # CF time values have meaning only together with units/calendar.
            row["cf_metadata_agrees"] = all(
                _attributes_agree(submitted.attrs.get(key), reference.attrs.get(key))
                for key in ("units", "calendar"))
            row.update(status="compared", values_agree=values_agree,
                       agrees=values_agree and row["cf_metadata_agrees"])
        except Exception as exc:
            row.update(status="read_error", error=_error(exc))
    return result


def _numeric(actual, expected):
    a, b = actual.values, expected.values
    finite_a, finite_b = np.isfinite(a), np.isfinite(b)
    paired = finite_a & finite_b
    masks = {}
    for name, operation in (("nan", np.isnan), ("positive_infinity", np.isposinf),
                            ("negative_infinity", np.isneginf),
                            ("nonfinite", lambda x: ~np.isfinite(x))):
        am, bm = operation(a), operation(b)
        masks[name] = {"actual_count": int(am.sum()), "reference_count": int(bm.sum()),
                       "mask_agrees": bool(np.array_equal(am, bm)),
                       "mask_difference_count": int(np.count_nonzero(am != bm))}
    count = int(paired.sum())
    maximum = rmse = None
    if count:
        # Scaling avoids overflow from squaring large finite differences.
        with np.errstate(over="ignore", invalid="ignore"):
            errors = _absolute_errors(a[paired], b[paired])
            high = errors.max()
            maximum = _finite_float(high)
            rmse = _finite_float(high * np.sqrt(np.mean((errors / high) ** 2))) if high else 0.0
    return {"status": "compared", "pairing": "positional", "finite_paired_count": count,
            "max_abs_error": maximum, "rmse": rmse, "missing_nonfinite": masks}


def _field(actual, expected, name, reference_small):
    reference = expected[name]
    required_units = reference.attrs.get("units")
    present = actual is not None and name in actual.data_vars
    row = {"present": present, "reference": _metadata(reference),
           "units": {"required": required_units is not None,
                     "reference": _attribute(required_units), "actual": None,
                     "status": "not_required" if required_units is None else "missing"},
           "dimensions_agree": None, "shape_agrees": None,
           "numeric": {"status": "missing"}}
    if not present:
        return row
    submitted = actual[name]
    row["actual"] = _metadata(submitted)
    row["dimensions_agree"] = submitted.dims == reference.dims
    row["shape_agrees"] = submitted.shape == reference.shape
    units = submitted.attrs.get("units")
    row["units"]["actual"] = _attribute(units)
    if required_units is not None:
        row["units"]["status"] = ("missing" if units is None else
                                  "match" if _attributes_agree(units, required_units) else "mismatch")
    # These gates precede all coordinate and data loads from the actual field.
    if not row["dimensions_agree"] or not row["shape_agrees"]:
        row["numeric"]["status"] = "incompatible_dimensions_or_shape"
        row["coordinates"] = {"status": "not_loaded_incompatible_dimensions_or_shape"}
    elif reference.dtype.kind not in "biuf" or submitted.dtype.kind not in "biuf":
        row["numeric"]["status"] = "unsupported_dtype"
    elif not reference_small or not _small(reference) or not _small(submitted):
        row["numeric"]["status"] = "not_loaded_size_limit"
    else:
        row["coordinates"] = _coordinates(submitted, reference)
        try:
            row["numeric"] = _numeric(submitted, reference)
        except Exception as exc:
            row["numeric"] = {"status": "read_error", "error": _error(exc)}
    return row


def array_diagnostics(submission, private, outputs):
    """Return finite/null JSON evidence without executing or changing submissions.

    ``private`` is the task-private directory containing ``controller/``.
    Unrequired files are never inspected. A required output without a same-name
    reference is explicitly skipped, so this is not an oracle for hidden inputs.
    """
    submission, controller = Path(submission), Path(private) / "controller"
    result = {"schema_version": 1, "graded": False,
              "limits": {"fields_per_file": MAX_FIELDS, "values_per_array": MAX_VALUES,
                         "reference_values_per_file": MAX_FILE_VALUES,
                         "bytes_per_array": MAX_ARRAY_BYTES}, "files": {}}
    for name in dict.fromkeys(outputs):
        if not isinstance(name, str) or not name.lower().endswith(".nc"):
            continue
        row = {"status": "pending", "fields": {}}
        result["files"][name] = row
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name:
            row["status"] = "invalid_output_path"
            continue
        reference_path, actual_path = controller / name, submission / name
        if not reference_path.is_file():
            row["status"] = "no_same_name_controller_reference"
            continue
        try:
            unsafe = (not reference_path.resolve().is_relative_to(controller.resolve())
                      or not actual_path.resolve().is_relative_to(submission.resolve())
                      or reference_path.is_symlink() or actual_path.is_symlink())
        except (OSError, RuntimeError):
            unsafe = True
        if unsafe:
            row["status"] = "unsafe_path"
            continue
        with ExitStack() as stack:
            try:
                expected = stack.enter_context(_open(reference_path))
            except Exception as exc:
                row.update(status="invalid_reference", error=_error(exc))
                continue
            names = sorted(expected.data_vars)
            row.update(reference_field_count=len(names),
                       truncated_field_count=max(0, len(names) - MAX_FIELDS))
            # Bound whole-file reference work as well as each individual array.
            reference_small = sum(v.size for v in expected.variables.values()) <= MAX_FILE_VALUES
            actual = None
            if not actual_path.is_file():
                row["status"] = "missing_submission_file"
            else:
                try:
                    actual = stack.enter_context(_open(actual_path))
                    row["status"] = "inspected"
                except Exception as exc:
                    row.update(status="invalid_submission_file", error=_error(exc))
            unexpected = sorted(set(actual.data_vars) - set(names)) if actual is not None else []
            row.update(unexpected_fields=unexpected[:MAX_FIELDS],
                       unexpected_fields_truncated_count=max(0, len(unexpected) - MAX_FIELDS))
            for field in names[:MAX_FIELDS]:
                row["fields"][field] = _field(actual, expected, field, reference_small)
    return result
