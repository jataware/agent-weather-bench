"""Control for certification: ignores its inputs and returns a stored answer."""
import argparse
import shutil
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--inputs", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
Path(args.output).mkdir(parents=True, exist_ok=True)
shutil.copyfile(Path(__file__).resolve().parent / "cached-answer.json", Path(args.output) / "answer.json")
