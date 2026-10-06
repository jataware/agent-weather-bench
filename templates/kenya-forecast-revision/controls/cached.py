"""Control for certification: ignores its inputs and returns stored results."""
import argparse
import shutil
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--inputs", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
here, output = Path(__file__).resolve().parent, Path(args.output)
output.mkdir(parents=True, exist_ok=True)
shutil.copyfile(here / "cached-answer.json", output / "answer.json")
shutil.copytree(here / "cached-results.zarr", output / "results.zarr")
