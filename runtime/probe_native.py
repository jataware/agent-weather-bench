"""Isolate the pilot's import-order abort in disposable Linux containers.

Host code uses only the standard library. Original broken images are expected
to fail; this diagnostic records failures rather than calling them model errors.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess

CASES = {
    "cfgrib_then_pyproj": "import cfgrib; import pyproj",
    "pyproj_then_cfgrib": "import pyproj; import cfgrib",
    "backend_discovery": "import xarray; xarray.backends.list_engines()",
}


def probe(item):
    image, name = item
    result = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--read-only",
         "--memory", "768m", "--cpus", "1", "--cap-drop", "ALL",
         "--entrypoint", "sh", image, "-c",
         'ulimit -c 0; exec python -c "$1"', "probe",
         CASES[name] + '; print("imports completed", flush=True)'],
        capture_output=True, text=True, timeout=60)
    return {"image": image, "case": name, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr,
            "passed": result.returncode == 0 and "imports completed" in result.stdout}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(probe, [(image, case) for image in args.image for case in CASES]))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, indent=2) + "\n")
    print(json.dumps([{k: v for k, v in row.items() if k not in ("stdout", "stderr")} for row in rows], indent=2))
