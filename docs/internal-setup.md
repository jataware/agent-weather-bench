# Internal setup

This repository is for internal development and review. Scientific, scoring, and data redistribution reviews are pending. Seasonal acquisition is disabled. No repository license has been selected. These limits also apply to the included source snapshots and historical material.

## Inspect a checkout

Use Python 3.12 or later. From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-controller.lock
./bench tasks list
./bench tasks validate --metadata-only
.venv/bin/python -m pytest -q
./bench judge status
```

These commands need no task data, sibling repositories, or model credentials. Metadata validation checks the published task files and source hashes. It does not validate private data or establish scientific approval.

## Install task data

The maintainers distribute the internal data bundle separately. Request the bundle matching the committed input manifests. Copy its three task directories into `var/private/tasks/`:

```text
var/private/tasks/
  acmad-objective/{agent-inputs,controller}/
  seasonal-calibration/{agent-inputs,controller}/
  wvg-definition-audit/{agent-inputs,controller}/
```

Then verify the supplied bytes and recompute the scientific references:

```sh
./bench tasks validate
./bench tasks prepare
```

Preparation uses this bundle and source snapshots inside this repository. It does not read other repositories, retrieve missing files, or rewrite manifests to accept different data. Original workspace names in provenance identify historical sources; they are not filesystem dependencies. Data redistribution remains pending.

## Build the scientific runtime

Use Docker. From the repository root:

```sh
docker build -f runtime/Dockerfile -t agent-weather-bench-runtime:local .
docker image inspect agent-weather-bench-runtime:local --format '{{.Id}}'
```

The base defaults to `python:3.13-slim`. For a fixed base image, add `--build-arg BASE=python@sha256:YOUR_BASE_DIGEST` to the build command. Python package versions are recorded in `runtime/requirements.lock`.

Copy the full content ID printed by `docker image inspect` into:

```sh
./bench systems init my-agent --image sha256:YOUR_IMAGE_ID
```

Configure the adapter or built-in driver in `systems/my-agent/system.yaml`. Existing example systems record the locally built image. Replace `runtime.image` with your image ID before running them on another machine. The harness requires that exact image locally and does not pull images during execution.

With task data installed, update `systems/harness-fixture/system.yaml` to your image ID and run:

```sh
./bench run acmad-objective --system harness-fixture --judge none
```

This fixture tests execution and replay without model calls. Expert criteria remain pending, and it is excluded from agent capability results.

## Optional tools and historical material

The generic harness and runtime need no other source repositories. Comparison systems can add `africas2s`, Rhiza weather skills, or `acmadDL` as declared tools. Record their versions. Historical `accord-rosetta` references describe the package supplied from the `acmadDL` source tree.

Model credentials are environment variables on the controller. Archived launch scripts also use environment variables. Historical reports preserve original names and paths as records of past runs. Source snapshots are records for review and are not imported as executable dependencies.

Archived Rhiza setup scripts require `RHIZA_WEATHER_SKILLS_DIR` to name the approved weather skills checkout. The current generic harness does not use this setting. Historical launch guards remain closed.
