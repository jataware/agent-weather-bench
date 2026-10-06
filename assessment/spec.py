"""A task template: a declarative spec plus one reference module of controller hooks."""
import hashlib
import importlib.util
import itertools
from pathlib import Path

import yaml

from .compare import tolerance

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
PRIVATE = ROOT / "var/private/templates"
MODES = ("outcome", "product", "process")
# The modules that decide an outcome. The runner, the certifier and the command line only orchestrate them.
DECIDING = ("assess.py", "compare.py", "execute.py", "feedback.py", "judge.py", "judge-prompt.md", "outcomes.py", "spec.py", "variant.py", "envelope.md")
HOOKS = ("prepare", "stage_inputs", "perturb_inputs", "candidate_instances", "brief_fields")
MODE_HOOKS = {"product": ("reference",), "process": ("reference",), "outcome": ("expected_coordinates", "score")}


class Template:
    def __init__(self, name):
        self.name, self.folder = name, TEMPLATES / name
        if not (self.folder / "spec.yaml").is_file():
            raise ValueError(f"Unknown template: {name}")
        self.spec = yaml.safe_load((self.folder / "spec.yaml").read_text())
        self.private = PRIVATE / name
        self._validate()
        module = importlib.util.spec_from_file_location(f"template_{name.replace('-', '_')}", self.folder / "reference.py")
        self.hooks = importlib.util.module_from_spec(module)
        module.loader.exec_module(self.hooks)
        missing = [hook for hook in HOOKS + MODE_HOOKS[self.spec["mode"]] if not callable(getattr(self.hooks, hook, None))]
        if missing:
            raise ValueError(f"reference.py lacks hooks: {missing}")
        unknown = set(self.spec.get("invariants", [])) - set(getattr(self.hooks, "INVARIANTS", {}))
        if unknown:
            raise ValueError(f"Spec names invariants the reference module does not define: {sorted(unknown)}")

    def _validate(self):
        spec = self.spec
        if spec.get("schema_version") != 1 or spec.get("template") != self.name or type(spec.get("spec_version")) is not int:
            raise ValueError("Spec needs schema_version 1, its own template name and an integer spec_version")
        if spec.get("mode") not in MODES:
            raise ValueError("Spec mode must be outcome, product or process")
        if not isinstance(spec.get("results"), dict) or not spec["results"]:
            raise ValueError("Spec needs named results")
        for name, row in spec["results"].items():
            if row.get("dtype") == "date":
                if row.get("kind") != "coordinate":
                    raise ValueError(f"Result {name}: only coordinates may be dates")
            else:
                try:                                               # the declared error bound becomes the absolute tolerance
                    row["tolerance"] = {**row["tolerance"], "atol": tolerance(row["tolerance"])}
                except (KeyError, TypeError, ValueError) as error:
                    raise ValueError(f"Result {name}: {error}") from None
            for dim in row.get("dims", []):
                if spec["results"].get(dim, {}).get("kind") != "coordinate":
                    raise ValueError(f"Result {name} uses the dimension {dim}, so {dim} must be a named coordinate result")
        if spec.get("claims_by") and spec["results"].get(spec["claims_by"], {}).get("kind") != "coordinate":
            raise ValueError("claims_by must name a coordinate result")
        for name, filename in spec.get("supplements", {}).items():
            if not (self.folder / filename).is_file():
                raise ValueError(f"Supplement {name} names a missing file: {filename}")
        for dimension, values in spec.get("conventions", {}).items():
            if not values or set(values.values()) - {"accepted", "pitfall"} or "accepted" not in values.values():
                raise ValueError(f"Convention {dimension} needs values labelled accepted or pitfall, with at least one accepted")
        described = set(spec.get("pitfalls", {}))
        named = {value for values in spec.get("conventions", {}).values() for value, label in values.items() if label == "pitfall"}
        if named - described:
            raise ValueError(f"Pitfalls without a description: {sorted(named - described)}")
        if set(spec.get("public_conventions", [])) - set(spec.get("conventions", {})):
            raise ValueError("public_conventions must name declared conventions")
        if (spec["mode"] == "process") != bool(spec.get("process")):
            raise ValueError("A process-mode spec needs a process checklist, and only a process-mode spec may have one")
        for step in spec.get("process", []):
            kinds = [key for key in ("checks", "results", "method_statement", "judge") if key in step]
            if not isinstance(step.get("id"), str) or not step.get("requirement") or not step.get("source") or len(kinds) != 1:
                raise ValueError("Each process step needs an id, a requirement, a source and exactly one kind of evidence")

    def matched(self):
        """The results that have a reference answer. Results marked `free` are valid under any sound method."""
        return {name: row for name, row in self.spec["results"].items() if not row.get("free")}

    def combinations(self):
        conventions = self.spec.get("conventions", {})
        return [dict(zip(conventions, values)) for values in itertools.product(*(list(v) for v in conventions.values()))]

    def pitfalls_in(self, combination):
        return [value for dimension, value in combination.items() if self.spec["conventions"][dimension][value] == "pitfall"]

    def instance(self, identifier):
        for row in self.hooks.candidate_instances():
            if row["id"] == identifier:
                return row
        raise ValueError(f"Unknown instance: {identifier}")

    def development_instances(self):
        listed = yaml.safe_load((self.folder / "instances.yaml").read_text())["development"]
        return [self.instance(identifier) for identifier in listed]

    def brief(self, params, level=1, supplied=()):
        """The brief for one instance. `supplied` names optional supplements handed to the agent, such as a conventions sheet."""
        text = (self.folder / "brief.md").read_text().format(**self.hooks.brief_fields(params))
        if level == 2:
            if "level2" not in self.spec:
                raise ValueError("This template has no Level 2")
            text += (self.folder / "brief-level2.md").read_text().format(**self.spec["level2"]["feedback"])
        for name in supplied:
            if name not in self.spec.get("supplements", {}):
                raise ValueError(f"This template has no supplement named {name}")
            text += f"\n`/task/{self.spec['supplements'][name]}` is supplied with this task. Follow it.\n"
        return text

    def fingerprint(self):
        """Identity of everything that decides an outcome: the template's own files and the deciding modules."""
        files = sorted(p for p in self.folder.iterdir() if p.suffix in (".yaml", ".py", ".md", ".json", ".txt") and p.name != "certification.json")
        files += [ROOT / "assessment" / name for name in DECIDING]
        digest = hashlib.sha256()
        for path in files:
            digest.update(str(path.relative_to(ROOT)).encode() + b"\0" + hashlib.sha256(path.read_bytes()).digest())
        return digest.hexdigest()


def templates():
    return sorted(path.parent.name for path in TEMPLATES.glob("*/spec.yaml"))
