"""System definitions: trusted controller adapters, isolated scientific tools."""
import re
import shutil
from pathlib import Path

from .storage import ROOT, identifier, read, write, inventory

DEFAULT_IMAGE = "sha256:14ded77c764dccdcaeef07f91c549709b4ff3549d0c30f5dc780e4376347917a"


def resolve_system(value):
    path = Path(value)
    if not path.is_file():
        path = ROOT / "systems" / identifier(value) / "system.yaml"
    if not path.is_file():
        raise ValueError(f"Unknown system: {value}")
    return path.resolve()


def validate(path):
    value = read(path)
    if value.get("schema_version") != 1:
        raise ValueError("Expected system schema_version 1")
    identifier(value["id"])
    if value.get("kind") not in ("agent", "harness_fixture"):
        raise ValueError("System kind must be agent or harness_fixture")
    runtime = value["runtime"]
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", runtime.get("image", "")):
        raise ValueError("Pin the runtime image by its full local Docker content ID")
    if not isinstance(runtime.get("memory"), str) or not re.fullmatch(r"[1-9][0-9]*[mg]", runtime["memory"]):
        raise ValueError("Declare a positive runtime memory limit, e.g. 4g")
    if not isinstance(runtime.get("cpus"), (float, int)) or isinstance(runtime["cpus"], bool) or not 0 < runtime["cpus"] <= 64:
        raise ValueError("Declare positive runtime CPU limits")
    budget = value["budget"]
    for key in ("max_seconds", "max_tool_calls", "command_seconds"):
        if type(budget.get(key)) is not int or budget[key] <= 0:
            raise ValueError(f"Declare positive {key}")
    driver = value["driver"]
    if driver["kind"] == "command":
        if not isinstance(driver.get("argv"), list) or not driver["argv"] or not all(isinstance(x, str) and x for x in driver["argv"]):
            raise ValueError("Command driver needs an argv list")
        if not isinstance(driver.get("env", []), list) or not all(re.fullmatch(r"[A-Z][A-Z0-9_]*", x) for x in driver.get("env", [])):
            raise ValueError("Driver env declares names, never secret values")
    elif driver["kind"] == "anthropic":
        for key in ("model", "api_key_env", "max_usd", "input_usd_per_million", "output_usd_per_million", "max_total_tokens", "max_output_tokens", "max_turns"):
            if driver.get(key) is None:
                raise ValueError(f"Configure driver {key}")
    else:
        raise ValueError("Supported controller drivers: command or anthropic")
    return value


def snapshot(path, destination):
    value = validate(path)
    destination.mkdir(parents=True, exist_ok=False)
    for name in value.get("substrate", {}).get("paths", []):
        if not isinstance(name,str): raise ValueError("Substrate paths must be strings inside the system directory")
        source = Path(path).parent / name
        if not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts or not source.exists() or source.is_symlink() or not source.resolve().is_relative_to(Path(path).parent.resolve()):
            raise ValueError("Substrate paths must name existing files/directories inside the system directory")
        if source.is_dir():
            inventory(source)
            shutil.copytree(source, destination / name)
        else:
            (destination / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination / name)
    return value, inventory(destination)


def init(name, image=DEFAULT_IMAGE):
    path = ROOT / "systems" / identifier(name)
    path.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(ROOT / "systems/example/adapter.py", path / "adapter.py")
    value = {"schema_version":1, "id":name, "kind":"agent", "description":"Replace adapter.py with your trusted controller integration.",
             "driver":{"kind":"command", "argv":["{python}", "{driver}/adapter.py"], "env":[]},
             "runtime":{"image":image, "memory":"4g", "cpus":2},
             "budget":{"max_seconds":600, "max_tool_calls":60, "command_seconds":120},
             "substrate":{"paths":["adapter.py"], "instructions":""}}
    write(path / "system.yaml", value)
    return {"system":str(path / "system.yaml")}
