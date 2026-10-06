"""Reference function and controller hooks for the Kenya forecast revision template.

The reference is a function of the instance parameters and a set of conventions, so
the controller can compute the answer under every reading listed in spec.yaml.
Implementation A: NumPy on arrays loaded through xarray, with lead-day arithmetic.
reference_independent.py is implementation B and shares no code with this file.
"""
import functools
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import numpy as np
import xarray as xr

HERE = Path(__file__).resolve().parent
ISSUES = ("2026-09-20", "2026-09-27")
DAY = np.timedelta64(1, "D")
INPUTS_SHARED_ACROSS_INSTANCES = True     # every instance sees the same two stores; only instance.json differs


def store_name(issue):
    return f"ECMWF_s2s_precip_{issue}.zarr"


# ---- data: frozen source bytes -> private stores -> staged agent inputs -------------

def prepare(private, source_dir=None):
    """Restore both stores from the hash-checked source archives. Idempotent."""
    private = Path(private)
    sources = json.loads((HERE / "sources.json").read_text())["stores"]
    for name, entry in sources.items():
        archive = private / "source" / entry["archive"]
        if not archive.is_file():
            if source_dir is None or not (Path(source_dir) / entry["archive"]).is_file():
                raise ValueError(f"Source archive missing: {entry['archive']}. Pass the directory that holds it.")
            archive.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(source_dir) / entry["archive"], archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != entry["archive_sha256"]:
            raise ValueError(f"Source archive hash mismatch: {entry['archive']}")
        expected = {row["path"]: row for row in entry["objects"]}
        destination = private / "stores" / name
        with zipfile.ZipFile(archive) as bundle:
            if set(bundle.namelist()) != set(expected):
                raise ValueError("Unexpected members in source archive")
            for path, row in expected.items():
                if Path(path).is_absolute() or ".." in Path(path).parts:
                    raise ValueError("Unsafe path in source archive")
                blob = bundle.read(path)
                if len(blob) != row["bytes"] or hashlib.sha256(blob).hexdigest() != row["sha256"]:
                    raise ValueError(f"Source object hash mismatch: {path}")
                target = destination / path
                if not target.is_file() or target.read_bytes() != blob:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(blob)
    return {"stores": sorted(sources), "objects": sum(len(v["objects"]) for v in sources.values())}


def stage_inputs(private, params, destination):
    """Write exactly what the agent may see: the two raw stores and instance.json."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for issue in (params["issue_previous"], params["issue_current"]):
        shutil.copytree(Path(private) / "stores" / store_name(issue), destination / store_name(issue))
    (destination / "instance.json").write_text(json.dumps(params, indent=2) + "\n")


def perturb_inputs(inputs, seed, kind="data"):
    """Change the rainfall in both staged stores so that a cached answer cannot survive.

    Adds a smooth space- and lead-dependent amount to the cumulative field, and
    lowers a few cumulative values to create clear negative increments, which makes
    the clipped and unclipped readings differ. Only the values of `tp` are rewritten,
    in place: every coordinate, attribute, chunk layout and the store's consolidated
    metadata stay exactly as the provider exported them, so any reader that works on
    the original works on the changed store.
    """
    import zarr
    rng = np.random.default_rng(seed)
    for path in sorted(Path(inputs).glob("ECMWF_s2s_precip_*.zarr")):
        group = zarr.open_group(path, mode="r+")
        array = group["tp"]
        names = list(array.metadata.dimension_names)
        order = [names.index(name) for name in ("number", "step", "latitude", "longitude")]
        values = np.transpose(np.asarray(array[...], dtype="float64"), order)
        lead = np.arange(values.shape[1], dtype="float64")       # the steps are whole days from the issue, checked by load()
        pattern = 1.5 + np.cos(np.deg2rad(40 * np.arange(values.shape[2])))[:, None] * np.sin(0.9 * np.arange(values.shape[3]) + rng.uniform(0, 3))[None, :]
        rate = rng.uniform(0.5, 1.5) * pattern                     # mm per day, differs by cell
        values += lead[None, :, None, None] * rate[None, None]
        members = rng.choice(values.shape[0], size=12, replace=False)
        steps = rng.integers(2, values.shape[1] - 2, size=12)
        for member, step in zip(members, steps):
            values[member, step] -= 4.0                            # one dip: a -4 mm then +4 mm increment
        values = np.round(values * 32) / 32                         # keep the source's 1/32 mm quantum
        array[...] = np.transpose(values, np.argsort(order)).astype(array.dtype)
    _load.cache_clear()


# ---- the reference calculation ---------------------------------------------------

def load(inputs, issue):
    return _load(str(Path(inputs).resolve()), issue)


@functools.lru_cache(maxsize=16)
def _load(inputs, issue):
    with xr.open_zarr(Path(inputs) / store_name(issue), chunks=None, consolidated=False) as ds:
        if ds.tp.attrs.get("units") != "kg m**-2":
            raise ValueError("Expected cumulative precipitation in kg m**-2")
        tp = ds.tp.transpose("number", "step", "latitude", "longitude").values.astype("float64")
        lead = np.rint(ds.step.values / DAY).astype(int)
        start = ds.time.values.astype("datetime64[D]")
        if str(start) != issue or lead[0] != 0 or not np.array_equal(np.diff(lead), np.ones(len(lead) - 1)):
            raise ValueError("Store does not hold daily cumulative steps from the stated issue")
        return {"tp": tp, "lead": lead, "lat": ds.latitude.values.astype(float), "lon": ds.longitude.values.astype(float)}


def select_cells(lat, lon, rectangle, boundary):
    if boundary == "inclusive":
        rows = (lat >= rectangle["south"]) & (lat <= rectangle["north"])
        cols = (lon >= rectangle["west"]) & (lon <= rectangle["east"])
    else:
        rows = (lat > rectangle["south"]) & (lat < rectangle["north"])
        cols = (lon > rectangle["west"]) & (lon < rectangle["east"])
    return np.flatnonzero(rows), np.flatnonzero(cols)


def period_total(data, offset, conventions, strict):
    """Total for the 7 days beginning `offset` days after the issue, per member and cell.

    An increment between cumulative steps k-1 and k belongs to the day ending at lead k.
    The period therefore owns the increments with lead k in (offset, offset+7].
    """
    tp, lead = data["tp"], data["lead"]
    shift = -1 if conventions["window_labels"] == "shifted_one_day_early" else 0
    low, high = offset + shift, offset + shift + 7
    if conventions["rainfall_semantics"] == "differenced_cumulative":
        values, ends = np.diff(tp, axis=1), lead[1:]
        if conventions["negative_increments"] == "clipped":
            values = np.maximum(values, 0)
    else:                                                          # pitfall: cumulative values read as daily totals
        values, ends = tp, lead
    chosen = (ends > low) & (ends <= high)
    if strict and chosen.sum() != 7:
        raise ValueError("Period is not fully covered by the forecast")
    if not chosen.any():
        raise ValueError("Period lies outside the forecast")
    return values[:, chosen].sum(axis=1)


def regional_mean(field, lat, weighting):
    weights = np.cos(np.deg2rad(lat)) if weighting == "cos_latitude" else np.ones(len(lat))
    return float((field.mean(axis=-1) * weights).sum() / weights.sum())


def reference(inputs, params, conventions):
    """Results for one instance under one combination of conventions."""
    current, previous = load(inputs, params["issue_current"]), load(inputs, params["issue_previous"])
    if not (np.array_equal(current["lat"], previous["lat"]) and np.array_equal(current["lon"], previous["lon"])):
        raise ValueError("The two issues are on different grids")
    rows, cols = select_cells(current["lat"], current["lon"], params["rectangle"], conventions["boundary"])
    if not len(rows) or not len(cols):
        raise ValueError("Rectangle selects no grid cells")
    lat, lon = current["lat"][rows], current["lon"][cols]
    issue_current, issue_previous = (np.datetime64(params[k], "D") for k in ("issue_current", "issue_previous"))
    accepted_window = conventions["window_labels"] == "end_labelled"
    new, old, change, regional = [], [], [], []
    for start in params["period_start"]:
        offset = int((np.datetime64(start, "D") - issue_current) / DAY)
        aligned = conventions["issue_alignment"] == "same_valid_period"
        previous_offset = int((np.datetime64(start, "D") - issue_previous) / DAY) if aligned else offset
        a = period_total(current, offset, conventions, accepted_window)[:, rows][:, :, cols].mean(axis=0)
        b = period_total(previous, previous_offset, conventions, accepted_window and aligned)[:, rows][:, :, cols].mean(axis=0)
        new.append(a); old.append(b); change.append(a - b)
        regional.append(regional_mean(a - b, lat, conventions["area_weighting"]))
    return {"latitude": lat, "longitude": lon, "current_mean_mm": np.array(new), "previous_mean_mm": np.array(old),
            "change_mm": np.array(change), "regional_change_mm": np.array(regional)}


# ---- instances -------------------------------------------------------------------

RECTANGLES = {
    "service-area": {"south": -5, "north": 5, "west": 34, "east": 42},      # the original case; east edge on a grid centre
    "central": {"south": -3, "north": 3, "west": 36, "east": 40.5},         # every edge on a grid centre
    "north-west": {"south": 0.5, "north": 6, "west": 33, "east": 38},
    "south-east": {"south": -4.5, "north": 0, "west": 37.5, "east": 42},
    "coast": {"south": -4.5, "north": 1.5, "west": 39, "east": 42},
    "full-domain": {"south": -4.5, "north": 6, "west": 33, "east": 42},
    "rift": {"south": -2, "north": 4, "west": 34.5, "east": 37.5},
    "lake-basin": {"south": -1.5, "north": 1.5, "west": 33, "east": 36},
}
PERIODS = {"weeks-1-2": (0, 1), "weeks-2-3": (1, 2), "weeks-3-4": (2, 3), "weeks-4-5": (3, 4), "week-1": (0,), "weeks-1-3": (0, 1, 2)}


def instance(rectangle, periods):
    start = np.datetime64(ISSUES[1], "D")
    return {"id": f"{rectangle}--{periods}", "issue_current": ISSUES[1], "issue_previous": ISSUES[0],
            "rectangle": dict(RECTANGLES[rectangle]), "period_start": [str(start + 7 * week * DAY) for week in PERIODS[periods]]}


def candidate_instances():
    """Every instance the frozen data supports: 8 rectangles by 6 period sets."""
    return [instance(rectangle, periods) for rectangle in RECTANGLES for periods in PERIODS]


def independent(inputs, params, conventions):
    """Implementation B, loaded on demand so that the two files stay separate."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("kenya_reference_independent", HERE / "reference_independent.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.answer(inputs, params, conventions)


def regression_checks(inputs):
    """Agreement with the answer key computed by the earlier repository's own oracle."""
    legacy = json.loads((HERE / "legacy-answer.json").read_text())["answer"]
    ours = reference(inputs, instance("service-area", "weeks-1-2"),
                     {"rainfall_semantics": "differenced_cumulative", "negative_increments": "clipped", "issue_alignment": "same_valid_period",
                      "area_weighting": "cos_latitude", "boundary": "inclusive", "window_labels": "end_labelled"})
    gap = max(float(np.max(np.abs(ours[name] - np.array(legacy[name])))) for name in ours)
    return [{"name": "legacy_answer_key", "passed": gap <= 1e-9, "detail": f"largest difference from the weather-skills-bench oracle is {gap:.3g}"}]


def brief_fields(params):
    box = params["rectangle"]
    def degrees(value, positive, negative):
        return f"{abs(value):g}°{positive if value >= 0 else negative}"
    starts = params["period_start"]
    periods = starts[0] if len(starts) == 1 else ", ".join(starts[:-1]) + " and " + starts[-1]
    return {"issue_previous": params["issue_previous"], "issue_current": params["issue_current"],
            "latitudes": f"{degrees(box['south'], 'N', 'S')} to {degrees(box['north'], 'N', 'S')}",
            "longitudes": f"{degrees(box['west'], 'E', 'W')} to {degrees(box['east'], 'E', 'W')}",
            "periods": periods, "period_word": "period" if len(starts) == 1 else "periods"}


# ---- invariants and claims: rules any valid answer obeys ---------------------------

def _change_is_difference(results, params, inputs=None):
    gap = float(np.max(np.abs(results["change_mm"] - (results["current_mean_mm"] - results["previous_mean_mm"]))))
    return gap <= 2e-3, f"largest |change - (current - previous)| is {gap:.3g} mm"


def _regional_within_cells(results, params, inputs=None):
    low, high = results["change_mm"].min(axis=(1, 2)), results["change_mm"].max(axis=(1, 2))
    ok = bool(np.all((results["regional_change_mm"] >= low - 2e-3) & (results["regional_change_mm"] <= high + 2e-3)))
    return ok, "each regional mean change lies within the range of its cell changes" if ok else "a regional mean change lies outside the range of its cell changes"


def _totals_plausible(results, params, inputs=None):
    low = float(min(results["current_mean_mm"].min(), results["previous_mean_mm"].min()))
    return low >= -0.5, f"smallest ensemble-mean weekly total is {low:.3g} mm"


INVARIANTS = {"change_equals_current_minus_previous": _change_is_difference,
              "regional_change_within_cell_range": _regional_within_cells,
              "weekly_totals_not_negative": _totals_plausible}


def expected_claims(results, params):
    """Claims as they follow from the submission's own numbers: one direction per period."""
    return {"direction": [{"wetter"} if value > 1e-3 else {"drier"} if value < -1e-3 else {"wetter", "drier", "unchanged"}
                          for value in results["regional_change_mm"]]}
