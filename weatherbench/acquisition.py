"""Training-only, controller-owned frozen native-response retrieval.

No provider network is available during attempts. Reviewed source preparation
and replay transfer have separate byte accounting; normalized fixtures never
enter this transport.
"""
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from .storage import ROOT, digest, read, write

SOURCE_ROOT = ROOT / "var/calibration/seasonal-source-audit"
REVIEWED_MAP_SHA256 = "3c7b2aa84e7c7cbc8081deb2100daadc494e45b3d4c269ef173b1fcd3d83fd63"
REVIEWED_INDEX_SHA256 = "ebaaf1f4ccba00675ded089d90585f10dbff3f0f2d945dcd31988119eea70530"
ACQUIRE_TOOL = {"type":"function", "name":"acquire",
    "description":"Acquire one allowlisted source as a frozen native training subset. Supply its exact source-plan URL and an absolute writable /work destination. For ECMWF also supply source-plan forecast.request unchanged; omit request for CHIRPS. No provider network or normalized answers are supplied.",
    "inputSchema":{"type":"object", "properties":{"url":{"type":"string"}, "destination":{"type":"string"},
                                                       "request":{"type":"object"}},
                   "required":["url","destination"], "additionalProperties":False}}


def _source(root, relative):
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Invalid source snapshot path")
    result = root.joinpath(*path.parts)
    if any(parent.is_symlink() for parent in (result, *result.parents)) or not result.is_file():
        raise ValueError("Source snapshot must contain plain files")
    return result


def preflight(source_plan, source_root=None):
    root = Path(source_root or SOURCE_ROOT)
    map_path, index_path = root / "frozen-replay-map.json", root / "observations-index.json"
    if digest(map_path) != REVIEWED_MAP_SHA256 or digest(index_path) != REVIEWED_INDEX_SHA256:
        raise ValueError("Native replay snapshot changed; review required")
    plan, mapping = read(source_plan), read(map_path)
    if mapping["source_plan_sha256"] != digest(source_plan):
        raise ValueError("Source plan differs from the reviewed replay snapshot")
    expected_years = [str(year) for year in range(1993, 2005)]
    forecast = plan["forecast"]["request"]
    if (forecast["year"] != expected_years or forecast["month"] != ["09"]
        or forecast["leadtime_month"] != ["2","3","4"] or forecast["system"] != "51"
        or forecast["originating_centre"] != "ecmwf" or forecast["area"] != [1,36,-3,39]):
        raise ValueError("Only the reviewed training-only forecast request is permitted")
    urls = plan["sources"]
    rows = mapping["entries"]
    if len(urls) != 37 or len(set(urls)) != 37 or {row["url"] for row in rows} != set(urls) or len(rows) != 37:
        raise ValueError("Replay must cover exactly the declared training sources")
    for row in rows:
        file = _source(root, row["file"])
        if digest(file) != row["sha256"] or file.stat().st_size != row["bytes"]:
            raise ValueError("Pinned native source bytes changed")
        if row["url"] == urls[0] and row.get("provider_request") != forecast:
            raise ValueError("Frozen forecast request mismatch")
    return plan, mapping, read(index_path)


class FrozenReplay:
    def __init__(self, source_plan, controller, source_root=None):
        root = Path(source_root or SOURCE_ROOT)
        self.plan, self.mapping, observations = preflight(source_plan, root)
        self.directory = Path(controller) / "acquisition"
        self.directory.mkdir(parents=True, exist_ok=False)
        self.sources = self.directory / "sources"
        self.sources.mkdir()
        self.events = self.directory / "events.jsonl"
        self.events.write_text("")
        self.entries = {row["url"]:row for row in self.mapping["entries"]}
        self.provenance = {row["url"]:{key:row[key] for key in
                           ("provider_response_ranges","source_pixel_window","grid","mask","units_provenance")}
                           for row in observations["entries"]}
        for row in self.entries.values():
            destination = self.sources / row["file"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_source(root, row["file"]), destination)
            if digest(destination) != row["sha256"]:
                raise ValueError("Native source snapshot copy mismatch")
        shutil.copyfile(root / "frozen-replay-map.json", self.directory / "map.json")
        write(self.directory / "provider-provenance.json", self.provenance)
        self.successes, self.transfer_bytes, self.cache_hits, self.denials = set(), 0, 0, 0

    def acquire(self, url, destination, request, deliver, timeout):
        started = time.monotonic()
        event = {"timestamp_utc":datetime.now(timezone.utc).isoformat(), "type":"acquire",
                 "mode":"frozen_replay", "url":url, "destination":destination, "request":request,
                 "source_snapshot_sha256":REVIEWED_MAP_SHA256, "provider_download_bytes":0}
        try:
            if not isinstance(url, str) or url not in self.entries:
                raise ValueError("Source URL is not in the training-only allowlist")
            if not isinstance(destination, str) or not destination.strip():
                raise ValueError("Destination must be an absolute writable /work path")
            path = PurePosixPath(destination)
            if (not path.is_absolute() or ".." in path.parts or len(path.parts) < 3
                or path.parts[1] != "work" or path.parts[2] == "inputs"):
                raise ValueError("Destination must be under /work, outside read-only /work/inputs")
            row = self.entries[url]
            expected = row.get("provider_request")
            if (expected is not None and request != expected) or (expected is None and request not in (None, {})):
                raise ValueError("Provider request must exactly match the declared training-only request")
            source = _source(self.sources, row["file"])
            if digest(source) != row["sha256"]:
                raise ValueError("Frozen source changed during attempt")
            result = deliver(str(path), source.read_bytes(), row["sha256"], timeout)
            if result["exit_code"] != 0:
                raise ValueError(result.get("stderr", "Native source transfer failed"))
            cache = bool(result.get("cache_hit", False))
            transferred = result.get("transfer_bytes", row["bytes"])
            event.update(status="success", artifact_sha256=row["sha256"], artifact_bytes=row["bytes"],
                         transfer_bytes=transferred, cache_hit=cache, representation=row["representation"],
                         format=row["format"], units=row["units"])
            self.successes.add(url); self.transfer_bytes += transferred; self.cache_hits += int(cache)
            result.update(acquisition={**event, "provider_provenance":self.provenance.get(url, {
                              "derivation":"Reviewed native training-year subset of archived provider response, not a fresh response to the narrowed request",
                              "provider_request":expected})})
        except (ValueError, OSError, RuntimeError, KeyError) as error:
            self.denials += 1
            event.update(status="denied", reason=str(error)[:1000], transfer_bytes=0, cache_hit=False)
            result = {"exit_code":1, "stdout":"", "stderr":str(error)[:1000], "acquisition":event}
        event["seconds"] = time.monotonic() - started
        with self.events.open("a") as stream:
            stream.write(json.dumps(event, allow_nan=False) + "\n")
        return result

    def finish(self):
        summary = {"state":"pass" if self.successes == set(self.entries) else "fail", "mode":"frozen_replay",
                   "source_snapshot_sha256":REVIEWED_MAP_SHA256, "events_sha256":digest(self.events),
                   "required_sources":sorted(self.entries), "acquired_sources":sorted(self.successes),
                   "replay_transfer_bytes":self.transfer_bytes, "agent_cache_hits":self.cache_hits,
                   "denied_requests":self.denials, "provider_download_bytes_during_attempt":0,
                   "source_preparation_provider_download_bytes":self.mapping["provider_download_bytes_observations"],
                   "normalized_fixtures_supplied":False, "private_verification_observations_supplied":False}
        write(self.directory.parent / "acquisition-summary.json", summary)
        return summary


def assess_acquisition(run):
    directory = Path(run) / "controller"
    try:
        summary = read(directory / "acquisition-summary.json")
        events = directory / "acquisition/events.jsonl"
        if summary["source_snapshot_sha256"] != REVIEWED_MAP_SHA256 or digest(events) != summary["events_sha256"]:
            raise ValueError("Trusted acquisition snapshot/log changed")
        if digest(directory / "acquisition/map.json") != REVIEWED_MAP_SHA256:
            raise ValueError("Trusted acquisition map changed")
        mapping = read(directory / "acquisition/map.json")
        if summary["required_sources"] != sorted(row["url"] for row in mapping["entries"]):
            raise ValueError("Trusted acquisition source coverage changed")
        expected = {row["url"]:row for row in mapping["entries"]}
        acquired, transferred, cache_hits, denials = set(), 0, 0, 0
        for line in events.read_text().splitlines():
            event = json.loads(line)
            if event["mode"] != "frozen_replay" or event["source_snapshot_sha256"] != REVIEWED_MAP_SHA256:
                raise ValueError("Unexpected acquisition transport")
            if event["status"] == "success":
                row = expected[event["url"]]
                if (event["artifact_sha256"] != row["sha256"] or event["artifact_bytes"] != row["bytes"]
                    or event["representation"] != row["representation"] or event["units"] != row["units"]
                    or (row.get("provider_request") is not None and event["request"] != row["provider_request"])
                    or type(event["transfer_bytes"]) is not int or event["transfer_bytes"] not in (0,row["bytes"])):
                    raise ValueError("Successful acquisition differs from its pinned native source")
                acquired.add(event["url"]); transferred += event["transfer_bytes"]; cache_hits += int(event["cache_hit"])
            elif event["status"] == "denied":
                denials += 1
            else:
                raise ValueError("Unexpected acquisition event state")
        state = "pass" if acquired == set(expected) else "fail"
        if (summary["state"] != state or summary["acquired_sources"] != sorted(acquired)
            or summary["replay_transfer_bytes"] != transferred or summary["agent_cache_hits"] != cache_hits
            or summary["denied_requests"] != denials):
            raise ValueError("Acquisition summary disagrees with trusted retrieval events")
        return summary
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        return {"state":"unresolved", "reason":"Trusted acquisition evidence unavailable: " + str(error)[:500]}
