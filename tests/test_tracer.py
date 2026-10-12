"""The call tracer: what a frozen submission calls in a declared library, statically and in a traced replay."""
import json
import os
import sys
import textwrap
from types import SimpleNamespace

from assessment.execute import Local
from assessment.substrate import library_calls, substrate_record
from assessment.tracer import read_trace, static_calls, traced_argv

FAKELIB = {
    "fakelib/__init__.py": textwrap.dedent('''
        from fakelib.sub import helper

        def internal():
            return 1

        def f():
            return internal() + helper()

        class C:
            def m(self):
                return 2

            @classmethod
            def make(cls):
                return cls()

            @staticmethod
            def unit():
                return 3
    '''),
    "fakelib/sub.py": "def helper():\n    return 4\n",
}

SOLVE = textwrap.dedent('''
    import json, os, sys
    import fakelib as fl
    from fakelib.sub import helper
    fl.f(); fl.f()
    fl.C().m()
    fl.C.make().unit()
    helper()
    out = sys.argv[sys.argv.index("--output") + 1]
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "answer.json"), "w") as handle:
        json.dump({"run": {"argv": sys.argv}}, handle)
''')

ARGV = ["python", "solve.py", "--inputs", "{input_dir}", "--output", "{output_dir}"]


def submission(tmp_path):
    folder = tmp_path / "submission"
    for name, text in FAKELIB.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(text)
    (folder / "solve.py").write_text(SOLVE)
    (folder / "answer.json").write_text(json.dumps({"run": {"argv": ARGV}}))
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "instance.json").write_text("{}")
    return folder, inputs


def test_static_calls_resolve_aliases_and_ignore_other_libraries(tmp_path):
    folder, _ = submission(tmp_path)
    (folder / "other.py").write_text("import africas2s as ds\nfrom acmaddl import fetch\nds.optimize(1)\nds.cv.loyo(2)\nfetch('x')\nprint(fetch)\n")
    calls = static_calls(folder, ["fakelib", "africas2s", "acmaddl"])
    # the submission vendors fakelib, so its own `helper()` call inside fakelib/__init__.py counts too: a lower bound, not a judgement
    assert calls["fakelib"] == {"fakelib.C": 1, "fakelib.C.make": 1, "fakelib.f": 2, "fakelib.sub.helper": 2}
    assert calls["africas2s"] == {"africas2s.cv.loyo": 1, "africas2s.optimize": 1}
    assert calls["acmaddl"] == {"acmaddl.fetch": 1}        # the bare reference `print(fetch)` is not a call


def test_traced_replay_counts_calls_from_the_submission_only(tmp_path):
    folder, inputs = submission(tmp_path)
    argv = [sys.executable, *ARGV[1:]]
    record = Local().run(folder, inputs, traced_argv(argv, ["fakelib"]), tmp_path / "scratch")
    assert record["exit_code"] == 0, record["stderr"]
    assert record["answer"]["run"]["argv"] == ["solve.py", "--inputs", str(tmp_path / "scratch/stage/_controller_inputs"), "--output", str(tmp_path / "scratch/output")]
    trace = read_trace(record["output"])
    assert trace["processes"] == 1
    assert trace["calls"] == {"fakelib.C.m": 1, "fakelib.C.make": 1, "fakelib.C.unit": 1, "fakelib.f": 2, "fakelib.sub.helper": 1}
    # `internal` and the helper call inside `f` are the library calling itself: not counted.


def test_library_calls_record_and_substrate_record_mark_substantive_use(tmp_path):
    folder, _ = submission(tmp_path)
    template = SimpleNamespace(private=None, hooks=SimpleNamespace(
        stage_inputs=lambda private, params, destination: (destination.mkdir(parents=True), (destination / "instance.json").write_text("{}"))))
    record = library_calls(template, {}, folder, Local(), tmp_path / "work", ["fakelib", "africas2s"])
    assert record["replay"]["state"] == "run" and record["replay"]["exit_code"] == 0 and record["replay"]["processes"] == 1
    assert record["calls"]["fakelib"]["fakelib.f"] == 2 and record["calls"]["africas2s"] == {}
    assert record["static"]["fakelib"]["fakelib.f"] == 2

    run = tmp_path / "run"
    (run / "logs").mkdir(parents=True)
    (run / "logs/events.jsonl").write_text(json.dumps({"type": "tool_result", "id": "x", "exit_code": 0, "stdout": "", "stderr": "", "seconds": .1,
                                                      "command": "python -c 'import africas2s; import fakelib'"}) + "\n")
    (run / "frozen").mkdir()
    (run / "controller").mkdir()
    (run / "controller/library-calls.json").write_text(json.dumps(record))
    config = {"substrate": {"libraries": ["fakelib", "africas2s"]}}
    use = substrate_record(run, config)
    assert use["libraries"]["fakelib"]["used"] and use["libraries"]["fakelib"]["substantive"]
    assert use["libraries"]["africas2s"]["used"] and not use["libraries"]["africas2s"]["substantive"]   # imported, never called
    assert use["library_calls"]["replay"]["processes"] == 1


def test_a_submission_without_a_run_command_is_recorded_as_not_run(tmp_path):
    folder, _ = submission(tmp_path)
    (folder / "answer.json").write_text("{}")
    template = SimpleNamespace(private=None, hooks=SimpleNamespace(stage_inputs=lambda *a: None))
    record = library_calls(template, {}, folder, Local(), tmp_path / "work", ["fakelib"])
    assert record["replay"]["state"] == "not_run" and record["calls"] == {"fakelib": {}}
    assert record["static"]["fakelib"]["fakelib.f"] == 2


def test_the_tracer_runs_the_runtime_sitecustomize_it_shadows(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    for name, text in FAKELIB.items():                       # importable at startup, as site-packages are in the images
        (runtime / name).parent.mkdir(parents=True, exist_ok=True)
        (runtime / name).write_text(text)
    # the runtime's own setup imports the traced library first, as the benchmark images import xarray; the tracer must already be in place
    (runtime / "sitecustomize.py").write_text("import os, fakelib\nopen(os.environ['AWB_TEST_CHAIN'], 'w').write('ran')\n")
    monkeypatch.setenv("PYTHONPATH", str(runtime))
    monkeypatch.setenv("AWB_TEST_CHAIN", str(tmp_path / "chained"))
    folder, inputs = submission(tmp_path)
    record = Local().run(folder, inputs, traced_argv([sys.executable, *ARGV[1:]], ["fakelib"]), tmp_path / "scratch")
    assert record["exit_code"] == 0, record["stderr"]
    assert (tmp_path / "chained").read_text() == "ran"
    assert read_trace(record["output"])["calls"]["fakelib.f"] == 2
