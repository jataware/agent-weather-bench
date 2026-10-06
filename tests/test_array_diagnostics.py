"""The same tests run from staging and after copying into the repository."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
import xarray as xr
from xarray.backends import BackendArray
from xarray.core import indexing


_spec = importlib.util.spec_from_file_location(
    "staged_array_diagnostics", Path(__file__).resolve().parents[1] / "weatherbench/diagnostics.py")
diagnostics = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(diagnostics)


@pytest.fixture
def directories(tmp_path):
    submission, private = tmp_path / "submission", tmp_path / "private"
    submission.mkdir()
    (private / "controller").mkdir(parents=True)
    return submission, private


def dataset(values=(1.0, 2.0), *, units="mm", x=(10, 20)):
    ds = xr.Dataset({"rain": ("x", np.array(values, dtype=np.float64))}, coords={"x": list(x)})
    if units is not None:
        ds.rain.attrs["units"] = units
    return ds


def compare(directories, actual, expected, outputs=("result.nc",)):
    submission, private = directories
    expected.to_netcdf(private / "controller/result.nc", engine="h5netcdf")
    actual.to_netcdf(submission / "result.nc", engine="h5netcdf")
    result = diagnostics.array_diagnostics(submission, private, outputs)
    json.dumps(result, allow_nan=False)
    return result


def field(result):
    return result["files"]["result.nc"]["fields"]["rain"]


def test_missing_units_and_numeric_error_are_both_reported(directories):
    result = compare(directories, dataset((1, 5), units=None), dataset())
    row = field(result)
    assert result["graded"] is False
    assert row["units"]["status"] == "missing"
    assert row["coordinates"]["fields"]["x"]["agrees"] is True
    assert row["numeric"]["finite_paired_count"] == 2
    assert row["numeric"]["max_abs_error"] == 3
    assert row["numeric"]["rmse"] == pytest.approx(3 / np.sqrt(2))
    assert "pass" not in row and "fail" not in row


def test_coordinate_shift_does_not_hide_positional_differences(directories):
    row = field(compare(directories, dataset((2, 4), x=(11, 21)), dataset()))
    assert row["coordinates"]["fields"]["x"]["agrees"] is False
    assert row["numeric"]["pairing"] == "positional"
    assert row["numeric"]["max_abs_error"] == 2


def test_reference_nan_mask_and_infinities_are_explicit(directories):
    row = field(compare(directories, dataset((2, 3, np.inf), x=(0, 1, 2)),
                        dataset((1, np.nan, -np.inf), x=(0, 1, 2))))
    numeric = row["numeric"]
    assert numeric["finite_paired_count"] == 1
    assert numeric["max_abs_error"] == numeric["rmse"] == 1
    assert numeric["missing_nonfinite"]["nan"] == {
        "actual_count": 0, "reference_count": 1,
        "mask_agrees": False, "mask_difference_count": 1}
    assert numeric["missing_nonfinite"]["positive_infinity"]["actual_count"] == 1
    assert numeric["missing_nonfinite"]["negative_infinity"]["reference_count"] == 1


def test_no_finite_pairs_return_null_error_statistics(directories):
    row = field(compare(directories, dataset((np.nan, np.inf)), dataset((np.nan, np.inf))))
    assert row["numeric"]["finite_paired_count"] == 0
    assert row["numeric"]["max_abs_error"] is None
    assert row["numeric"]["rmse"] is None


def test_optional_units_are_not_graded(directories):
    row = field(compare(directories, dataset(units="dimensionless"), dataset(units=None)))
    assert row["units"] == {"required": False, "reference": None,
                            "actual": "dimensionless", "status": "not_required"}
    assert row["numeric"]["max_abs_error"] == 0


def test_float_roundoff_is_reported_without_a_numeric_failure(directories):
    row = field(compare(directories, dataset((1 + 2e-15, 2)), dataset()))
    assert 0 < row["numeric"]["max_abs_error"] < 1e-14
    assert row["numeric"]["status"] == "compared"
    assert "tolerance" not in row["numeric"]


class NeverLoad(BackendArray):
    def __init__(self, shape, dtype=np.dtype("float64")):
        self.shape, self.dtype = shape, dtype

    def __getitem__(self, key):
        raise AssertionError("Untrusted values must not be loaded")


def lazy_dataset(shape, dims=("x",), dtype=np.dtype("float64")):
    variable = xr.Variable(dims, indexing.LazilyIndexedArray(NeverLoad(shape, dtype)))
    return xr.Dataset({"rain": variable})


def mocked_compare(monkeypatch, directories, actual, expected):
    submission, private = directories
    (submission / "result.nc").touch()
    (private / "controller/result.nc").touch()
    monkeypatch.setattr(diagnostics, "_open", lambda path: expected if path.parent.name == "controller" else actual)
    result = diagnostics.array_diagnostics(submission, private, ["result.nc"])
    json.dumps(result, allow_nan=False)
    return field(result)


def test_huge_shape_is_rejected_without_loading_values(monkeypatch, directories):
    row = mocked_compare(monkeypatch, directories, lazy_dataset((10**12,)), dataset())
    assert row["shape_agrees"] is False
    assert row["actual"]["shape"] == [10**12]
    assert row["numeric"]["status"] == "incompatible_dimensions_or_shape"
    assert row["coordinates"]["status"] == "not_loaded_incompatible_dimensions_or_shape"


def test_wrong_dimensions_do_not_load_even_matching_shape(monkeypatch, directories):
    row = mocked_compare(monkeypatch, directories, lazy_dataset((2,), dims=("other",)), dataset())
    assert row["shape_agrees"] is True and row["dimensions_agree"] is False
    assert row["numeric"]["status"] == "incompatible_dimensions_or_shape"


def test_large_matching_reference_is_not_loaded(monkeypatch, directories):
    huge = (diagnostics.MAX_VALUES + 1,)
    row = mocked_compare(monkeypatch, directories, lazy_dataset(huge), lazy_dataset(huge))
    assert row["numeric"]["status"] == "not_loaded_size_limit"


@pytest.mark.parametrize("dtype", [np.dtype("complex128"), np.dtype("object")])
def test_unsupported_types_do_not_load(monkeypatch, directories, dtype):
    row = mocked_compare(monkeypatch, directories, lazy_dataset((2,), dtype=dtype), dataset())
    assert row["numeric"]["status"] == "unsupported_dtype"


def test_unknown_and_unrequired_outputs_do_not_open_oracles(monkeypatch, directories):
    submission, private = directories
    (private / "controller/hidden.nc").touch()
    (submission / "hidden.nc").touch()
    (submission / "unknown.nc").touch()

    def no_open(path):
        raise AssertionError(f"Should not inspect {path}")

    monkeypatch.setattr(diagnostics, "_open", no_open)
    result = diagnostics.array_diagnostics(submission, private, ["unknown.nc", "answer.json"])
    assert list(result["files"]) == ["unknown.nc"]
    assert result["files"]["unknown.nc"]["status"] == "no_same_name_controller_reference"
    assert result["files"]["unknown.nc"]["fields"] == {}


@pytest.mark.parametrize("contents,status", [(None, "missing_submission_file"),
                                           (b"invalid", "invalid_submission_file")])
def test_absent_and_invalid_submission_files_are_explicit(directories, contents, status):
    submission, private = directories
    dataset().to_netcdf(private / "controller/result.nc", engine="h5netcdf")
    if contents is not None:
        (submission / "result.nc").write_bytes(contents)
    result = diagnostics.array_diagnostics(submission, private, ["result.nc"])
    assert result["files"]["result.nc"]["status"] == status
    assert field(result)["present"] is False
    assert field(result)["numeric"]["status"] == "missing"
    json.dumps(result, allow_nan=False)


def test_missing_field_is_explicit(directories):
    row = field(compare(directories, dataset().rename({"rain": "wrong"}), dataset()))
    assert row["present"] is False
    assert row["numeric"]["status"] == "missing"


def test_reference_and_unexpected_field_truncation_are_recorded(directories):
    expected = xr.Dataset({f"field_{i:03}": ("x", [float(i)]) for i in range(85)})
    actual = xr.Dataset({f"extra_{i:03}": ("x", [float(i)]) for i in range(83)})
    row = compare(directories, actual, expected)["files"]["result.nc"]
    assert len(row["fields"]) == len(row["unexpected_fields"]) == 80
    assert row["reference_field_count"] == 85
    assert row["truncated_field_count"] == 5
    assert row["unexpected_fields_truncated_count"] == 3


def test_open_uses_no_default_indexes_and_no_time_decoding(monkeypatch, tmp_path):
    path = tmp_path / "result.nc"
    path.write_bytes(b"CDF")
    called = {}

    def capture(path, **kwargs):
        called.update(kwargs)
        return xr.Dataset()

    monkeypatch.setattr(diagnostics.xr, "open_dataset", capture)
    diagnostics._open(path).close()
    assert called["create_default_indexes"] is False
    assert called["decode_times"] is False
    assert called["decode_timedelta"] is False


def test_scipy_netcdf_is_supported(directories):
    submission, private = directories
    dataset().to_netcdf(private / "controller/result.nc", engine="scipy")
    dataset((2, 2)).to_netcdf(submission / "result.nc", engine="scipy")
    result = diagnostics.array_diagnostics(submission, private, ["result.nc"])
    assert field(result)["numeric"]["max_abs_error"] == 1


@pytest.mark.parametrize("actual,expected", [
    (np.array([2**63 - 1], dtype=np.int64), np.array([2**63 - 2], dtype=np.int64)),
    (np.array([-2**63], dtype=np.int64), np.array([-2**63 + 1], dtype=np.int64)),
    (np.array([2**64 - 1], dtype=np.uint64), np.array([2**64 - 2], dtype=np.uint64)),
    (np.array([2**63 - 1], dtype=np.int64), np.array([2**63], dtype=np.uint64)),
])
def test_integer_differences_survive_float64_longdouble(monkeypatch, actual, expected):
    monkeypatch.setattr(diagnostics.np, "longdouble", np.float64)
    row = diagnostics._numeric(xr.DataArray(actual), xr.DataArray(expected))
    assert row["max_abs_error"] == row["rmse"] == 1


def test_opposite_integer_signs_do_not_wrap():
    actual = xr.DataArray(np.array([-2**63, -1], dtype=np.int64))
    expected = xr.DataArray(np.array([2**64 - 1, 2], dtype=np.uint64))
    row = diagnostics._numeric(actual, expected)
    assert row["max_abs_error"] == float(3 * 2**63 - 1)
    assert np.isfinite(row["rmse"])


def test_truncated_unit_display_does_not_hide_metadata_difference(directories):
    prefix = "u" * 250
    row = field(compare(directories, dataset(units=prefix + "actual"),
                        dataset(units=prefix + "reference")))
    assert row["units"]["actual"] == row["units"]["reference"] == prefix
    assert row["units"]["status"] == "mismatch"


@pytest.mark.parametrize("target", ["self", "outside", "inside"])
def test_submission_symlinks_are_not_opened(monkeypatch, directories, target):
    submission, private = directories
    dataset().to_netcdf(private / "controller/result.nc", engine="h5netcdf")
    path = submission / "result.nc"
    destination = {"self": path, "outside": private / "controller/result.nc",
                   "inside": submission / "other.nc"}[target]
    path.symlink_to(destination)
    monkeypatch.setattr(diagnostics, "_open", lambda path: pytest.fail("Unsafe path opened"))
    result = diagnostics.array_diagnostics(submission, private, ["result.nc"])
    assert result["files"]["result.nc"]["status"] == "unsafe_path"


def test_whole_reference_file_limit_prevents_value_reads(monkeypatch, directories):
    variables = {"rain": lazy_dataset((1_000_000,)).rain.variable}
    variables.update({f"other_{i}": lazy_dataset((1_000_000,)).rain.variable for i in range(4)})
    row = mocked_compare(monkeypatch, directories, lazy_dataset((1_000_000,)), xr.Dataset(variables))
    assert row["numeric"]["status"] == "not_loaded_size_limit"
