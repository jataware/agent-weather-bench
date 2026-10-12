"""Which functions of a declared library a submission actually calls.

Two views, both lower bounds, both from the frozen submission rather than the agent's chat:

- `static_calls` reads the submitted code and resolves every call whose callee is imported
  from a declared library (through aliases such as `import africas2s as ds`).
- `traced_argv` wraps the declared run command so that, when the controller replays it, a
  `sitecustomize` module counts every call from the submission's code into a declared library,
  function by function, and writes the counts under the output directory. `read_trace`
  collects them. The replay used for this measurement is separate from the one that decides
  the assessment; its outputs are discarded.

An import that is never called, or a call made only in the chat and not in the delivered
command, does not count. That is the point: a library that is installed, imported and then
bypassed by hand-rolled arithmetic measures availability, not use.
"""
import ast
import json
from pathlib import Path

SINK = ".awb-library-calls"
CODE_SUFFIXES = (".py",)

SITECUSTOMIZE = r'''
import atexit, functools, importlib.machinery, json, os, sys
LIBRARIES = [name for name in os.environ.get("AWB_TRACE_LIBRARIES", "").split(",") if name]
SINK = os.environ.get("AWB_TRACE_SINK")
CALLS = {}


def owned(name):
    return any(name == library or name.startswith(library + ".") for library in LIBRARIES)


def counting(qualname, function):
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        try:
            caller = sys._getframe(1).f_globals.get("__name__", "")
            if not owned(caller):
                CALLS[qualname] = CALLS.get(qualname, 0) + 1
        except Exception:
            pass
        return function(*args, **kwargs)
    return wrapper


def wrap_class(cls, prefix):
    for attribute, value in list(vars(cls).items()):
        if attribute.startswith("_"):
            continue
        try:
            if isinstance(value, (classmethod, staticmethod)):
                inner = value.__func__
                if getattr(inner, "__module__", None) != cls.__module__: continue
                setattr(cls, attribute, type(value)(counting(prefix + "." + attribute, inner)))
            elif callable(value) and not isinstance(value, type) and getattr(value, "__module__", None) == cls.__module__:
                setattr(cls, attribute, counting(prefix + "." + attribute, value))
        except Exception:
            pass


def wrap_module(module):
    for attribute, value in list(vars(module).items()):
        if attribute.startswith("_") or not callable(value) or getattr(value, "__module__", None) != module.__name__:
            continue
        try:
            if isinstance(value, type):
                wrap_class(value, module.__name__ + "." + attribute)
            else:
                setattr(module, attribute, counting(module.__name__ + "." + attribute, value))
        except Exception:
            pass


class Loader:
    def __init__(self, inner):
        self.inner = inner

    def create_module(self, spec):
        return self.inner.create_module(spec)

    def exec_module(self, module):
        self.inner.exec_module(module)
        try:
            wrap_module(module)
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self.inner, name)


class Finder:
    def find_spec(self, name, path, target=None):
        if not owned(name):
            return None
        spec = importlib.machinery.PathFinder.find_spec(name, path)
        if spec is None or spec.loader is None or not hasattr(spec.loader, "exec_module"):
            return None
        spec.loader = Loader(spec.loader)
        return spec


def flush():
    if not SINK:
        return
    try:
        os.makedirs(SINK, exist_ok=True)
        with open(os.path.join(SINK, "%d.json" % os.getpid()), "w") as handle:
            json.dump({"pid": os.getpid(), "argv": sys.argv[:4], "calls": CALLS}, handle)
    except Exception:
        pass


def chain():
    """Run the runtime's own sitecustomize, if the image has one further along sys.path, so its setup still applies."""
    own = os.path.dirname(os.path.abspath(__file__))
    for entry in sys.path:
        candidate = os.path.join(entry or os.getcwd(), "sitecustomize.py")
        if os.path.abspath(entry or os.getcwd()) != own and os.path.isfile(candidate):
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("sitecustomize_runtime", candidate)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except Exception:
                pass
            return


if LIBRARIES:
    sys.meta_path.insert(0, Finder())      # before the runtime's own setup, which may import a declared library
    atexit.register(flush)
chain()
'''


def traced_argv(argv, libraries):
    """The declared command wrapped so that its Python processes count calls into `libraries`.

    The wrapper is a shell script: it writes the tracer as `sitecustomize.py` into a fresh directory,
    puts that directory first on PYTHONPATH, points the sink at `{output_dir}/.awb-library-calls`
    and then runs the original command unchanged. A `sitecustomize` the runtime image already
    had, further along PYTHONPATH, is run from the tracer so that its setup is kept. Placeholders stay in the original arguments, so
    every executor substitutes them as usual.
    """
    if not libraries or any("," in name for name in libraries):
        raise ValueError("Declare at least one library name without commas")
    script = ('d="$(mktemp -d)"; cat > "$d/sitecustomize.py" <<\'AWB_TRACER_EOF\'\n' + SITECUSTOMIZE.strip("\n") + "\nAWB_TRACER_EOF\n"
              'export PYTHONPATH="$d${PYTHONPATH:+:$PYTHONPATH}" AWB_TRACE_LIBRARIES="' + ",".join(libraries) + '" '
              'AWB_TRACE_SINK="{output_dir}/' + SINK + '"\nexec "$@"')
    return ["/bin/sh", "-c", script, "awb-trace", *argv]


def read_trace(output):
    """Merge the per-process counts a traced replay wrote: {"processes": n, "calls": {qualname: count}}."""
    folder = Path(output) / SINK
    processes, calls = 0, {}
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            row = json.loads(path.read_text())
        except ValueError:
            continue
        processes += 1
        for name, count in (row.get("calls") or {}).items():
            calls[name] = calls.get(name, 0) + int(count)
    return {"processes": processes, "calls": dict(sorted(calls.items()))}


def _qualified(node, aliases):
    """The dotted name a call's callee resolves to through the file's imports, or None."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name) or node.id not in aliases:
        return None
    return ".".join([aliases[node.id], *reversed(parts)])


def static_calls(root, libraries):
    """Per library, the qualified callees the submitted Python files call, with counts. A lower bound."""
    root = Path(root)
    record = {library: {} for library in libraries}

    def owner(name):
        return next((library for library in libraries if name == library or name.startswith(library + ".")), None)

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in CODE_SUFFIXES or path.stat().st_size > 2_000_000:
            continue
        try:
            tree = ast.parse(path.read_text(errors="replace"))
        except (SyntaxError, ValueError):
            continue
        aliases = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if owner(alias.name):
                        aliases[(alias.asname or alias.name).split(".")[0]] = alias.name if alias.asname else alias.name.split(".")[0]
            elif isinstance(node, ast.ImportFrom) and node.module and owner(node.module):
                for alias in node.names:
                    if alias.name != "*":
                        aliases[alias.asname or alias.name] = node.module + "." + alias.name
        if not aliases:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _qualified(node.func, aliases)
                library = owner(name) if name else None
                if library and name != library:
                    record[library][name] = record[library].get(name, 0) + 1
    return {library: dict(sorted(calls.items())) for library, calls in record.items()}
