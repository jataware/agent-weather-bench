"""Wrapper preserves runtime uncertainty and never follows submitted links."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]


def wrapper():
    path=ROOT/"templates/monthly-cycle-calibration/saved_state.py"
    spec=importlib.util.spec_from_file_location("monthly_saved_state_test",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(tmp_path):
    submission,inputs=tmp_path/"submission",tmp_path/"inputs"
    submission.mkdir();inputs.mkdir()
    (submission/"model.json").write_text("{}")
    (submission/"answer.json").write_text(json.dumps({"model_path":"model.json","predict":{"argv":["python","code.py","{model_path}","{input_dir}","{output_dir}"]}}))
    (inputs/"saved-inference.json").write_text("{}")
    return submission,inputs


@pytest.mark.parametrize("crash,infra",[(True,False),(False,True)])
def test_runtime_failure_remains_unresolved(tmp_path,crash,infra):
    submission,inputs=fixture(tmp_path)
    class Base:
        name="simulated"
        def run(self,submission,inputs,argv,scratch,seconds):
            output=Path(scratch)/"output";output.mkdir(parents=True)
            return {"exit_code":139 if crash else 125,"output":str(output),"answer":None,
                    "crashed_by_signal":crash,"infrastructure_unavailable":infra,"stderr":"simulated only"}
    result=wrapper().SavedStateExecutor(Base()).run(submission,inputs,[],tmp_path/"scratch")
    assert result["crashed_by_signal"]==crash
    assert result["infrastructure_unavailable"]==infra
    decision=json.loads((tmp_path/"scratch/saved-state-decision.json").read_text())
    assert decision["state"]=="unresolved"


def test_saved_submission_link_is_rejected_without_following(tmp_path):
    submission,inputs=fixture(tmp_path)
    secret=tmp_path/"controller-private.txt";secret.write_text("not actor data")
    (submission/"leak").symlink_to(secret)
    class Base:
        name="must-not-run"
        def run(self,*args,**kwargs):
            raise AssertionError("Unsafe actor bundle must not run")
    result=wrapper().SavedStateExecutor(Base()).run(submission,inputs,[],tmp_path/"scratch")
    assert result["exit_code"]==1 and "Symlink" in result["stderr"]
    assert not (tmp_path/"scratch/target-free-submission/leak").exists()
    assert secret.read_text()=="not actor data"
