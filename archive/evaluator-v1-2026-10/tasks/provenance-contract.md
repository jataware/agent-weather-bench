# Provenance evidence contract

Every task delivers `provenance.json` with the following structure. This is a
record of actual work and data access, independent of the tools used.

```json
{
  "schema_version": 1,
  "sources": [{
    "id": "the source URL or institutional identifier",
    "product_version": "the actual product/version or dated institutional case",
    "access": "downloaded",
    "request": {"url": "the requested URL or dataset", "parameters": {}},
    "retrieved_at": "2026-10-02T10:00:00Z"
  }],
  "files": [{
    "path": "retained/monthly-input.nc",
    "sha256": "64 lowercase hexadecimal characters",
    "source_ids": ["the source URL or institutional identifier"]
  }],
  "transformations": [{
    "operation": "describe the scientific processing step",
    "inputs": ["retained/monthly-input.nc"],
    "outputs": ["training.nc"],
    "parameters": {"units": "mm", "month_lengths": [31, 30, 31]}
  }]
}
```

The example is structural, not a completed provenance record. All named files
are retained inside the submission; paths are relative and hashes identify their
actual bytes. Every transformation input/output must appear in `files`.
Source identifiers must cover the supplied source manifest or acquisition plan.
Derived files may have an empty `source_ids` list if transformations establish
their inputs. Source-only documents can be identified and cited without storing
their full copyrighted text.

`access` is one of `downloaded`, `cache_hit`, or `supplied`. Record the actual
source product/version and request (URL or dataset and parameters); use an ISO
timestamp with timezone for downloads and cache hits. A supplied source may use
`null` for an unknown retrieval timestamp. A raw-response replay transfer is
recorded as `downloaded`, with `request.transport` set to `frozen_replay`; it must
not be described as a fresh provider download.

For range/subset access, hash the bytes actually retained and record the spatial
window or byte ranges and source URL. Do not present a subset hash as the hash of
an entire global source object. Native data do not need to be globally downloaded
when the permitted spatial subset suffices.

Processing parameters must include units/conversions, dates and calendars,
coordinates and selection boundaries, missing-value rules and aggregation
weights. Add task-specific evidence: seasonal training-year lists and thresholds
for every fold; ACMAD category mapping and support/weighting conventions; WVG
boxes, seasonal/baseline conventions and which choices came from each source.

The static validator checks the structure, source coverage and retained-file
hashes. A reviewer checks whether the transformation record accurately explains
the scientific artifacts. Trusted access logs are needed to establish that
claimed downloads/cache hits happened and respected the information boundary.
These are distinct kinds of evidence, not repeated scored provenance leaves.
