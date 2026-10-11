"""Offline, controller-owned stress controls; never rewrites a benchmark contract.

Run: .venv/bin/python experiments/grader_stress.py
All generated submissions live under var/review, outside original agent attempts.
"""
import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import warnings
from pathlib import Path

import numpy as np
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASKS = {
    "kenya-forecast-revision": ("service-area--weeks-1-2", "pitfall_summed_cumulative"),
    "seasonal-rainfall-calibration": ("train-1993-2004--new-2005-2006--all-cells", "skipped_cross_validation"),
    "weeks34-rainfall": ("final-2018-2021--all-cells", "uses_later_forecasts"),
    "seasonal-cca-reproduction": ("outer-2005-2019--all-cells", "full_training"),
    "rainfall-downscaling": ("train-to-2008--forecast-2009-2012", "full_training"),
}


def rewrite(folder, layout, zarr_format, consolidated, permute):
    """Change representation, preserving the scientific object (unless mislabelled)."""
    folder = Path(folder)
    store = folder / "results.zarr"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with xr.open_zarr(store, chunks=None) as source:
            dataset = source.load()
    answer = json.loads((folder / "answer.json").read_text())
    # Exercise both legal scalar homes: answer.json and a rank-zero store array.
    for name, row in layout.items():
        if row.get("kind") != "coordinate" and not row.get("dims"):
            if name in dataset:
                answer.setdefault("results", {})[name] = float(dataset[name])
                dataset = dataset.drop_vars(name)
            elif name in answer.get("results", {}):
                dataset[name] = xr.DataArray(answer["results"].pop(name))
    if permute:
        indices = {dim: np.arange(size - 1, -1, -1) for dim, size in dataset.sizes.items()}
        dataset = dataset.isel(indices)
        for name in dataset.data_vars:
            dataset[name] = dataset[name].transpose(*reversed(dataset[name].dims))
    # Dates may be YYYY-MM-DD text or datetime labels.
    for name, row in layout.items():
        if row.get("dtype") == "date" and dataset[name].dtype.kind == "M":
            dataset = dataset.assign_coords({name: dataset[name].dt.strftime("%Y-%m-%d")})
    for variable in dataset.variables.values():
        variable.encoding = {}
    encoding = {name: {"chunks": tuple(max(1, min(3, size)) for size in variable.shape)}
                for name, variable in dataset.variables.items() if variable.ndim}
    shutil.rmtree(store)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dataset.to_zarr(store, mode="w", zarr_format=zarr_format, consolidated=consolidated, encoding=encoding)
    (folder / "answer.json").write_text(json.dumps(answer, allow_nan=False) + "\n")


def install_wrapper(folder, layout):
    """Make the same legal representation transformation on every scientific rerun."""
    shutil.copyfile(__file__, folder / "stress_transform.py")
    (folder / "stress-layout.json").write_text(json.dumps(layout))
    (folder / "stress_solve.py").write_text('''import argparse,json,subprocess,sys
from pathlib import Path
from stress_transform import rewrite
p=argparse.ArgumentParser();p.add_argument('--inputs');p.add_argument('--output');a=p.parse_args()
subprocess.run([sys.executable,'solve.py','--inputs',a.inputs,'--output',a.output],check=True)
rewrite(a.output,json.loads(Path('stress-layout.json').read_text()),2,True,True)
path=Path(a.output)/'answer.json';answer=json.loads(path.read_text());answer['run']['argv'][1]='stress_solve.py';path.write_text(json.dumps(answer)+'\\n')
''')
    answer_path = folder / "answer.json"
    answer = json.loads(answer_path.read_text())
    answer["run"]["argv"][1] = "stress_solve.py"
    answer_path.write_text(json.dumps(answer) + "\n")


def controls(template):
    spec = importlib.util.spec_from_file_location("stress_controls_" + template.name.replace("-", "_"), template.folder / "controls/build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load(template, folder):
    from assessment.compare import read_results
    raw, problems = read_results(template.spec["results"], folder, json.loads((folder / "answer.json").read_text()))
    if problems:
        raise AssertionError(problems)
    return raw


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(destination, output):
    from assessment.assess import assess
    from assessment.compare import align, compare
    from assessment.execute import Local
    from assessment.spec import Template
    from assessment.variant import consistent, table
    destination.mkdir(parents=True, exist_ok=False)
    report = {"kind": "controller_owned_grader_stress", "model_calls": 0, "notes": [
        "Storage transformations exercise the declared representation equivalence, not a new scientific solution.",
        "Scientific fault controls are pre-existing planted defects, reassessed independently of old agent assessments.",
        "No prose judge is called: required prose checks remain unresolved; computed checks decide these diagnostics."], "tasks": []}
    for name, (instance, defect) in TASKS.items():
        template = Template(name)
        fingerprint = template.fingerprint()
        params = template.instance(instance)
        folder = destination / name
        folder.mkdir()
        inputs = folder / "inputs"
        template.hooks.stage_inputs(template.private, params, inputs)
        correct = controls(template).build("correct", inputs, params, folder / "correct")
        baseline = load(template, correct)
        references = table(template, inputs, params, baseline) if template.uses_reference else None
        accepted = [i for i, (combination, _, _) in enumerate(references or []) if not template.pitfalls_in(combination)]
        task = {"template": name, "instance": instance, "spec_version": template.spec["spec_version"],
                "fingerprint": fingerprint, "representations": [], "assessment_files": []}
        for zarr_format in (2, 3):
            for consolidated in (False, True):
                for permute in (False, True):
                    label = f"zarr{zarr_format}-{'consolidated' if consolidated else 'unconsolidated'}-{'reversed' if permute else 'original'}"
                    copy = folder / label
                    shutil.copytree(correct, copy)
                    rewrite(copy, template.spec["results"], zarr_format, consolidated, permute)
                    raw = load(template, copy)
                    equivalent, detail = compare(template.spec["results"], raw, baseline)
                    if references is not None:
                        # Production assessment frames results first when the reference
                        # deliberately omits coordinate arrays (seasonal calibration).
                        framed = align(template.spec["results"], raw, template.hooks.expected_coordinates(inputs, params)) if callable(getattr(template.hooks, "expected_coordinates", None)) else raw
                        hits, _ = consistent(template, framed, references)
                        accepted_match = bool(set(hits) & set(accepted))
                    else:
                        hits, accepted_match = [], True
                        align(template.spec["results"], raw, template.hooks.expected_coordinates(inputs, params))
                    task["representations"].append({"case": label, "equivalent": bool(equivalent), "accepted_match": accepted_match,
                                                    "largest_numeric_difference": max((v["largest_difference"] or 0 for v in detail.values()), default=0)})
                    assert equivalent and accepted_match, (name, label, detail)
        representative = folder / "zarr2-consolidated-reversed"
        install_wrapper(representative, template.spec["results"])
        result = assess(template, params, representative, Local(), folder / "full-representation-assessment")
        path = folder / "representation-assessment.json"
        path.write_text(json.dumps(result, indent=2) + "\n")
        task["assessment_files"].append({"path": str(path.relative_to(ROOT)), "sha256": sha(path)})
        task["computed_correct_outcome"] = result["computed_outcome"]
        assert result["computed_outcome"] == "pass", (name, result["checks"])
        # Swapping two labels without swapping their data is scientific mislabelling.
        corrupted = {key: value.copy() for key, value in baseline.items()}
        name_of_field = next(key for key, row in template.spec["results"].items() if row.get("dims") and not row.get("free"))
        dimension = template.spec["results"][name_of_field]["dims"][0]
        corrupted[dimension][[0, 1]] = corrupted[dimension][[1, 0]]
        agrees, _ = compare(template.spec["results"], corrupted, baseline)
        assert not agrees, (name, "mislabelling accepted")
        task["mislabelled_arrays_rejected_by_comparison"] = True
        faulty = controls(template).build(defect, inputs, params, folder / "faulty")
        bad = assess(template, params, faulty, Local(), folder / "full-scientific-assessment")
        path = folder / "scientific-assessment.json"
        path.write_text(json.dumps(bad, indent=2) + "\n")
        task["assessment_files"].append({"path": str(path.relative_to(ROOT)), "sha256": sha(path)})
        task["scientific_fault"] = {"control": defect, "computed_outcome": bad["computed_outcome"],
                                    "failed_checks": [key for key, row in bad["checks"].items() if row["state"] == "fail"]}
        assert bad["computed_outcome"] == "fail", (name, bad["checks"])
        assert template.fingerprint() == fingerprint
        task["contract_unchanged"] = True
        report["tasks"].append(task)
        print(name, "8 representations + replay/perturbations passed;", defect, "rejected", flush=True)
        output.write_text(json.dumps(report, indent=2) + "\n")
    report["completed"] = True
    report["summary"] = {"templates": len(report["tasks"]), "legal_representations": sum(len(t["representations"]) for t in report["tasks"]),
                         "complete_correct_assessments": len(report["tasks"]), "scientific_fault_assessments": len(report["tasks"])}
    output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, default=ROOT / "var/review/grader-stress-2026-10-08-v3")
    parser.add_argument("--output", type=Path, default=ROOT / "experiments/grader-stress-2026-10-08.json")
    args = parser.parse_args()
    run(args.destination, args.output)
