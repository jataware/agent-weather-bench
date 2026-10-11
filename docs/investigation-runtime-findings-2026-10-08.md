# Runtime findings during the parallel investigations — 8 October 2026

Three infrastructure issues occurred during this investigation: interrupted collection after an agent completed its submission, a real macOS Python crash during our controller-side author validation, and a later transient Docker daemon outage. They are separate from the earlier Docker import-order failure and the previously removed test that deliberately signaled host Python.

## Optional scratch-state collection discarded a completed run

The baseline ingestion attempt `20261008T120152-native-rainfall-reconciliation-service-area--weeks-1-2-L1-investigation-astra-python-3c1235` finished its scientific submission. The runner froze the ordinary submission files, then aborted while inventorying optional scratch state. The scratch directory contained a symlink at `perturbed_inputs/ECMWF_s2s_precip_2026-09-27.zarr` pointing to `/work/inputs/ECMWF_s2s_precip_2026-09-27.zarr`. The strict file inventory rejected that link.

The failure was in collecting optional state, not in the agent's answer or its scientific reruns. The completed frozen submission was recovered and assessed without an agent retry or submission edits; it passed. The [recovery ledger](../experiments/collection-recovery-2026-10-08.json) records its artifact digest, omitted link and recovery metadata.

The runner now persists the adapter result before collection. Optional state retention copies ordinary files and records omitted links or special files without following them. Scientific deliverables continue to use strict collection. [The regression tests](../tests/test_optional_retention.py) cover a directory link, dangling link and linked state root, and confirm that strict submission collection still rejects links. This runner change does not change a scientific grading instrument.

The original runner had not persisted the exact adapter duration when collection failed. The recovered run therefore has `seconds: null` and is excluded from timing comparisons. Its duration must not be inferred from recovery time, file timestamps or the adjacent tool-enabled attempt. Recovery preserved the original scientific attempt; it did not supply a second chance to solve the task.

The original end-of-run sandbox inspection payload was also lost before persistence. Successful tool execution establishes that the required startup inspection completed; it does not reconstruct the final inspection. The recovered provenance explicitly records `passed: null`, `state: unresolved` and `inspection_payload_lost: true`, and the assessment carries `sandbox: unresolved`. Numerical and prose assessments pass separately. **Recovery does not imply successful end-of-run sandbox attestation.**

## Threaded controller validation triggered a native host crash

We incorrectly parallelized trusted forecast-audit validation inside one Python interpreter. A two-thread partial-cache diagnostic ran template hooks that opened, loaded and wrote NetCDF/HDF5 data concurrently. That process exited with status 139. The macOS report `Python-2026-10-08-140558.ips` records a genuine `SIGSEGV` / `EXC_BAD_ACCESS`, with capture time **14:05:50.1859 Amsterdam time, 12:05:50.1859 UTC**. Its report header is timestamped 14:05:58 local time; these are different timestamps for the same incident.

The faulting thread was thread 2. Its stack starts in `H5F_addr_decode`, passes through HDF5 variable-length data conversion and dataset metadata functions, and reaches `nc4_get_var_meta`, `NC4_HDF5_inq_var_all` and the Python `netCDF4.Dataset` constructor. A separate four-thread certification process also emitted `HDF5-DIAG` errors. We terminated that owned process with `SIGTERM` (exit 143); that deliberate stop is not another observed segmentation fault.

The evidence ties the crash to our concurrent native file-I/O validation path. It does not establish the exact upstream library defect or prove that every HDF5 build has the same limitation. We did not repeat the crash to obtain more evidence.

All threaded scientific validation was stopped. The partial-cache diagnostic was rerun serially and completed cleanly, with all four recorded input-response reruns exiting zero. SHA256 checks confirm that all three forecast-audit source files still match `sources.json`. That verifies source-byte integrity; it does not turn the failed threaded certification into usable evidence.

The clean diagnostic revealed a **separate grading gap**: cached hindcasts or cached production forecasts could each pass an aggregate response check when the other output group changed. Its two `computed_outcome: pass` records are evidence of false acceptance before response-group refinement, not evidence that those cached controls were correct. See `var/review/audit-partial-cache-before-groups.json`; the controller revision and subsequent grading decisions are recorded separately.

The replacement validation workflow uses fresh Python subprocesses, at most two at a time, with scientific file I/O inside each process rather than in shared controller threads. `var/review/parallel_audit_certify.py` subsequently completed all 68 audit control assessments with their intended results and no further native failure. The [audit report](forecast-audit-investigation-2026-10-08.md) records the completed workers and a separate report-serialization recovery. Process separation preserves useful parallelism while avoiding this shared-interpreter path. It is an operational containment measure, not a proven native-library repair or a guarantee against future crashes.

## Later Docker daemon unavailability

After the full test run, the Docker daemon was temporarily unavailable. No forecast-audit agent inference was in flight; those agent attempts had not launched. The investigation lead restored Docker Desktop with `open -a Docker`, then saved a health snapshot at **12:28:50 UTC** in `var/review/docker-recovery-2026-10-08.txt`. That record shows server version **28.0.4**, 12 CPUs, 8,217,751,552 bytes of configured memory, and Desktop status `running`.

The initial unavailable response and restart action are recorded in the investigation lead's tool transcript and incident handoff, rather than a separate log file. The saved snapshot supports the subsequent healthy state. The cause of the outage is unknown; there is no basis here to connect it to the earlier native HDF5 crash or diagnose a Docker implementation defect. Fresh trusted-control replays were resumed after recovery; their scientific results belong in the separate control and investigation reports. This incident does not supply a failed audit-model attempt.

## Evidence and limits

[The runtime evidence ledger](../experiments/investigation-runtime-findings-2026-10-08.json) records hashes of the recovery ledger, crash report and diagnostic logs, selected crash fields, and independently rechecked source hashes. Local evidence includes:

- `var/review/docker-recovery-2026-10-08.txt`: saved Docker health snapshot after restoration.
- `var/review/audit-certification-threaded-failure.log`: HDF5 diagnostics from the stopped threaded certification.
- `var/review/audit-partial-cache-before-groups-threaded-failure.txt`: the failed diagnostic's redirected output, which is empty; the native crash report supplies the failure evidence.
- `var/review/audit-partial-cache-before-groups.json`: the completed serial diagnostic with explicit zero exit codes.
- `/Users/ezekielbarnett/Library/Logs/DiagnosticReports/Python-2026-10-08-140558.ips`: the macOS native crash report.

The earlier Docker failure involved a Linux scientific image aborting on a particular `cfgrib` / `pyproj` import order. Its verified preload workaround remains a different finding. The earlier host notification source was a regression test deliberately sending `SIGSEGV`; that test now simulates the executor record. **Neither prior fix prevented this new, unintended crash in threaded author validation.**

No model retries, crash reproductions, Docker actions or additional certification loops were performed to write or update this report. The recovery, serial diagnostic and saved health snapshot support the specific conclusions above; they do not establish general runtime reliability.
