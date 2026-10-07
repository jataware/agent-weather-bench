"""Build a local, task-by-task account of the development attempts.

Reads frozen solver material and stored assessments. It never runs submitted
code, starts a model, changes an assessment, or reads authentication material.
Run from the repository with .venv/bin/python archive/docs-2026-10/scripts/build_task_runbook.py.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

import yaml

ROOT = Path(__file__).resolve().parents[3]            # the repository root; this folder is an archive
sys.path.insert(0, str(ROOT))
from weatherbench.task_tools.render import markdown  # noqa: E402

OUT = ROOT / "var/review/task-runs.html"
OVERLAY_POLICY = "809715abb9cee093b1f7bd5d80503f515efa5bfe8a40b077050259c19b121c73"
CORE = ("task.yaml", "prompt.md", "rubric.yaml", "input-manifest.json", "sources.yaml")
SOURCE_FILES: dict[str, str] = {}
HELPER_REVIEWS: dict[str, list] = defaultdict(list)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tracked(path):
    path = Path(path)
    SOURCE_FILES[str(path.relative_to(ROOT))] = digest(path)
    return path


def load(path):
    return json.loads(tracked(path).read_text())


def read(path):
    return tracked(path).read_text()


def esc(value):
    return html.escape(str(value), quote=True)


def link(path, label=None):
    path = Path(path)
    if path.is_absolute():
        path = path.relative_to(ROOT)
    return f'<a href="../../{quote(str(path), safe="/")}">{esc(label or path.name)}</a>'


def pre(value):
    text = json.dumps(value, indent=2, default=str) if not isinstance(value, str) else value
    return "<pre>" + esc(text) + "</pre>"


def details(label, content, cls=""):
    return f'<details class="{cls}"><summary>{esc(label)}</summary>{content}</details>'


def table(headers, rows, cls=""):
    return f'<div class="table-scroll {cls}"><table><thead><tr>' + "".join(
        f"<th>{esc(x)}</th>" for x in headers
    ) + "</tr></thead><tbody>" + "".join(
        "<tr>" + "".join(f"<td>{x}</td>" for x in row) + "</tr>" for row in rows
    ) + "</tbody></table></div>"


def state(value):
    safe = value if value in {"pass", "fail", "unresolved", "not_applicable", "pending", "partial", "failed"} else "other"
    return f'<span class="state {safe}">{esc(value.replace("_", " "))}</span>'


def bullets(xs):
    return "<ul>" + "".join("<li>" + esc(x) + "</li>" for x in xs) + "</ul>"


def leaves(node):
    if "children" not in node:
        yield node
    else:
        for child in node["children"]:
            yield from leaves(child)


# These explanatory notes are curator interpretations of the linked frozen
# material/audits, not replacements for a stored automatic or expert grade.
TASKS = {
    "seasonal-calibration": {
        "title": "Seasonal acquisition and calibration",
        "objective": "Acquire native forecast and rainfall subsets, construct Kenyan OND seasonal totals, fit and validate a calibration, and retain a workflow that can predict from a frozen fit.",
        "given": [
            "Starts with source-plan.json only. Normalized training/reference fixtures mentioned in the package inventory were not mounted for the solver.",
            "The acquisition tool supplies 37 frozen native-source responses: ECMWF system 51 September-initialized precipitation reforecasts and CHIRPS monthly observations for 1993–2004. This is recorded raw-response replay, not a new provider download.",
            "The Kenyan box is south −3°, north 1°, west 36°, east 39°. Forecast leads 2/3/4 cover October/November/December. The agent must convert m/s to mm/day and use actual calendar month lengths; CHIRPS is monthly mm.",
            "The calibration method is open. Training-only validation must exclude each held-out year from fitting, thresholds and tuning. The task asks for probability reliability evidence and a baseline, not just plausible probabilities.",
        ],
        "private": "Controller reference aggregation and 2005–2006 verification observations are outside solver mounts. Those historical verification years had already been inspected during development; they are not an untouched prospective holdout.",
        "evaluate": "Static checks inspect seasonal aggregation, development-output schema and common delivery contracts. Trusted acquisition verifies the actual access ledger. Replay and saved-state inference assess executable delivery. Calibration, leakage freedom, reliability and interpretation still need expert evidence; passing acquisition does not automatically award the 15-point mixed criterion.",
        "changes": ["No frozen task instructions or inputs were changed between these three attempts. The current core task files still match every frozen snapshot.", "Later diagnostic alignment distinguished coordinate/member metadata defects from rainfall-unit errors: the first attempt's values match after alignment. Its original aggregation failure remains recorded.", "Source-declaration diagnostics were subsequently separated from invalid provenance. This is an evidence-attribution repair, not a retroactive scientific success or a new executed grade."],
    },
    "acmad-objective": {
        "title": "ACMAD probability consolidation",
        "objective": "Reproduce the final objective combination of three already calibrated seasonal probability products and audit support, weighting sensitivity and component disagreement.",
        "given": [
            "Three ASO 2026 probability products on a common latitude/longitude grid, supplied as forecast-precip.nc, forecast-sst.nc and observed-sst.nc. These are calibrated category probabilities in percent, not raw ensemble-member rainfall.",
            "The 0.3 skill threshold and 50 mm dry mask were already applied upstream. The agent is explicitly told not to apply either again.",
            "Use equal weights across available complete three-category distributions, renormalize correctly, retain support counts and leave no-support cells missing. Compare with a nominal 2:8:8 weighting and report differences in percentage points.",
            "Actual member-pool counts are unavailable. The 2:8:8 scenario is a sensitivity analysis; it cannot establish actual pooled-member probabilities. No forecast fitting, retrieval or published skill replication is required.",
        ],
        "private": "Independent expected objective probabilities, support counts, sensitivity and disagreement arrays stay with the controller. There is no future observed-rainfall skill test for this consolidation task.",
        "evaluate": "Independent array comparisons evaluate objective probabilities (45 points) and support/sensitivity/disagreement (25 points). Report interpretation is 20 expert points. The last 10 points require usable replay and reviewer evidence; original-input replay can faithfully reproduce a scientifically wrong solution.",
        "changes": ["An initial adapter/protocol failure preceded the three scientific attempts; it is shown separately below.", "The float32 percentage-point disagreement comparison originally used a tolerance tight enough to reject correct subtraction. A bounded rounding allowance was introduced after the attempts. The correct attempt changed from 45–75 to 70–100; its submitted files were not edited.", "The repaired tolerance does not rescue the genuine ×100 scale mistakes in the other two attempts. Later expert-packet/trace policies changed, but no native model judge was called."],
    },
    "wvg-definition-audit": {
        "title": "WVG definition and implementation audit",
        "objective": "Compare a paper's Pacific predictor geometry with an existing implementation, compute both under explicit common conventions, and explain the resulting differences without claiming a full paper reproduction.",
        "given": [
            "ERSST v5 monthly SST for 1981–2023, an implementation excerpt, provenance and a source manifest. Paper/implementation boxes and the comparison conventions are specified in the task.",
            "All three runs use codex-luna-literature, whose separate /substrate/literature directory contains a frozen publisher-text extract and a manifest. The literature is supplied, not autonomously retrieved; the four-file initial input inventory alone omits this assistance.",
            "The comparison fixes cosine-latitude weighting, closed box boundaries, equal-month MAM means and a 1981–2010 sample-standard-deviation baseline. Western-V uses three box means; WVG uses standardized Niño 3.4 minus standardized Western-V under the curator contract.",
            "The scientific question includes distinguishing paper evidence from curator choices, temperature anomalies from standardized indices, and high correlation from exact equivalence or forecast-skill replication.",
        ],
        "private": "Controller reference indices and comparison metrics are not mounted. The source extract is available to the agent. This task has no withheld future forecasting target.",
        "evaluate": "Box averages, standardization and index arrays contribute 50 deterministic points; comparison arithmetic contributes 15. Source interpretation contributes 25 expert points, and an executable relocated replay contributes 10. The science and replay interface are assessed separately.",
        "changes": ["All three runs have the same frozen scientific material and literature substrate and start independently, without scientific feedback.", "The numerical results remain 65–90 in the preserved assessments. Later manual source review identified overstrong attribution in two reports; those concerns are not formal expert ratings or new scores.", "Two manifests are rejected before replay can run; the third command executes and fails on output relocation. Those are different delivery failures despite identical score bounds."],
    },
    "short-rains-workflow": {
        "title": "East African short-rains workflow",
        "objective": "Repair an inherited rainfall-unit convention, implement issue-time-safe nested seasonal prediction and probabilistic verification, and retain inference from saved fitted state.",
        "given": [
            "Real CHIRPS regional monthly rainfall (three regions, 1993–2019), ERA5 monthly SST (1993–2023), CanSIPS OND forecast indices and 108 prescribed search candidates.",
            "Legacy normalization/catalog/fetch scripts, starter workflow/search snippets and literature notes are supplied. The rainfall array says mm/day but encodes monthly totals divided by 30; the correct recovery is ×30, rather than multiplying by each month's calendar length.",
            "The method contract is detailed: climatology, antecedent IOD, forecast IOD and nested univariate OLS alternatives; identity/log1p target transforms; Student-t predictive uncertainty and CPT-style quantiles.",
            "At the September 30 issue, observed SST may only extend through August 31. Outer prediction years 2005–2019 and inner candidate-selection folds must fit moments, thresholds and transformations on their own permitted years. Production is fitted once on 1993–2019 for 2020–2023.",
        ],
        "private": "Controller 2020–2023 rainfall targets and independent scientific reference arrays are outside solver mounts. Source data are retrospective final products, so calendar discipline does not establish real-time release-vintage availability.",
        "evaluate": "Checks cover unit recovery, seasonal totals, all hindcast/production probabilities, nested losses/selections, thresholds and verification arithmetic. Replay reproduces the outputs; a target perturbation probes information isolation; inference removes rainfall inputs and changes allowed predictors. Correct arrays do not by themselves resolve source/method interpretation or saved-state code review.",
        "changes": ["An earlier assessment treated the allowed inclusive training-year-range representation as if it had to enumerate every year. That representation check was repaired without changing the scientific inputs or prompt; see the preserved assessment records below.", "The second Fable run changed several settings: maximum output 8,192 → 32,768 tokens, per-attempt dollar cap $18 → $9, response timeout 180 → 300 seconds. It was a fresh attempt, not a continuation or a controlled output-limit-only experiment.", "Both Fable runs stopped because reserving another maximum-size call would exceed their configured dollar budgets. The first also encountered truncated generated code. Their differing completion does not establish a fair model capability ranking."],
    },
    "weatherbench-verification": {
        "title": "WeatherBench forecast verification and diagnosis",
        "objective": "Reproduce temperature verification on exact common valid-time support and quantify the effects of three consequential mistakes in a supplied comparison script.",
        "given": [
            "Real public HRES forecasts, ERA5 truth and 1990–2019 climatology on a 64×32 grid, with January 1–20, 2020 initializations and 24/72/120/168-hour leads. Temperature is in kelvin.",
            "A broken comparison script, metric excerpts, source notes and licenses. A curator-created availability mask exercises support handling; it is not a recorded real forecasting outage.",
            "Compare HRES, initialization-time ERA5 persistence and valid-time climatology over global, northern extratropical and tropical regions. All systems must share finite truth/forecast/availability support.",
            "Compute spatially weighted case MSE then temporally average and square-root it; compute per-case uncentered anomaly correlation then average. Climatology ACC is undefined and must remain NaN/null. Quantify correct, initialization-truth, uniform-weight, own-support and all-three-fault variants.",
        ],
        "private": "Independent metric and fault-contrast reference calculations are controller-only. The solver is given the observations needed to perform verification; this is not a forecast training or private-target prediction exercise.",
        "evaluate": "Exact coordinates, units, support masks, per-case arithmetic, headline metrics and fault contrasts are independently compared. Replay and a changed-HRES/availability probe check the executable diagnostic. Expert criteria ask whether effect directions and scientific boundaries are interpreted correctly.",
        "changes": ["The initial evaluation was saved, but building an assessment crashed because a YAML publication date was not JSON serializable. This was a controller failure, separate from the solver's defects; a later policy produced the recorded assessment.", "The solver appended effect sizes to report.txt after recording its provenance hash. The final file inventory is sound, but the solver's report hash is stale.", "The old checker incorrectly reported missing source coverage as a consequence of that stale hash. The later static overlay finds all source IDs and reports coverage pass, while provenance still fails. No submitted solution or stored executed grade was rewritten."],
    },
    "cca-seasonal-reproduction": {
        "title": "Seasonal EOF/CCA method reproduction",
        "objective": "Adapt an existing seasonal CCA implementation to East African rainfall, including training-only EOF/CCA fitting, nested mode selection, probability calibration and saved-state inference.",
        "given": [
            "ERA5 June–August SST at 27 native cells for 1993–2023 and CHIRPS OND rainfall at 12 cells for training years 1993–2019.",
            "Pinned AfricaS2S CCA code, an implementation/method record, a PyCPT probability-route excerpt, candidates.json and a detailed algorithm.md. This is a tightly specified scientific code adaptation with substantial supplied assistance.",
            "Fourteen candidate mode combinations include a fixed (1,1,1) comparator. Training-only weighted standardization and EOFs precede CCA; probabilities use the specified rotation-invariant Student-t route and CPT-style terciles.",
            "Expanding outer years 2005–2019 contain expanding inner folds; full-training overlap is explicitly a diagnostic, not CV. The 2020–2023 production fit uses only the 1993–2019 training targets. Saved-state inference must not reopen training targets.",
        ],
        "private": "2020–2023 rainfall targets and independent prediction/selection/probability references are controller-only. The task does not ask for a complete CPT binary reproduction or published paper score replication.",
        "evaluate": "Independent checks cover nested mode losses/selection, fixed and nested hindcasts, probability thresholds, production forecasts, full-fit diagnostics and verification arithmetic. Trusted replay, target perturbation and changed-predictor inference probe executable state and boundaries. Route interpretation remains a mixed criterion even when its numerical checks pass.",
        "changes": ["Luna and Astra use the same frozen task/input material but different wall/tool-command budgets. They are separate starts, not a repair sequence with expert feedback.", "The first five overnight runs launched under policy d8ed3bb8… and were assessed again under 7e6d17d6… after controller/packet repairs. Both valid preserved assessments are shown where present.", "Later local reviewers assessed selected Astra criteria on bounded packets. Their provisional 0/1/2 judgments do not replace the native judge=none score bounds; relevant source/fold evidence was omitted from some packets."],
    },
    "station-verification": {
        "title": "Station observation and gridded-forecast verification",
        "objective": "Parse actual East African station observations, align exact UTC forecast valid times, compare interpolation methods on common support and quantify deliberate verification faults.",
        "given": [
            "Real NOAA ISD CSV observations for six stations, January 1–27, 2020, including original row order, duplicates and quality fields; real HRES forecasts with 20 initialization dates and four leads.",
            "NOAA format PDFs, a station manifest, WeatherReal README/parser code, a broken comparison and a curator-created method availability mask.",
            "TMP is signed tenths Celsius: accept specified quality flags 1/5, reject +9999, convert to kelvin, match exact UTC seconds, and resolve duplicates after QC using report-type priority then original row order.",
            "Compare bilinear and nearest interpolation on the coarse public grid, including periodic longitude. Preserve empty-support stations. Headline RMSE pools actual station cases; equal-station averaging is a separate diagnostic. Controlled faults include Celsius treated as kelvin.",
        ],
        "private": "Independent station parsing, interpolation and diagnostic references are controller-only. The solver receives observed records; sparse coverage is real, whereas the method-availability perturbation is constructed.",
        "evaluate": "Independent checks validate station truth, coordinate/time alignment, common masks, metric values and each fault variant. Ordinary replay checks reproduced submitted scientific arrays; the changed-stencil/mask test independently recomputes truth and metrics and can detect a faithfully replayed error.",
        "changes": ["Original replay passed even though the all-three-fault output was wrong: reproducing the submitted arrays was not enough to establish that every diagnostic was scientifically correct. The independent changed-input test failed.", "The original broad replay detail overstates correctness for that faulty contrast; the replay result is preserved and explained rather than silently changed.", "Unlike the WeatherBench/monthly hash cascades, this attempt actually uses incorrect source identifiers and paths escaping the retained submission. Those genuine provenance/source failures remain in the later overlay."],
    },
    "monthly-cycle-calibration": {
        "title": "Monthly cyclic regression calibration",
        "objective": "Fit cyclically shared monthly regression slopes with whole-year nested validation, measure whether sharing helps and deliver production forecasts from saved fitted state.",
        "given": [
            "Previous-calendar-month SST predictors for 1993–2023 and CHIRPS monthly rainfall targets for three regions, 1993–2019, retaining all 12 months.",
            "An explicit algorithm.md, literature notes, an AfricaS2S smoothed-method excerpt and six candidate cyclic regularization strengths with December/January coupling.",
            "Compare climatology, independent-month, constant-slope and nested cyclic methods. Hold out whole years in inner and outer validation; distinguish standardized coefficients from physical mm/°C slopes.",
            "Outer years are 2005–2019. Production uses one 1993–2019 fit for 2020–2023. The specification allows negative linear predictions; the agent should report the behavior rather than silently clip it.",
        ],
        "private": "2020–2023 rainfall targets and independent moment/coefficient/selection/prediction references are controller-only. Saved inference receives predictors without target files.",
        "evaluate": "Checks compare fold moments, cyclic/physical coefficients, nested inner selection, outer predictions, production predictions and verification. Whole-year target perturbation and saved inference probe information use, but a crashing probe establishes a runtime defect, not demonstrated leakage.",
        "changes": ["The agent successfully generated outer artifacts, then made a late source edit after creating documentation/provenance. It did not rerun the edited workflow; the frozen inference branch now uses an uninitialized variable.", "The production checker stopped at missing units, concealing an additional 34.9691 mm constant-comparator numerical error. Later array diagnostics separated those two defects.", "The rubric groups correct nested selection with wrong production output, so the 20-point selection criterion receives zero. This grouping is an evaluation-design concern, not a changed score. The later overlay repairs misleading source-coverage attribution only."],
    },
    "subseasonal-optimization": {
        "title": "Subseasonal forecast optimization",
        "objective": "Improve weeks 3–4 precipitation forecasts on a real regional benchmark using training labels and limited development feedback, then freeze a reusable forecasting method for private final evaluation.",
        "given": [
            "Nine southwest US cells and weekly Sunday issues. CPC observations and CFSv2 reforecasts are already 14-day total mm; lead 14 forecasts target issue+14 days through the following 14-day window.",
            "Training includes 831 labeled issues whose targets end before 2015; development has 147 unlabeled issues in 2015–2017; final has 208 unlabeled issues in 2018–2021. Development/final coordinates and CFSv2 features are public.",
            "A train-only seasonal-climatology/affine starter and curator source notes are supplied. Methods are open. Training validation must respect label target-end dates and overlapping windows.",
            "At most five trusted development feedback calls return aggregate weighted RMSE/skill, never target labels. Adaptive use of this feedback is allowed and must be documented; no final-score tool exists. Prediction shape/support/units cannot be changed to improve the score.",
        ],
        "private": "Development and final observed targets stay outside the solver. Each development query is frozen in a trusted ledger. Final RMSE is computed only after final submission freezes; historical targets inspected in development do not establish an untouched public benchmark holdout.",
        "evaluate": "Deterministic prediction schema earns 25 points. Expert admissibility (30), performance/interpretation (25) and reusable-method review (20) remain unresolved without expert ratings. Numerical forecast performance is reported separately, not required to exceed a baseline to complete a scientifically honest experiment.",
        "changes": ["The frozen prompt names /work/submission/inputs, while the actual start request maps initial data to /work/inputs. Both agents located the data. This prompt typo remains disclosed rather than retroactively rewritten.", "Luna used one feedback query; Astra used all five and adapted later search families after earlier feedback. These are different research trajectories; Astra's later searches were not blind to development scores.", "Earlier bounded judge packets omitted some trace/feedback evidence, and a local review incorrectly treated unavailable feedback as a proven failure. Later previews improve evidence visibility; no paid/native judge score was issued and no final targets were exposed during either attempt."],
    },
    "conservative-downscaling": {
        "title": "Conservative seasonal rainfall downscaling",
        "objective": "Audit an uncertain forecast unit scale, map coarse forecast ranks to observed rainfall and reconstruct nonnegative fine-scale rainfall that conserves calibrated coarse-cell volume.",
        "given": [
            "Four Kenyan one-degree February-initialized CFSv2 MAM predictor cells for 1993–2016; a 40×40 CHIRPS 0.05° grid with 1993–2008 training MAM totals; exact spherical cell geometry.",
            "Original AfricaS2S BCSD code, a native CPT header, inherited CHIRPS normalization/catalog code and a source audit. The raw forecast physically claims mm/day but its scale is unresolved; do not invent a ×92 conversion.",
            "The required independent rank-paired maps use sorted raw/observed samples, prescribed interpolation/tie rules and tail clamping. Fine climatological ratios must remain nonnegative with unit area-weighted coarse means.",
            "Leave-one-year-out fitting must exclude each held-out year from coarse mapping and fine detail. A fixed full-training state produces 2009–2016 forecasts. Conservation is relative to mapped/calibrated mm, not to ambiguous raw-source moisture.",
        ],
        "private": "Fine-scale 2009–2016 CHIRPS verification truth and independent coarse/fine references are controller-only. Only 1993–2008 fine training truth is supplied to the solver.",
        "evaluate": "Static checks assess spherical geometry, rank mapping, spatial detail, leave-one-year-out results, positivity and volume conservation. Replay, whole-held-year truth perturbation, no-truth saved inference and raw predictor ×92+7 invariance are separate probes. Final forecast RMSE versus climatology is an outcome, not the construction correctness score.",
        "changes": ["As in the subseasonal task, the prompt's initial input path differs from the actual /work/inputs start mapping. The solver resolved it; the frozen prompt is retained.", "The one attempt passes numerical construction and all four execution/invariance probes. It nevertheless has worse final RMSE than climatology; passing mathematical conservation must not be described as improved forecasting skill.", "No model/task changes or execution reruns were used to improve this result after the disk-space concern. Later diagnostics/previews leave its stored assessment unchanged."],
    },
}

RUN_NOTES = {
    "68489d": ["The adapter failed before a usable scientific submission. Two tool calls and about nine seconds are a framework/protocol trial, not evidence that the model could not solve probability consolidation."],
    "b79c2c": ["Constructed probability-combination artifacts, but divided fraction-scale probabilities by 100 again. The objective and weighting sensitivity therefore have genuine scale errors.", "Support and component-disagreement checks pass. The declared replay omits {output_dir}, so the controller rejects it before executing submitted code."],
    "7406d9": ["Computed objective probabilities, support counts, weighted sensitivity and component disagreement correctly and delivered a valid relocated replay.", "Originally lost 25 audit points solely because float32 disagreement rounding exceeded the old tolerance. After that checker repair, the same frozen files pass both deterministic criteria (70 points). Report interpretation and reviewer-dependent workflow credit remain unresolved."],
    "bc648f": ["Delivered a replayable solution, but objective and sensitivity values are 100 times too small. Replaying it successfully reproduces those incorrect scientific outputs.", "The objective/audit leaves fail, while interpretation and reviewer-dependent reuse remain unresolved. A pass in replay is not a substitute for independent expected-value comparison."],
    "a433e5": ["Recomputed both WVG definitions and all comparison metrics correctly. Reported correlation 0.99478023, mean absolute difference 0.14817210 and maximum difference 0.57981819.", "Read both implementation and supplied literature. Manual review finds an overstrong claim that the paper standardizes WVG temperatures; the supplied passage supports standardization of WPG more directly. Formal interpretation remains unresolved.", "Replay omits {output_dir} and fixes its output location, so the controller does not execute it."],
    "fda4e0": ["Computed the same correct index/comparison values and read the supplied literature and implementation. Its source interpretation distinguishes the task's standardized comparison from the paper's temperature/anomaly definitions more carefully.", "The manifest includes the required output argument, but run.py ignores it and writes /work/indices.nc. Trusted replay actually runs and fails with PermissionError on the read-only frozen submission."],
    "164334": ["Scientific indices and comparison metrics match the reference, as in the other WVG attempts. The source review flags an overstrong claim that this standardized construction is exactly the paper definition.", "The replay command omits the output-directory placeholder; it is rejected before execution. All three runs show correct numerical work but none demonstrates complete reusable delivery."],
    "2ef9f3": ["Acquired all 37 native-source responses and fitted a cellwise affine rainfall calibration. Aggregated values agree after alignment, but latitude order and member metadata violate the required output grid/schema.", "The Gaussian probability calculation reverses CDF signs, producing 144 negative near-category probabilities (minimum −0.37016). Exported development predictions use full-training fits despite reporting separate leave-one-out results.", "Reported leave-one-out MAE is about 79.32 mm; the exported in-sample artifact instead has MAE about 59.89 mm. Saved coefficient/grid alignment, provenance, replay and actual reliability-bin evidence are also incomplete."],
    "9e6394": ["Acquired all 37 source subsets, then explicitly ended with an incomplete final response and no scientific submission artifacts.", "Stopped after roughly 32 seconds and 42 tools, rather than exhausting the 900-second/90-tool allowance. Acquisition success alone is not sufficient evidence for the mixed source/interpretation criterion."],
    "8ec234": ["Acquired all sources and produced correct aggregation, leave-one-out rainfall/probability predictions and retained fold thresholds.", "Verification category labels nevertheless use full-training thresholds, changing 8 of 144 held-out labels. Reported Brier score 0.75 versus correctly held-out 0.80556, and accuracy 0.625 versus 0.59722, reveal consequential evaluation leakage.", "Thirty denied acquisition requests caused by colliding destination filenames were corrected but consumed budget. The run exhausted 90 tool calls before complete contracts, report and replay delivery; mixed/expert scientific leaves remain unresolved rather than receiving automatic credit."],
    "624212": ["Repaired the ×30 rainfall convention and implemented all prescribed systems, nested candidate search, training-only thresholds and probabilistic verification. Scientific arrays match the independent reference.", "Delivered complete contracts, offline replay, a passing target-isolation probe and saved-state inference without rainfall under changed allowed predictors. The deterministic nested-calibration and verification criteria contribute 50 points; processing interpretation and reviewer-dependent reuse still need expert ratings."],
    "c5d9e0": ["Explored sources and began a large implementation, but an 8,192-token response limit truncated generated code. It did not freeze the required complete scientific deliverables.", "The Anthropic driver stopped when another reserved maximum-output call would exceed the $18 per-attempt cap. Recorded spend was $12.75141 over 21 provider calls; unfinished delivery should be interpreted in that budget/adapter context."],
    "62a092": ["On a fresh attempt with a 32,768-token output allowance, produced core scientific arrays matching the short-rains reference and tested aspects of replay/inference during the run.", "The frozen final submission still lacks complete provenance/execution/handoff packaging, so trusted required delivery/reuse fails. Correct deterministic arrays contribute 50 points.", "This attempt had a $9 cap and 300-second response timeout, not the first run's $18/180-second settings. It stopped on the next-call budget reservation after $6.65883 and 12 provider calls. The two Fable attempts are not a controlled comparison."],
    "41b31b": ["Implemented correct common-support verification, RMSE/ACC arithmetic and all numerical fault contrasts. Both ordinary replay and an independent changed-HRES/availability probe pass.", "Appended effect sizes after hashing report.txt, leaving only that provenance file hash stale. All required source identifiers are present; the old source-coverage failure was a checker cascade.", "The prose says initialization truth suppresses HRES errors, while its own numbers show HRES RMSE increases by 0.954, 1.538, 1.504 and 1.279 K; persistence becomes zero. Numerics are correct, but that interpretation is defective."],
    "938881": ["The fixed (1,1,1) outer CCA predictions match within about 4.55×10⁻¹³, demonstrating a correct component fit.", "The inner-loss calculation double-indexes an already scalar value and broadcasts it, corrupting nested selection. Tercile thresholds use the wrong quantile estimator (up to about 33.694 mm error), and production/full-fit routes are incorrect.", "Required reports/contracts are missing. Scientific multivariate, probability and verification-route criteria fail; a correct fixed comparator is not the complete nested probabilistic reproduction."],
    "ac6241": ["Implemented training-only weighted EOF/CCA fitting, correct nested candidate losses/selection, prescribed probability routes, full-fit diagnostic and production state. Independent numerical comparisons pass.", "Full replay, target perturbation and no-target changed-predictor saved inference pass; production prediction differences are around 1.14×10⁻¹². Deterministic multivariate/probability criteria earn 45 points, while route interpretation and review-dependent delivery remain unresolved."],
    "66e7b1": ["Searched 15 train-only temporal-validation configurations (one/two/three harmonics across five ridge strengths) and retained an executable fitted calibration with complete development/final predictions.", "Used one development feedback query: RMSE 11.89974 mm versus climatology 12.05160 and raw CFSv2 14.88975. Final RMSE is 14.02172 versus climatology 14.28153 and raw 14.89005.", "All replay/changed-feature/saved-inference checks pass. Manual recomputation finds its reported CV RMSE 12.06595 uses incorrect weight normalization; the correct value is 13.29273. The common factor leaves candidate ranking unchanged, but the reported error is wrong."],
    "ff16df": ["Parsed observations/QC/duplicate rules correctly, computed both interpolation methods and correct headline/common-support verification, retaining empty-support cases.", "In the all-three-fault variant, the Celsius offset is omitted, causing an approximately 271 K diagnostic discrepancy. Ordinary replay reproduces its original wrong output; the independent changed-input check detects the error.", "Provenance uses paths outside retained submission and incorrect source identifiers. Those are real failures, distinct from the false source-coverage cascades in WeatherBench and monthly calibration."],
    "e7f6e0": ["Correctly computed fold moments, cyclic coefficients, nested whole-year losses/selection, outer predictions and verification. Pooled skill favors independent-month (MSSS 0.24544) over nested cyclic (0.23435), a negative smoothing result the report acknowledges.", "The production constant-slope comparator selects a cyclic candidate instead, yielding up to 34.96910 mm error. Missing units obscure that numerical error in the first checker message.", "A late untested code edit after successful artifact generation/provenance removes a dataset initialization. Replay and target-perturbation commands crash with UnboundLocalError; saved inference also opens absent targets before handling --model. Correct old output files coexist with broken final code."],
    "733b9d": ["Implemented the specified rank mapping and fine climatological ratios with exact spherical geometry, nonnegative rainfall and area/volume conservation relative to calibrated coarse mm.", "Numerical construction and replay, held-year truth perturbation, saved inference and raw positive-affine ×92+7 invariance all pass. The deterministic scientific criteria contribute 75 points.", "Final RMSE 141.63078 mm is worse than climatology 105.87363 (skill −33.77%). This is a valid specified construction with poor predictive performance, not a demonstrated forecast improvement."],
    "04722d": ["Ran 256 temporal-validation configurations and five mixture choices, using an embargo based on label target-end dates. The selected method is an equal mixture of harmonic ridge anomaly calibration and a 20-day circular Gaussian seasonal ridge method, with local/regional raw CFSv2 predictors.", "Used all five development feedback queries; later family searches occurred after earlier feedback, which is allowed and disclosed. Development RMSEs were 11.91462, 11.95526, 12.09270, 12.02345 and 11.87526 mm; query 5's mixture was frozen.", "All delivery/schema/replay/changed-feature/saved-state checks pass. Independent audit reconstructs fitted coefficients/predictions within 1.6×10⁻¹³ and confirms reported weighted CV RMSE 13.22271. Final RMSE 13.89491 improves raw by 6.68% and climatology by 2.71%; no significance or global leaderboard claim follows from this development sample."],
}


def model_info(run_dir, system):
    driver = system["driver"]
    if driver.get("model"):
        return driver["model"], driver.get("effort", driver.get("reasoning_effort", "not recorded"))
    text = read(run_dir / "system/adapter.py")
    match = re.search(r'^MODEL\s*=\s*[\'"]([^\'"]+)', text, re.M)
    effort = re.search(r'(?:model_reasoning_effort|reasoningEffort)[^\n]{0,70}', text)
    # CLI adapters in these frozen systems explicitly set the effort below.
    effort_value = "high" if '"high"' in (effort[0] if effort else "") or "'high'" in (effort[0] if effort else "") else "medium"
    return match[1] if match else "not recorded", effort_value if effort else "not recorded"


def describe_input(path, entry):
    if path.suffix == ".nc":
        import xarray as xr
        with xr.open_dataset(path) as ds:
            dims = "; ".join(f"{k}: {v}" for k, v in ds.sizes.items())
            variables = "<br>".join(f'<code>{esc(k)}</code> ({esc(", ".join(v.dims))}); units: {esc(v.attrs.get("units", "not declared"))}' for k, v in ds.data_vars.items())
            coords = []
            for k, v in ds.coords.items():
                if v.ndim == 1 and v.size:
                    vals = v.values
                    if v.size <= 12:
                        bounds = ", ".join(str(x) for x in vals)
                    else:
                        bounds = f"first {vals[0]}; last {vals[-1]} ({v.size} values)"
                    coords.append(f"{k}: {bounds}")
            return f'<strong>{esc(dims)}</strong><br>{variables}' + details("Coordinates and declared global attributes", pre("\n".join(coords)) + pre(dict(ds.attrs)))
    if path.suffix == ".pdf":
        return "Supplied source/format PDF; open the local file to read it."
    if path.name in {"source-manifest.json", "source-plan.json", "source-audit.json", "candidates.json"}:
        value = load(path)
        return "Structured source/method information." + details("Exact supplied contents", pre(value))
    text = read(path)
    return esc(text.splitlines()[0][:220] if text.splitlines() else "Empty supplied file") + details("Exact supplied text / code", pre(text))


def probe_html(key, value):
    names = {"replay": "Full replay from retained inputs", "prediction": "Saved-state inference", "counterfactual": "Changed inputs / information-isolation probe", "acquisition": "Trusted source acquisition", "integrity": "Run isolation and integrity"}
    if not isinstance(value, dict):
        return esc(value)
    detail = value.get("reason") or value.get("detail") or value.get("probe") or ""
    if len(detail) > 900:
        detail = detail[:900] + " … (full diagnostic below)"
    extra = " ".join(str(value[x]) for x in ("saved_fit_behavior", "probe_limit") if x in value)
    executed = f' · command exit {value["exit_code"]}' if "exit_code" in value else " · no command exit recorded"
    return f'<div class="probe"><h5>{esc(names.get(key, key.replace("_", " ")))}</h5><p>{state(value.get("state", "unresolved"))}{esc(executed)}</p><p>{esc(detail)}</p>' + (f'<p class="muted">{esc(extra)}</p>' if extra else "") + details("Exact controller record", pre(value)) + "</div>"


def history(run_dir, ass):
    records, incomplete = [], []
    for folder in sorted((run_dir / "controller/assessments").iterdir()):
        file = folder / "assessment.json"
        if file.exists():
            old = load(file)
            current = old.get("judge_fingerprint") == ass.get("judge_fingerprint")
            changes = []
            for k, v in old.get("outcomes", {}).items():
                now = ass.get("outcomes", {}).get(k, {})
                if (v.get("state"), v.get("fractional_score")) != (now.get("state"), now.get("fractional_score")):
                    changes.append(f'{k}: {v.get("state")} → {now.get("state")} in displayed assessment')
            records.append([f'<code>{esc(old.get("judge_fingerprint", folder.name)[:16])}…</code>' + ("<br><strong>Displayed assessment</strong>" if current else ""), esc(old.get("judge", "none")), state(old["completion"]), esc("–".join(f"{x:g}" for x in old["score_bounds"])), esc("; ".join(changes) or "Same criterion states as displayed assessment"), link(file, "Assessment") + " · " + link(folder / "evaluation.json", "Execution evidence")])
        elif (folder / "evaluation.json").exists():
            incomplete.append(f'<p><code>{esc(folder.name)}</code>: evaluation saved but no complete assessment in this directory. {link(folder / "evaluation.json", "Preserved evaluation")}</p>')
    return table(["Policy fingerprint", "Expert judge", "Completion", "Bounds / 100", "Difference", "Records"], records) + "".join(incomplete) + '<p class="muted">Policy fingerprints identify configurations, not dates. Directory order is not experimental chronology. The displayed record is the run’s stored assessment.json pointer; all other preserved records remain available.</p>'


def trace_html(run_dir):
    path = run_dir / "logs/events.jsonl"
    if not path.exists():
        return "<p>No tool-event log retained.</p>"
    events = [json.loads(x) for x in read(path).splitlines() if x.strip()]
    rows, stops = [], []
    for index, event in enumerate(events):
        kind = event.get("type")
        if kind == "tool_result":
            label = event.get("command") or event.get("url") or event.get("destination") or event.get("name") or event.get("tool") or "Tool response"
            detail = {k: event[k] for k in ("command", "url", "destination", "exit_code", "seconds", "truncated", "state", "status", "error") if k in event}
            for k in ("stdout", "stderr"):
                if event.get(k):
                    text = str(event[k])
                    detail[k] = text[:1800] + ("\n[Display excerpt; full response is in the retained trace.]" if len(text) > 1800 else "")
            command = str(label)
            # Full commands are already available in the trace. Display manageable
            # excerpts of long heredoc scripts without concealing that truncation.
            if len(str(detail.get("command", ""))) > 2400:
                detail["command"] = detail["command"][:2400] + "\n[Display excerpt; complete command is in the retained trace.]"
            rows.append([esc(index), esc(command.splitlines()[0][:200]), esc(event.get("exit_code", event.get("status", "not recorded"))), details("Command and response excerpt", pre(detail))])
        elif kind == "stop":
            stops.append(pre(event))
    return f'<p>Event numbers below are zero-based positions in {link(path, "the immutable tool-event trace")}. These are tool responses in execution order, not a reconstruction of hidden reasoning. Commands and outputs are displayed as inert text; long entries are explicitly excerpted.</p>' + table(["Event", "Action", "Exit / status", "Detail"], rows) + ("<h5>Recorded termination</h5>" + "".join(stops) if stops else "")


def audit_html(run_id, audits):
    entries = audits.get(run_id, [])
    content = ""
    for path, findings in entries:
        content += f'<p>{link(path, "Original post-run audit")}. These are provisional curator/code-review observations, not an issued expert grade.</p>'
        for item in findings:
            if isinstance(item, str):
                content += "<p>" + esc(item) + "</p>"
                continue
            text = item.get("claim", item.get("conclusion", item.get("summary", item.get("diagnostic", ""))))
            label = item.get("provisional_label", item.get("classification", "development observation"))
            content += f'<div class="finding"><strong>{esc(item.get("id", label))}</strong> <span class="muted">{esc(label.replace("_", " "))}</span><p>{esc(text)}</p>'
            evidence = []
            for ref in item.get("evidence", []):
                if isinstance(ref, dict):
                    target = Path(ref.get("path", ""))
                    evidence.append(link(target, str(target)) + (" · lines " + esc(ref["lines"]) if ref.get("lines") else ""))
                else:
                    evidence.append(esc(ref))
            content += ("<p class=\"muted\">" + "<br>".join(evidence) + "</p>" if evidence else "")
            limit = item.get("limit", item.get("limitation"))
            if limit:
                content += f'<p class="muted">Limit: {esc(limit)}</p>'
            content += "</div>"
    return details("Post-run audit: claims, code/trace citations and limitations", content) if content else ""


def helper_html(run_id):
    pairs = HELPER_REVIEWS.get(run_id, [])
    if not pairs:
        return ""
    rows = []
    for item in pairs:
        a, b = item["a"], item["b"]
        reasons = ""
        for label, rating in (("Reviewer A", a), ("Reviewer B", b)):
            reasons += f'<strong>{label}</strong><p>{esc(rating.get("reason", ""))}</p><p class="muted">Uncertainty: {esc(rating.get("uncertainty", "not separately recorded"))}</p>'
            reasons += '<p class="muted">Citations: ' + esc("; ".join(str(x) for x in rating.get("evidence", []))) + '</p>'
        rows.append([esc(item["criterion"]), esc("unresolved" if a.get("score") is None else a["score"]), esc("unresolved" if b.get("score") is None else b["score"]), details("Both original reasons, uncertainty and citations", reasons), link(item["source"], "Comparison")])
    return '<h5>Additional local reviewer exercise — separate from the score above</h5><p class="muted">These fresh-context helper reviews used bounded evidence packets and a 0/1/2 rating scale. A null rating is unresolved. They were not the locked native model judge, did not create human gold labels, and were not applied to the displayed 0–100 assessment. Some partial/negative ratings concern evidence omitted from the packet rather than missing from the submission.</p>' + table(["Criterion", "Reviewer A / 2", "Reviewer B / 2", "Reasoning", "Original record"], rows)


def render_run(row, rubric, ordinal, audits, checks):
    run_dir = ROOT / "var/runs" / row["run"]
    run = load(run_dir / "run.json")
    system = load(run_dir / "system.json")
    request = load(run_dir / "request.json")
    ass = load(run_dir / "assessment.json")
    evpath = Path(ass["assessment_directory"]) / "evaluation.json"
    ev = load(evpath)
    inventory = load(run_dir / "artifacts.json")
    model, effort = model_info(run_dir, system)
    suffix = run["id"].rsplit("-", 1)[-1]
    trial = suffix == "68489d"
    bounds = ass["score_bounds"]
    lower = sum(x["weight"] * (x["fractional_score"] or 0) * 100 for x in ass["outcomes"].values())
    upper = lower + sum(x["weight"] * 100 for x in ass["outcomes"].values() if x["fractional_score"] is None)
    assert abs(lower - bounds[0]) < 1e-7 and abs(upper - bounds[1]) < 1e-7, run["id"]
    hashes_ok = all((run_dir / "frozen" / key).is_file() and digest(run_dir / "frozen" / key) == value["sha256"] for key, value in inventory.items())
    assert hashes_ok, run["id"]
    core_match = all(digest(run_dir / "task" / f) == digest(ROOT / "tasks" / run["task"] / f) for f in CORE)
    assert core_match, run["id"]
    checks.append({"run": run["id"], "task": run["task"], "framework_trial": trial, "score_bounds_verified": bounds, "frozen_artifact_hashes_verified": len(inventory), "current_task_core_matches_frozen": core_match})
    h = f'<article class="attempt" id="run-{esc(suffix)}"><div class="run-heading"><h4>{"Framework trial" if trial else "Attempt " + str(ordinal)} · {esc(model)}</h4><a href="#task-{esc(run["task"])}">Task ↑</a></div>'
    h += f'<p class="mono run-id">{esc(run["id"])}</p><div class="chips"><span>Solver status: <strong>{esc(run["status"])}</strong></span><span>Recorded time: <strong>{run["seconds"]:.1f}s</strong></span><span><strong>{run.get("tool_calls", "?")}</strong> tools</span><span>Task <strong>{esc(run["task_version"])}</strong></span><span>Reasoning: <strong>{esc(effort)}</strong></span></div>'
    h += "<h5>What this attempt did</h5>" + bullets(RUN_NOTES[suffix])
    budget = system["budget"]
    driver = system["driver"]
    context = f'<p>{esc(system.get("description", ""))}</p><p>Configured allowance: {esc(budget.get("max_seconds"))} seconds total; {esc(budget.get("max_tool_calls"))} tool calls; {esc(budget.get("command_seconds"))} seconds per command. Runtime: {esc(system["runtime"].get("cpus"))} CPUs, {esc(system["runtime"].get("memory"))} RAM, offline pinned container.</p>'
    if driver.get("model"):
        provider = {k: driver[k] for k in ("kind", "model", "effort", "reasoning_effort", "max_usd", "max_output_tokens", "max_total_tokens", "max_turns", "response_timeout_seconds", "input_usd_per_million", "output_usd_per_million") if k in driver}
        context += pre(provider)
        spend = 12.75141 if suffix == "c5d9e0" else 6.65883
        context += f'<p>Separately billed provider spend: <strong>${spend:.5f}</strong>. These two calls account for the pilot total $19.41024; no new paid calls were made to build this report.</p>'
    else:
        context += '<p>Codex CLI through ChatGPT subscription authentication; separately billed API spend recorded as $0. Allocated subscription cost is unknown. Token counts below are usage, not an actual API invoice.</p>'
    context += '<p>Usage categories overlap: cached input is a subset of input, and reasoning output is a subset of output. Do not add every column.</p>' + pre(run.get("usage", {}))
    context += '<p>Launch policy fingerprint: <code>' + esc(run.get("launch_policy_fingerprint", "Not recorded in this early run")) + '</code>. Parent/prior: ' + esc(run.get("parent")) + '; retained files supplied at start: ' + esc(len(request.get("retained_files", {}))) + ".</p>"
    context += link(run_dir / "system.json", "Frozen system settings") + " · " + link(run_dir / "request.json", "Exact start request")
    h += details("Model settings, budgets, token accounting and starting state", context)
    h += '<h5>How the recorded assessment scored it</h5><p>' + state(ass["completion"]) + f' · <strong>{bounds[0]:g}–{bounds[1]:g} / 100</strong> · expert judge: <strong>{esc(ass["judge"])}</strong></p>'
    h += '<p class="muted">Lower bound is awarded known credit; upper bound includes still-unresolved credit. A range is not a final grade or confidence interval. Failed unweighted validity can prevent completion even with substantial known scientific credit.</p>'
    score_rows = []
    for leaf in leaves(rubric["tree"]):
        v = ass["outcomes"][leaf["id"]]
        weight = v["weight"] * 100
        frac = v["fractional_score"]
        credit = f"0–{weight:g}" if frac is None else f"{frac * weight:g}"
        rationale = []
        for check in leaf.get("checks", []):
            cv = ev["static"]["check_results"].get(check, {})
            rationale.append(f'{check}: {cv.get("state", "not separately recorded")}')
        if frac is None:
            rationale.append("Expert/reviewer evidence has not been graded by the native judge")
        elif v["state"] == "fail" and not rationale:
            rationale.append("Required execution or leaf evidence fails; see checks/probes below")
        score_rows.append([f'<strong>{esc(leaf["id"])}</strong><br><span class="muted">{esc(leaf["evaluator"])}</span>', f"{weight:g}", state(v["state"]), "Unresolved" if frac is None else f"{frac:g}", credit, esc("; ".join(rationale))])
    h += table(["Criterion", "Weight", "State", "Credit fraction", "Points", "Recorded basis / unresolved work"], score_rows)
    check_rows = []
    for key, value in ev["static"]["check_results"].items():
        check_rows.append([f'<code>{esc(key)}</code>', state(value.get("state", "unresolved")), esc(value.get("detail", "") or "No separate detail string; see criterion/check evidence"), esc(", ".join(str(x) for x in value.get("evidence", [])))])
    h += '<h5>Individual static checks, including unweighted delivery requirements</h5>' + table(["Check", "Result", "Actual diagnostic", "Evidence named by checker"], check_rows)
    h += '<h5>Executed probes and information boundary</h5><div class="probes">' + "".join(probe_html(k, v) for k, v in ev.items() if k not in {"static", "forecast_outcomes", "feedback"}) + '</div>'
    if ev.get("forecast_outcomes"):
        h += '<h5>Forecast performance, reported separately from completion</h5>' + pre(ev["forecast_outcomes"]) + '<p class="muted">Private to the solver during the attempt does not mean untouched during benchmark development. These retained development evaluations do not establish significance or a leaderboard ranking.</p>'
    if ev.get("feedback"):
        ledger = ev["feedback"]
        feedback_rows = [[esc(v.get("query")), esc(v.get("status")), esc(v.get("metrics", {}).get("rmse_mm", "not scored")), esc(v.get("prediction_sha256", "")), link(run_dir / "controller/feedback-public.json", "Public feedback record")] for v in ledger.get("requests", [])]
        h += '<h5>Development feedback actually returned to the agent</h5>' + table(["Query", "Status", "RMSE mm", "Frozen queried-file SHA-256", "Record"], feedback_rows) + '<p class="muted">Final target labels and final scores were not exposed during the attempt.</p>'
    overlay_path = ROOT / "var/calibration/overnight-static-diagnostics" / (run["id"] + ".json")
    if overlay_path.exists():
        overlay = load(overlay_path)
        diff_rows = []
        current = overlay.get("static", {}).get("check_results", {})
        for key, value in current.items():
            old = ev["static"]["check_results"].get(key, {})
            if old.get("state") != value.get("state"):
                diff_rows.append([esc(key), state(old.get("state", "unresolved")), state(value.get("state", "unresolved")), esc(value.get("detail", ""))])
        h += '<h5>Later diagnostic overlay — no new executed score</h5><p>The later static-only policy <code>' + OVERLAY_POLICY[:16] + '…</code> was applied to the same frozen files. Docker replay and model judging were not rerun; the score table above remains the preserved executed assessment.</p>'
        h += table(["Changed static check", "Executed assessment", "Later diagnostic", "Detail"], diff_rows) if diff_rows else '<p>No static check states differ from the displayed executed assessment.</p>'
        h += link(overlay_path, "Full diagnostic overlay, including bounded array differences")
    h += audit_html(run["id"], audits)
    h += helper_html(run["id"])
    output_rows = [[link(run_dir / "frozen" / key, key), f'{value["bytes"]:,}', f'<code>{value["sha256"][:16]}…</code>'] for key, value in inventory.items()]
    output_content = table(["Frozen deliverable", "Bytes", "SHA-256"], output_rows)
    for key in inventory:
        if key.endswith("outlook.png"):
            file = run_dir / "frozen" / key
            href = "../../" + quote(str(file.relative_to(ROOT)), safe="/")
            output_content += f'<p>Exact figure produced by this attempt:</p><img class="model-figure" src="{href}" loading="lazy" alt="Model-authored outlook figure for {esc(run["id"])}">'
    for name in ["answer.json", "report.txt", "handoff.txt", "execution.json"]:
        file = run_dir / "frozen" / name
        if file.exists():
            text = read(file)
            output_content += details("Exact model-authored " + name, pre(text))
    h += details(f"What it handed in: {len(inventory)} verified frozen files; full answer, report and handoff", output_content)
    h += details("Tool-by-tool record of this attempt", trace_html(run_dir))
    h += '<h5>Assessment versions preserved for this same frozen attempt</h5>' + history(run_dir, ass)
    h += '<p class="muted">All frozen deliverable hashes verified for this report. Current task.yaml, prompt.md, rubric.yaml, input-manifest.json and sources.yaml match this run’s frozen copies. Launch fingerprint absence in early runs is disclosed, not reconstructed.</p>'
    h += '<p>' + link(run_dir / "assessment.json", "Displayed assessment JSON") + " · " + link(evpath, "Executed evaluation JSON") + " · " + link(run_dir / "artifacts.json", "Complete retained inventory") + "</p></article>"
    return h


def render_task(task_id, rows, audits, checks):
    note = TASKS[task_id]
    canonical = ROOT / "var/runs" / rows[0]["run"]
    taskdir = canonical / "task"
    request = load(canonical / "request.json")
    task = yaml.safe_load(read(taskdir / "task.yaml"))
    rubric = yaml.safe_load(read(taskdir / "rubric.yaml"))
    sources = yaml.safe_load(read(taskdir / "sources.yaml"))
    inventory = load(canonical / "input-manifest.json")
    h = f'<section class="task" id="task-{esc(task_id)}"><div class="task-heading"><p class="eyebrow">{esc(task.get("track", "forecasting workflow").replace("_", " "))} · {esc(task["version"])}</p><h2>{esc(note["title"])}</h2><p class="lead">{esc(note["objective"])}</p></div>'
    jump_rows = []
    for row in rows:
        rd = ROOT / "var/runs" / row["run"]
        record = load(rd / "run.json")
        assessment = load(rd / "assessment.json")
        suffix = record["id"].rsplit("-", 1)[-1]
        label = record["system"] + (" · adapter trial" if suffix == "68489d" else "")
        jump_rows.append([f'<a href="#run-{esc(suffix)}">{esc(label)} · {esc(suffix)}</a>', esc(record["status"]), state(assessment["completion"]), esc("–".join(f"{x:g}" for x in assessment["score_bounds"]))])
    h += table(["Jump to an attempt", "Solver status", "Recorded completion", "Score bounds / 100"], jump_rows)
    h += '<h3>1. What is given to the agent</h3>' + bullets(note["given"])
    h += '<p class="boundary"><strong>Controller-only material:</strong> ' + esc(note["private"]) + '</p>'
    h += '<p>These are the actual initial files from the frozen run, not the package’s hypothetical complete inventory. Runs on this task share initial file hashes; any system-specific substrate is shown separately.</p>'
    inrows = []
    for name, entry in inventory.items():
        path = canonical / "inputs" / name
        assert path.exists() and digest(path) == entry["sha256"]
        tracked(path)
        inrows.append([link(path, name), f'{entry["bytes"]:,}', describe_input(path, entry)])
    h += table(["Initial supplied file", "Bytes", "Contents / assistance"], inrows)
    for row in rows[1:]:
        other = load(ROOT / "var/runs" / row["run"] / "input-manifest.json")
        assert other == inventory, (task_id, row["run"])
    substrate_seen = set()
    for row in rows:
        rd = ROOT / "var/runs" / row["run"]
        rq = load(rd / "request.json")
        assert rq["prompt"] == request["prompt"] and rq["contracts"] == request["contracts"]
        for file in sorted((rd / "system").rglob("*")):
            if not file.is_file() or file.name == "adapter.py" or file.suffix not in {".txt", ".md", ".json"}:
                continue
            sha = digest(file)
            if sha not in substrate_seen:
                substrate_seen.add(sha)
                h += details("Also supplied in system substrate: " + str(file.relative_to(rd / "system")), pre(read(file)))
        instr = rq.get("substrate_instructions", "")
        if instr and hashlib.sha256(instr.encode()).hexdigest() not in substrate_seen:
            substrate_seen.add(hashlib.sha256(instr.encode()).hexdigest())
            h += details("Additional system instructions", pre(instr))
    if task_id == "seasonal-calibration":
        acq = request.get("acquisition", {})
        h += details("Exact source-acquisition capabilities / allowed requests", pre(acq))
    paths = request["paths"]
    h += '<p><strong>Environment:</strong> initial inputs at <code>' + esc(paths["inputs"]) + '</code>; outputs at <code>' + esc(paths["submission"]) + '</code>; frozen task at <code>/task</code>; supplied system material at <code>' + esc(paths["substrate"]) + '</code>. The trusted adapter exposes container execute' + (", acquire" if task_id == "seasonal-calibration" else "") + (", score_development" if task_id == "subseasonal-optimization" else "") + '. Solver containers have no network, private-reference or credential mounts. CPU/RAM and time allowances are listed per attempt.</p>'
    h += details("Exact task instructions received at launch", markdown(request["prompt"]))
    for key, text in request["contracts"].items():
        h += details("Exact supplied " + key + " contract", markdown(text))
    source_rows = []
    for item in sources.get("sources", []):
        locator = str(item.get("locator", ""))
        loc = f'<a href="{esc(locator)}">{esc(locator)}</a>' if locator.startswith(("https://", "http://")) else esc(locator)
        source_rows.append([esc(item.get("id")), esc(item.get("kind", "")), esc(item.get("title", item.get("role", ""))), loc + ("<br>Revision: <code>" + esc(item["revision"]) + "</code>" if item.get("revision") else ""), esc(item.get("role", item.get("snapshot_policy", "")))])
    h += details("Pinned source records and what this task borrows from them", table(["Source ID", "Kind", "Title / purpose", "Locator / revision", "Role"], source_rows) + '<p class="muted">A source record is a citation and pin, not evidence that the entire paper or repository was in the solver context. The initial/substrate inventories above establish what was supplied.</p>' + link(taskdir / "sources.yaml", "Complete frozen source record"))
    h += '<h3>2. What the evaluator is checking</h3><p>' + esc(note["evaluate"]) + '</p>'
    rubric_rows = []
    for leaf in leaves(rubric["tree"]):
        rubric_rows.append([f'<strong>{esc(leaf["id"])}</strong><br>{esc(leaf.get("weight", ""))} points · {esc(leaf["evaluator"])}', esc(leaf["criterion"]), esc(", ".join(leaf.get("checks", [])) or "No isolated static check list; see trusted execution / expert evidence"), esc(", ".join(leaf.get("evidence", [])))])
    h += table(["Criterion and weight", "Exact frozen criterion", "Named checks", "Required evidence"], rubric_rows)
    h += '<p><strong>Unweighted validity/integrity:</strong> ' + esc(rubric.get("basic_validity", {}).get("checks", [])) + '. ' + esc(rubric.get("basic_validity", {}).get("integrity", "Trusted runtime boundaries and retained artifacts are checked independently.")) + '</p>'
    h += '<p>' + link(taskdir / "rubric.yaml", "Exact frozen rubric") + " · " + link(ROOT / "tasks" / task_id / "review.html", "Task author’s specification/review page") + '</p>'
    h += '<h3>3. Actual model attempts and their recorded results</h3>'
    ordinal = 0
    for row in rows:
        if not row["run"].endswith("68489d"):
            ordinal += 1
        h += render_run(row, rubric, ordinal, audits, checks)
    h += '<h3>4. What changed, and what that changes about interpretation</h3>' + bullets(note["changes"]) + '<p><a href="#contents">Back to task list ↑</a></p></section>'
    return h


def gather_audits():
    audits = defaultdict(list)
    for filename in ("overnight-solver-audit.json", "overnight-final-task-audit.json"):
        path = ROOT / "var/calibration" / filename
        for run in load(path)["runs"]:
            audits[run["id"]].append((path, run.get("findings", [])))
    path = ROOT / "var/calibration/overnight-astra-optimization-audit.json"
    d = load(path)
    audits[d["run"]].append((path, d["findings"]))
    for filename, key in (("acmad-natural-cohort.json", "records"), ("wvg-natural-cohort.json", "runs"), ("seasonal-natural-cohort.json", "attempts")):
        path = ROOT / "var/calibration" / filename
        for run in load(path)[key]:
            findings = run.get("scientific_findings", [])
            if run.get("development_review"):
                findings = [run["development_review"]]
            if run.get("source_interpretation_review"):
                review = run["source_interpretation_review"]
                findings = [{"summary": review.get("concern", review.get("other_claims", "")), "classification": review.get("status", "source_review"), "evidence": run.get("source_read_evidence", [])}]
                # Source-read records are command metadata, not file citations.
                findings[0]["evidence"] = ["Source-read evidence retained in the linked cohort JSON."]
                if run.get("replay_diagnosis"):
                    findings.append(run["replay_diagnosis"])
            audits[run["run"]].append((path, findings))
    return audits


def gather_helpers():
    path = ROOT / "var/calibration/judge-local-review/disagreements.json"
    comparison = load(path)
    for case in comparison["cases"]:
        mapping = load(ROOT / "var/calibration/judge-expanded" / case["case"] / "source-map.json")
        if not mapping.get("natural_attempt"):
            continue
        origin = Path(mapping["source_directory"])
        if "judge-pilot" in origin.parts:
            origin = Path(load(origin / "source-map.json")["source_directory"])
        for criterion in case["criteria"]:
            HELPER_REVIEWS[origin.name].append({"criterion": criterion["criterion"], "a": criterion["ratings"]["reviewer-a"], "b": criterion["ratings"]["reviewer-b"], "source": path})
    path = ROOT / "var/calibration/judge-new-parent-review/comparison.json"
    comparison = load(path)
    mapping = load(ROOT / "var/calibration/judge-new-parent-check/private-map.json")
    for criterion in comparison["comparisons"]:
        HELPER_REVIEWS[mapping[criterion["case"]]].append({**criterion, "source": path})


CSS = """
:root{--ink:#213c43;--muted:#526a70;--paper:#f6f5ef;--line:#d7ddd8;--accent:#236c61}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:25px}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.65 system-ui,-apple-system,sans-serif}main{max-width:1220px;margin:auto;padding:28px 28px 80px}a{color:var(--accent);text-underline-offset:3px;overflow-wrap:anywhere}a:focus-visible,summary:focus-visible,button:focus-visible{outline:3px solid #bb791d;outline-offset:3px}header{display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px;font-size:14px;border-bottom:1px solid var(--line);padding:10px 0 20px}h1{font:400 clamp(34px,5vw,53px)/1.15 Georgia,serif;margin:32px 0 22px}h2{font:400 34px/1.22 Georgia,serif;margin:10px 0 16px}h3{font-size:22px;margin:35px 0 16px}h4{font-size:23px;margin:0}h5{font-size:17px;margin:24px 0 8px}p{margin:12px 0}.lead{font-size:19px;max-width:1000px}.muted{color:var(--muted);font-size:13px}.mono,code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}code{font-size:.87em;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f3ef;border:1px solid var(--line);border-radius:4px;font-size:12px;line-height:1.6;padding:16px;max-height:620px;overflow:auto}.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.8px;color:var(--muted)}.chips{display:flex;gap:8px;flex-wrap:wrap;font-size:13px}.chips span{padding:6px 10px;background:#eef2ed;border:1px solid var(--line);border-radius:4px}.callout,.boundary{padding:15px 20px;border-left:3px solid var(--accent);background:#eaf0e9}.toc{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.toc a{display:block;text-decoration:none;border:1px solid var(--line);background:#fffefa;padding:14px 16px;border-radius:6px}.toc a strong{display:block}.toc a span{color:var(--muted);font-size:13px}.task{border-top:3px solid var(--accent);padding-top:25px;margin-top:65px}.task-heading{margin-bottom:20px}.attempt{background:#fffefa;border:1px solid var(--line);border-radius:8px;margin:24px 0;padding:24px}.run-heading{display:flex;justify-content:space-between;gap:12px;align-items:baseline}.run-heading a{font-size:13px}.run-id{font-size:12px;overflow-wrap:anywhere}.table-scroll{overflow:auto;border:1px solid var(--line);border-radius:5px;margin:16px 0;max-width:100%}table{border-collapse:collapse;width:100%;font-size:13px;min-width:700px}th,td{text-align:left;vertical-align:top;padding:12px 13px;border-bottom:1px solid var(--line);overflow-wrap:anywhere}th{background:#edf1eb;font-size:12px}td:first-child{max-width:230px}tr:last-child td{border-bottom:0}details{margin:13px 0;padding:13px 16px;border:1px solid var(--line);border-radius:5px;background:#fffefa}summary{cursor:pointer;color:var(--accent);font-size:14px;font-weight:600}summary:hover{text-decoration:underline}details h2,details h3{font-family:inherit;font-size:19px}details h4,details h5{font-size:16px}.state{display:inline-block;border-radius:3px;padding:2px 7px;font-size:12px;border:1px solid var(--line);white-space:nowrap}.pass{background:#e3eee4;color:#235b35}.fail,.failed{background:#f6e8e2;color:#8a3c24}.unresolved,.pending{background:#f5efda;color:#77591c}.partial{background:#e5eef3;color:#34566a}.not_applicable{background:#eff0eb;color:#626c60}.probes{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.probe{border:1px solid var(--line);padding:5px 16px 12px;border-radius:5px;min-width:0}.probe p{font-size:13px}.probe h5{margin:12px 0}.finding{border-left:2px solid var(--line);padding-left:16px;margin:20px 0}.finding p{font-size:14px}li{margin:8px 0}footer{border-top:1px solid var(--line);padding-top:22px;margin-top:40px;font-size:13px;color:var(--muted)}button{font:inherit;color:var(--accent);background:#fffefa;border:1px solid var(--line);padding:7px 12px;border-radius:4px;cursor:pointer}.print-controls{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}@media(max-width:700px){main{padding:16px 14px 45px}.toc,.probes{grid-template-columns:1fr}.attempt{padding:17px 12px}h2{font-size:28px}h3{font-size:20px}h4{font-size:20px}.lead{font-size:17px}th,td{padding:10px}.task{margin-top:45px}}@media print{body{background:white}main{max-width:none;padding:0}.print-controls,header{display:none}.task{break-before:page}.attempt{break-inside:auto}.table-scroll{overflow:visible}table{min-width:0}pre{max-height:none}.probes{grid-template-columns:1fr}.toc{display:block}.toc a{border:0;padding:5px}}
"""


def main():
    initial = load(ROOT / "var/calibration/task-audit-summary.json")
    overnight = load(ROOT / "var/calibration/overnight-audit-summary.json")
    rows = initial["runs"] + overnight["run_results"]
    assert len(rows) == 21 and len({row["run"] for row in rows}) == 21
    by_task = defaultdict(list)
    for row in rows:
        by_task[row["task"]].append(row)
    assert set(by_task) == set(TASKS)
    audits = gather_audits()
    gather_helpers()
    checks = []
    sections = "".join(render_task(task_id, by_task[task_id], audits, checks) for task_id in TASKS)
    nav = ""
    for task_id, note in TASKS.items():
        attempts = len(by_task[task_id]) - (1 if task_id == "acmad-objective" else 0)
        systems = ", ".join(dict.fromkeys(x["system"] for x in by_task[task_id]))
        nav += f'<a href="#task-{esc(task_id)}"><strong>{esc(note["title"])}</strong><span>{attempts} solver attempt{"s" if attempts != 1 else ""}{" + 1 adapter trial" if task_id == "acmad-objective" else ""} · {esc(systems)}</span></a>'
    page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Agent Weather Bench · Tasks, attempts and judgments</title><style>' + CSS + '.model-figure{display:block;width:100%;height:auto;border:1px solid var(--line);margin:18px 0}</style></head><body><main><header><strong>Agent Weather Bench · Development record</strong><nav><a href="#contents">All 10 tasks</a> · <a href="#reading-scores">How scores work</a> · <a href="index.html">Separate calibration review form</a></nav></header>'
    page += '<h1>What the agents were asked to do,<br>what they did, and how it was assessed.</h1><p class="lead">A task-by-task account of the retained October 5 development experiments. Each task shows the actual supplied material, exact rubric, every attempt’s scientific and delivery results, and changes to evaluation or artifacts.</p><div class="chips"><span><strong>10</strong> tasks</span><span><strong>20</strong> solver attempts</span><span><strong>1</strong> separate adapter trial</span><span><strong>0</strong> native model-judge calls</span><span><strong>0</strong> human gold labels</span></div>'
    page += '<p class="muted">No new models, submitted code, dataset downloads or Docker probes were run to build this report. The existing note-taking review page is preserved. Exact source/code/report text is available in expandable panels; key checks and score breakdowns are visible by default.</p>'
    page += '<div class="callout"><strong>What this document is for</strong><p>Choose a task below and read in order: supplied inputs → evaluation contract → actual attempts → changes. You can compare the model’s own report with the individual checker/probe results. You do not need to infer its work from one composite score or approve every run.</p></div>'
    page += '<h2 id="contents">The tasks and attempts</h2><nav class="toc">' + nav + '</nav>'
    page += '<h2 id="reading-scores">How to read the judgments</h2><p>Every displayed assessment used <code>judge=none</code>. Numerical checks and trusted execution ran; the locked native model judge did not. Some local helper models reviewed selected criteria later, as calibration exercises. Those are provisional evidence reviews, not official expert grades and not human-approved gold labels.</p>'
    page += '<p>A passed deterministic criterion receives its full weight; a known failure receives zero; an unresolved criterion can still contribute between zero and its full weight. For example, the subseasonal attempt’s <strong>25–100</strong> means 25 known schema points and 75 still awaiting expert/reviewer evidence. It does not mean a model received a final grade of 25. Several execution or mixed criteria remain unresolved even when their probes pass because the aggregator also expects a reviewer rating.</p>'
    page += '<p>Completion also depends on unweighted delivery, provenance and integrity. An attempt can have correct scientific arrays but failed delivery, and a replay can reproduce scientifically wrong arrays. Forecast skill is reported separately from reproducing a specified method. The report preserves all three distinctions.</p>'
    page += '<p>The tasks, model budgets and number of repeats differ. All attempts are development studies with pending task/scoring approvals, not an official model ranking or a demonstrated frontier ceiling. “Private final” describes the solver’s information boundary; the historical targets were inspected in development.</p>'
    page += '<div class="print-controls"><button type="button" id="expand">Expand all exact evidence</button><button type="button" id="collapse">Collapse exact evidence</button><button type="button" id="print">Print / save PDF</button></div>'
    page += sections
    page += '<section class="task" id="judge-development"><h2>Separate judge-calibration work</h2><p>The task records above are actual solver attempts. Constructed wrong solutions and controlled copies were also used to test evaluation sensitivity; they are not additional natural model attempts. Local reviewers sometimes disagreed about partial credit, and omission of relevant source/trace evidence caused unsupported negative ratings. Reviewer agreement alone does not establish correctness.</p><p>The <a href="index.html">six-case calibration form</a> is for reviewing specific rubric/evidence-policy choices. It is optional and separate from understanding what happened in these runs. No native paid judge was called: exporting the artifact packets to that external service remained unapproved. No human reference labels have been collected.</p>'
    page += '<p>Original local comparisons: ' + link(ROOT / 'var/calibration/judge-local-review/disagreements.json', 'Original selected-criterion comparison') + ' · ' + link(ROOT / 'var/calibration/judge-new-parent-review/comparison.json', 'CCA/subseasonal selected-criterion comparison') + '. Criteria from these helper exercises do not replace any score shown above.</p></section>'
    page += '<footer><p>Generated from frozen requests, tasks, initial inventories, system settings, retained artifacts, tool events and stored assessments. File hashes and score-bound arithmetic were verified for all 21 records. The same core task files are still current for all records; earlier launch fingerprints remain unrecorded where absent.</p><p>Source manifest: <a href="task-runs.sources.json">task-runs.sources.json</a>. Regenerate with <code>.venv/bin/python scripts/build_task_runbook.py</code>. Existing overview: <a href="findings.html">findings.html</a>.</p></footer></main><script>document.getElementById("expand").onclick=()=>document.querySelectorAll("details").forEach(e=>e.open=true);document.getElementById("collapse").onclick=()=>document.querySelectorAll("details").forEach(e=>e.open=false);document.getElementById("print").onclick=()=>window.print();</script></body></html>'
    tracked(Path(__file__))
    OUT.write_text(page)
    manifest = {"schema_version": 1, "kind": "task_by_task_development_runbook", "task_count": 10, "solver_attempts": 20, "framework_failure_trials": 1, "new_model_calls": 0, "submitted_code_executed": False, "new_execution_probes": 0, "html_sha256": digest(OUT), "bytes": OUT.stat().st_size, "verified_runs": checks, "sources_sha256": dict(sorted(SOURCE_FILES.items()))}
    OUT.with_suffix('.sources.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({"html": str(OUT), "bytes": OUT.stat().st_size, "tasks": 10, "runs": len(checks), "source_files": len(SOURCE_FILES), "new_model_calls": 0}))


if __name__ == "__main__":
    main()
