"""Controller reruns get the system's per-command budget, not the executors' silent 120 seconds."""
from assessment.runner import ReplayBudget


class Recorder:
    name = "fake"

    def __init__(self):
        self.calls = []

    def run(self, submission, inputs, argv, scratch, seconds=120):
        self.calls.append(seconds)
        return {"exit_code": 0, "executor": self.name}


def test_reruns_default_to_the_command_budget_and_an_explicit_value_still_wins():
    inner = Recorder()
    executor = ReplayBudget(inner, 1800)
    executor.run("s", "i", ["python", "run.py"], "scratch")
    executor.run("s", "i", ["python", "run.py"], "scratch", seconds=30)
    assert inner.calls == [1800, 30]
    assert executor.name == "fake" and executor.seconds == 1800
