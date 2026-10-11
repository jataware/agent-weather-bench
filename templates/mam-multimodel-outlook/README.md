# MAM outlook: retrieval through calibrated forecast

Start with the complete control, including fresh retrieval during reruns:

```sh
.venv/bin/python -m assessment assess mam-multimodel-outlook kenya-interior--mam-2016 --control correct --output var/review/mam-correct
.venv/bin/python -m assessment rubric mam-multimodel-outlook
```

The default executor runs the submitted command in Docker. Trusted local
control verification can use `--local-trusted`. Source bytes must already be
frozen at the private path in `sources.json`. `prepare` verifies that snapshot;
`prepare --source ARCHIVE` restores the hash-identified files from another
local copy. `freeze_source.py` documents the isolated one-time cache decode,
not a requirement to unpickle caches whenever a task runs.

| Decision | Home |
| --- | --- |
| The job | `brief.md`: retrieve monthly sources, prepare seasonal totals, calibrate four centres, issue probabilities and report historical skill |
| The question | `spec.yaml`: reproduce an explicit ensemble-regression recipe |
| The instruments | `reference.py`: reference agreement, probability/combination/score identities, fresh reruns and held-out-year isolation; `acquisition.py`: source service and request evidence |
| The result | Scientific completion, supplementary prose review and descriptive withheld-season skill have separate columns |

This is a prescribed forecast-production task. It does not optimize an arbitrary
method, estimate multi-model weights or reproduce a complete national consensus
process. All four source ensembles are distinct centres, with 25/40/28/31
members. The initial instance has 23 training seasons and one retrospective
forecast season on 18 shared interior cells. Only three convention choices
are classified: physical/calendar integration, fold-local thresholds, and equal-centre
combination. Their sixteen joint readings distinguish accepted computation from
named pitfalls. Other unrecognized answers remain unresolved.

`science.py` defines the NumPy/SciPy calculation. `reference_independent.py`
uses separate interpolation, scalar regression, manual sample quantiles, normal
CDF and RPS arithmetic. Native AfricaS2S parity is an additional diagnostic;
it is not imported by either deciding implementation. A library update therefore
cannot silently redefine the task's accepted answer.

The staged input root has two parts. Only `public/` is mounted for the actor.
`provider/` is mounted read-only into a controller-owned source sidecar, accessible
through a private HTTP service on an isolated Docker bridge. Withheld CHIRPS
2016 observations and source-decode diagnostics are never in either actor
mounts or provider resources. There are no provider credentials, published
ports or general internet access. The source snapshot preserves decoded
monthly values and native schema in curator-produced NetCDF; it does not claim
to retain original provider GRIB responses or provide CDS-compatible transport.

Each replay starts a fresh service with the controller-selected snapshot. The
changed-data probe updates object hashes and source arrays, so hard-coded answers
and stale submission caches fail. Another probe changes one training year's
verifying observation: that year's cross-validated forecast must stay unchanged.
Private request logs retain object hashes, bytes and timings separately from
scientific completion. Fetching files alone does not establish correct use of
their contents; the reference and source perturbations test that relationship.

The initial recipe has useful native-tool support: acmadDL normalization can
prepare native monthly rates and coordinates; AfricaS2S default-Wilks `ereg`
can produce calibrated component probabilities and equal-model combinations.
Live-provider discovery, authentication and provider download throughput remain
outside this frozen-service experiment. Tool availability and required-tool
conditions belong to the system definition, not to the scientific rubric.

Scientific approval and redistribution approval are pending. Public historical
years may have appeared in model training; one forecast year on neighbouring
cells is not a stable model ranking or a demonstrated capability boundary.
