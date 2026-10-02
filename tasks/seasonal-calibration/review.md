# Seasonal calibration review

Review the [prompt](prompt.md), [source plan](source-plan.json), [rubric](rubric.yaml),
and [local reference manifest](input-manifest.json).

## Changes after Zeek's critique

The task now starts from a source plan and asks the agent to acquire and normalize
training data. Normalized pilot arrays remain controller development fixtures,
not starting inputs. The experiment must pin requests and response content, and
distinguish provider transfers, frozen replay transfers and cache hits.

The workflow contract accepts declared commands in any supported language or CLI;
it no longer requires `solve.py` or `predict.py`. Provenance has a shared structured
standard. Six scored outcomes replace fifteen leaves; file/schema validity and
source coverage are checked once as prerequisites. Independently recomputable
development metrics remain a scientific outcome.

The existing independent aggregation agrees with the pilot reference. Acquisition
and raw-response replay have not been validated for the revised task. The inherited
request is a candidate for preflight, not a newly tested API recipe.

## Decisions still open

- Choose provider-backed acquisition or frozen raw-response replay for the primary reproducible comparison; label the modes separately if both are used.
- Confirm that source/provenance/command contracts accommodate CLI substrates.
- Confirm calibration and fold evidence while allowing different sound methods.
- Reserve untouched years for a later release if forecast-skill conclusions are needed; 2005–06 remain inspected development diagnostics.
- Review weights and complete acquisition, clean replay and saved-fit adapters before launch.

Your [original critique](../../docs/reviews/2026-10-02/seasonal-calibration-critique.md)
and [the revision response](../../docs/reviews/2026-10-02/response.md) are retained.
Scientific, scoring and redistribution approval remain pending. No agent attempt
or new provider data retrieval was performed for this revision.
