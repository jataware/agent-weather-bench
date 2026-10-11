"""Hash-checked restoration of a template's frozen local development snapshot."""
import hashlib
import json
import shutil
from pathlib import Path


def restore(folder, private, source_dir):
    manifest = json.loads((Path(folder) / "sources.json").read_text())
    if source_dir is None:
        raise ValueError("Pass --source with the original frozen task directory named in sources.json")
    source, private = Path(source_dir), Path(private)
    for row in manifest["files"]:
        path = source / row["file"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError(f"Frozen source missing or changed: {path}")
    private.mkdir(parents=True, exist_ok=True)
    for row in manifest["files"]:
        path, target = source / row["file"], private / row["file"]
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != row["sha256"]:
                raise ValueError(f"Refusing to replace frozen data: {target}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    return {"restored": len(manifest["files"]), "source_weather_is_synthetic": False, "private": str(private)}
