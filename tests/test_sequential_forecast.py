"""Sequential release/protocol tests; no Docker, model calls or native file I/O."""
from copy import deepcopy
import json
import os
from pathlib import Path
import select
import subprocess
import threading

import pytest

from assessment.sequential import build_command, messages, validate_episode, validate_prediction

IMAGE = "sha256:" + "a" * 64


def record(case_id, issue, start, release, raw, observed):
    return {"case_id": case_id, "issue_time": issue, "target_start": start,
            "release_time": release, "raw_mm": raw, "observed_mm": observed}


@pytest.fixture
def episode():
    # Labels release at issue+14 target start +14 target duration +7 latency.
    return {
        "locations": [{"id": 10, "latitude": 33., "longitude": 246.},
                      {"id": 20, "latitude": 34.5, "longitude": 247.5}],
        "training": [record("training", "2019-12-01", "2019-12-15", "2020-01-05",
                            [1., 2.], [11., 12.])],
        "pending": [record("pending", "2019-12-08", "2019-12-22", "2020-01-12",
                           [3., 4.], [21., 22.])],
        "cases": [record("first", "2020-01-05", "2020-01-19", "2020-02-09",
                         [5., 6.], [31., 32.]),
                  record("second", "2020-01-12", "2020-01-26", "2020-02-16",
                         [7., 8.], [41., 42.]),
                  record("third", "2020-02-09", "2020-02-23", "2020-03-15",
                         [9., 10.], [51., 52.])],
    }


def test_labels_release_at_cutoff_once_and_future_targets_stay_private(episode):
    validate_episode(episode)
    stream = list(messages(episode))
    initial, first, second, third = stream
    assert initial["type"] == "initialize"
    assert initial["locations"] == episode["locations"]
    assert initial["training"] == episode["training"]
    assert "pending" not in initial and "cases" not in initial
    assert first["released_observations"] == []
    # Release at the issue itself is usable; no extra one-day holdback.
    assert second["released_observations"] == episode["pending"]
    assert third["released_observations"] == [episode["cases"][0]]
    for msg, source in zip(stream[1:], episode["cases"]):
        assert msg["type"] == "forecast"
        assert msg["case_id"] == source["case_id"]
        assert msg["raw_mm"] == source["raw_mm"]
        assert "observed_mm" not in msg
        for observation in msg["released_observations"]:
            assert observation["release_time"] <= msg["issue_time"]
            assert observation["issue_time"] < msg["issue_time"]
    observed_ids = [r["case_id"] for msg in stream[1:] for r in msg["released_observations"]]
    assert observed_ids == ["pending", "first"]


def test_unreleased_truth_cannot_change_earlier_agent_messages(episode):
    changed = deepcopy(episode)
    for row in changed["cases"]:
        row["observed_mm"] = [901., 902.]
    # Before first case's release, all emitted input is identical despite new truth.
    assert list(messages(changed))[:3] == list(messages(episode))[:3]
    # At release, the observations become visible and change the message.
    assert list(messages(changed))[3] != list(messages(episode))[3]


def test_future_covariates_are_not_sent_before_their_issue(episode):
    changed = deepcopy(episode)
    changed["cases"][2]["raw_mm"] = [999., 998.]
    assert list(messages(changed))[:3] == list(messages(episode))[:3]
    assert list(messages(changed))[3]["raw_mm"] == [999., 998.]


def test_episode_stream_is_deterministic_and_does_not_modify_controller_data(episode):
    before = deepcopy(episode)
    assert list(messages(episode)) == list(messages(episode))
    assert episode == before


def test_program_mutation_of_messages_cannot_change_controller_truth(episode):
    before = deepcopy(episode)
    stream = messages(episode)
    initialized = next(stream)
    initialized["training"][0]["observed_mm"][0] = 999.
    initialized["locations"][0]["latitude"] = -90.
    first = next(stream)
    first["raw_mm"][0] = 999.
    next(stream)
    third = next(stream)
    assert third["released_observations"][0]["raw_mm"] == [5., 6.]
    assert episode == before


@pytest.mark.parametrize("damage", ["reverse_cases", "future_initial_label", "bad_date",
                                    "raw_shape", "target_shape", "nonfinite_raw",
                                    "nonfinite_target", "duplicate_case", "early_declared_release",
                                    "wrong_target_lead"])
def test_invalid_episode_rejected_before_program_launch(episode, damage):
    if damage == "reverse_cases":
        episode["cases"].reverse()
    elif damage == "future_initial_label":
        episode["training"][0]["release_time"] = "2020-01-06"
    elif damage == "bad_date":
        episode["cases"][0]["issue_time"] = "2020-99-01"
    elif damage == "raw_shape":
        episode["cases"][0]["raw_mm"] = [1.]
    elif damage == "target_shape":
        episode["cases"][0]["observed_mm"] = [1.]
    elif damage == "nonfinite_raw":
        episode["cases"][0]["raw_mm"][0] = float("nan")
    elif damage == "nonfinite_target":
        episode["cases"][0]["observed_mm"][0] = float("inf")
    elif damage == "duplicate_case":
        episode["cases"][1]["case_id"] = "first"
    elif damage == "early_declared_release":
        episode["cases"][0]["release_time"] = "2020-02-08"
    elif damage == "wrong_target_lead":
        episode["cases"][0]["target_start"] = "2020-01-18"
    with pytest.raises(ValueError):
        validate_episode(episode)


@pytest.mark.parametrize("prediction", [[-1., 2.], [float("nan"), 2.], [float("inf"), 2.],
                                       [1.], [1., 2., 3.], [[1., 2.]], [True, 2.], ["1", 2.]])
def test_malformed_or_nonphysical_forecast_rejected(episode, prediction):
    msg = list(messages(episode))[1]
    with pytest.raises(ValueError):
        validate_prediction({"case_id": "first", "prediction_mm": prediction}, msg, 2)


def test_response_can_only_forecast_current_issue(episode):
    first, second = list(messages(episode))[1:3]
    assert validate_prediction({"case_id": "first", "prediction_mm": [0, 2.]}, first, 2) == [0., 2.]
    # An attempted correction to an already issued forecast is rejected.
    with pytest.raises(ValueError):
        validate_prediction({"case_id": "first", "prediction_mm": [99., 99.]}, second, 2)
    # Bulk trajectories/alternate cases cannot smuggle a retrospective replacement.
    with pytest.raises(ValueError):
        validate_prediction({"case_id": "second", "prediction_mm": [1., 2.],
                             "replace": {"first": [99., 99.]}}, second, 2)


def test_validated_forecast_is_detached_from_mutable_response(episode):
    msg = list(messages(episode))[1]
    response = {"case_id": "first", "prediction_mm": [1., 2.]}
    committed = validate_prediction(response, msg, 2)
    response["prediction_mm"][0] = 999.
    assert committed == [1., 2.]


def test_streaming_program_command_mounts_only_submission_without_network(tmp_path):
    submission = tmp_path / "submission"
    submission.mkdir()
    (submission / "forecast.py").write_text("# Fixture; never executed\n")
    command = build_command(submission, ["python", "forecast.py"], IMAGE, "test-stream")
    assert all(isinstance(value, str) for value in command)
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    mounts = [command[index + 1] for index, value in enumerate(command) if value == "--mount"]
    assert len(mounts) == 1
    assert str(submission.resolve()) in mounts[0]
    assert "readonly" in mounts[0]
    assert "--tmpfs" in command
    assert not any("docker.sock" in value for value in command)
    # The private episode is carried by controller stdin, never a bind mount.
    assert not any("provider" in value or "private-target" in value for value in mounts)


def test_submission_symlink_cannot_mount_controller_directory(tmp_path):
    controller = tmp_path / "private-controller"
    controller.mkdir()
    (controller / "hidden-targets.json").write_text('{"private": true}')
    alias = tmp_path / "submission"
    alias.symlink_to(controller, target_is_directory=True)
    with pytest.raises(ValueError):
        build_command(alias, ["python", "forecast.py"], IMAGE, "bad-link")


def test_inner_symlink_cannot_include_private_controller_file(tmp_path):
    submission = tmp_path / "submission"
    submission.mkdir()
    hidden = tmp_path / "hidden-targets.json"
    hidden.write_text('{"private": true}')
    (submission / "training.json").symlink_to(hidden)
    with pytest.raises(ValueError):
        build_command(submission, ["python", "forecast.py"], IMAGE, "bad-inner-link")


class FakeDockerProcess:
    """Trusted stdlib pipe peer, not a host-executed submitted program.

    Threads carry only JSON bytes. There are no scientific imports/file reads.
    The evaluator's real nonblocking stdin/stdout protocol remains exercised.
    """
    def __init__(self, command, respond, **kwargs):
        self.command = command
        incoming, incoming_writer = os.pipe()
        outgoing_reader, outgoing = os.pipe()
        self.stdin = os.fdopen(incoming_writer, "wb", buffering=0)
        self.stdout = os.fdopen(outgoing_reader, "rb", buffering=0)
        self.returncode = None
        self.received = []
        self._stop = threading.Event()

        def peer():
            buffer = bytearray()
            try:
                while not self._stop.is_set():
                    ready, _, _ = select.select([incoming], [], [], .01)
                    if not ready:
                        continue
                    chunk = os.read(incoming, 65536)
                    if not chunk:
                        break
                    buffer.extend(chunk)
                    while b"\n" in buffer:
                        line, _, remaining = buffer.partition(b"\n")
                        buffer[:] = remaining
                        payload = json.loads(line)
                        self.received.append(payload)
                        response = respond(payload)
                        if response is not None:
                            if not isinstance(response, bytes):
                                response = (json.dumps(response) + "\n").encode()
                            os.write(outgoing, response)
            finally:
                os.close(incoming)
                os.close(outgoing)
                self.returncode = -9 if self._stop.is_set() else 0

        self._thread = threading.Thread(target=peer, daemon=True)
        self._thread.start()

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self._thread.join(timeout)
        if self._thread.is_alive():
            raise subprocess.TimeoutExpired("trusted-fake-docker", timeout)
        return self.returncode

    def kill(self):
        self._stop.set()


@pytest.fixture
def fake_transport(monkeypatch, tmp_path):
    from assessment import sequential
    submission = tmp_path / "submission"
    submission.mkdir()
    (submission / "forecast.py").write_text("# Not executed by tests\n")
    processes = []
    cleanup = []

    def run(respond, episode, **kwargs):
        def popen(command, **options):
            assert command[0:2] == ["docker", "run"]
            process = FakeDockerProcess(command, respond, **options)
            processes.append(process)
            return process

        def remove(command, **options):
            assert command[0:3] == ["docker", "rm", "-f"]
            cleanup.append(command)
            return subprocess.CompletedProcess(command, 0)

        monkeypatch.setattr(sequential.subprocess, "Popen", popen)
        monkeypatch.setattr(sequential.subprocess, "run", remove)
        result = sequential.evaluate(submission, ["python", "forecast.py"], episode, IMAGE,
                                     seconds=2, step_seconds=.2, **kwargs)
        return result, processes[-1]

    return run, processes, cleanup


def respond_raw(message):
    if message["type"] == "forecast":
        return {"case_id": message["case_id"], "prediction_mm": message["raw_mm"]}


def test_full_stdio_replay_commits_identical_forecasts_and_release_trace(fake_transport, episode):
    run, processes, cleanup = fake_transport
    first, peer = run(respond_raw, episode)
    second, _ = run(respond_raw, episode)
    assert first["state"] == second["state"] == "pass"
    assert first["predictions"] == second["predictions"] == [[5., 6.], [7., 8.], [9., 10.]]
    assert first["events"] == second["events"]
    assert peer.received == list(messages(episode))
    assert [event["released_cases"] for event in first["events"][1:]] == [[], ["pending"], ["first"]]
    assert first["private_truth_mounted"] is False
    assert len(processes) == len(cleanup) == 2


def test_late_attempt_to_replace_prior_issue_fails_without_mutating_commit(fake_transport, episode):
    run, _, _ = fake_transport

    def wrong_case(message):
        if message["type"] == "forecast":
            return {"case_id": "first", "prediction_mm": [5., 6.]}

    result, _ = run(wrong_case, episode)
    assert result["state"] == "fail"
    assert result["predictions"] == [[5., 6.]]
    assert len(result["events"]) == 2  # initialize and first committed issue only
    assert "current case_id" in result["reason"]


@pytest.mark.parametrize("failure", ["missing", "invalid_json", "extra_forecast", "ready_banner"])
def test_protocol_failures_cannot_be_counted_as_complete_episodes(fake_transport, episode, failure):
    run, _, cleanup = fake_transport

    def malformed(message):
        if message["type"] == "initialize":
            return b"READY\n" if failure == "ready_banner" else None
        if failure == "missing":
            return None
        if failure == "invalid_json":
            return b"not-json\n"
        if failure == "extra_forecast" and message["case_id"] == "third":
            reply = json.dumps(respond_raw(message)).encode() + b"\n"
            return reply + b'{"case_id":"fourth","prediction_mm":[1,2]}\n'
        return respond_raw(message)

    result, peer = run(malformed, episode)
    assert result["state"] == "fail"
    assert result["reason"]
    assert peer.poll() is not None and cleanup
    if failure == "extra_forecast":
        assert len(result["predictions"]) == 3
        assert "extra output" in result["reason"]
    else:
        assert result["predictions"] == []


def test_unavailable_docker_is_unresolved_without_host_execution(monkeypatch, tmp_path, episode):
    from assessment import sequential
    submission = tmp_path / "submission"
    submission.mkdir()

    def missing(*args, **kwargs):
        raise FileNotFoundError(2, "missing Docker", "docker")

    monkeypatch.setattr(sequential.subprocess, "Popen", missing)
    result = sequential.evaluate(submission, ["python", "forecast.py"], episode, IMAGE)
    assert result["state"] == "unresolved"
    assert result["predictions"] == [] and result["events"] == []


def test_docker_launch_failure_is_unresolved_not_submission_failure(monkeypatch, tmp_path, episode):
    from assessment import sequential
    submission = tmp_path / "submission"
    submission.mkdir()

    class FailedDocker:
        def __init__(self):
            incoming, writer = os.pipe()
            reader, outgoing = os.pipe()
            os.close(incoming)
            os.close(outgoing)
            self.stdin = os.fdopen(writer, "wb", buffering=0)
            self.stdout = os.fdopen(reader, "rb", buffering=0)
            self.returncode = 125

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            return self.returncode

    monkeypatch.setattr(sequential.subprocess, "Popen", lambda *a, **k: FailedDocker())
    monkeypatch.setattr(sequential.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 0))
    result = sequential.evaluate(submission, ["python", "forecast.py"], episode, IMAGE,
                                 seconds=1, step_seconds=.1)
    assert result["state"] == "unresolved"
    assert result["predictions"] == []
