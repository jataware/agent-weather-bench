# Forecast improvement: proposed task and ordinary library access

Status: design draft. No new model attempts, executable template or established
difficulty claim. Existing experiment records and systems remain unchanged.

## Agent-facing brief

Build a seasonal rainfall forecasting system for the region and issue dates in
`target-metadata.json`. Produce probabilities of below-, near- and above-normal
rainfall, using the category definitions in that file.

Discover and retrieve appropriate data from the frozen source catalogue. Choose
your forecasting method and use development evaluations to improve it. Each
forecast may use only information permitted at its issue date. The catalogue
records source coverage, units and information cutoffs; final verification
observations are unavailable to you.

Your objective is the lowest ranked probability score on unseen forecast cases.
You have six development-score requests within the shared compute and inference
budget. Final scores are not returned during the attempt.

Submit the forecast arrays, reproducible program and short account required by
the common submission envelope. The program must work from the supplied input
and output paths on new instances of the same forecasting problem.

## Environment statement

Common: a command tool, general scientific Python, the source catalogue,
target/output metadata, ordinary runtime documentation and development scoring.

Weather-library condition adds only:

> acmadDL and AfricaS2S are installed. Their standard documentation is available
> at the locations listed in the environment inventory. Use them where useful.

A Rhiza condition would expose its ordinary skill catalogue in the same way.
The agent discovers operations and chooses how to use them. There is no selected
function, bespoke API guide, mandatory toy run, prescribed algorithm or supplied
task solver. Observed native use is measured afterward, separately from success.

## Controller evaluation

Validity checks cover required support, finite probability distributions, units,
reproduction and information boundaries. Skill is the independently computed
ranked probability score on fixed controller-owned verification cases. Report
raw forecast, climatology and a verified strong comparator beside the score;
validity and forecast performance are separate. Report writing does not substitute
for forecast performance.

The author chooses and freezes data, category definitions, development/final
splits, scoring and comparator before model inference. Method selection and
preprocessing are agent decisions. Source availability and target semantics
belong in metadata; they are legitimate requirements, not solution hints.

## Qualification still required

This problem shape alone does not make a hard task. Before spending more agent
tokens, independently reproduce a strong forecast on the exact allowed sources
and demonstrate attainable improvement over simple forecasts. Use enough
temporal verification cases to distinguish improvement from noise, accounting
for spatial and temporal dependence. Retain failed candidate qualifications.

The previously inspected MAM holdout failed that prerequisite and must not be
retuned into the desired result. Previously inspected holdouts cannot serve as
fresh final evidence. Existing weeks 3–4 development feedback supports RMSE;
the proposed probabilistic task needs an explicitly implemented and tested RPS
feedback interface before execution.

Only after qualification should a bounded cheaper/stronger-model pilot test
difficulty. A scientific capability gap requires valid submissions with a
repeatable performance difference; budget stops, API discovery and packaging
failures remain different findings.

## Interpretation of the completed tooling studies

The earlier guided studies supplied selected functions, operation-specific API
instructions and runnable examples. Their results describe an assisted workflow
bundle. They do not establish autonomous library discovery or generic tooling
benefit. They remain useful diagnostic evidence and are preserved under their
original study names. This proposal does not silently relabel or rerun them.
