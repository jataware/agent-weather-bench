# The WMO objective seasonal forecasting checklist is a draft standard

Status: draft. No domain scientist has reviewed it, and it has not been checked
against the primary document.

## The folder holds one standard for process-mode templates

Process-mode templates (parameterised tasks whose Level 1 requires a published
method) ask an agent to follow a published standard, and the
controller (the trusted evaluator in `assessment/`) checks each required step. This folder holds the standard's
practices and the checklist that turns them into testable steps. One checklist
serves every template that names the same standard.

## The checklist rests on a secondary source

- **The primary document was not obtained.** It is the *Guidance on Operational
  Practices for Objective Seasonal Forecasting*, WMO-No. 1246 (2020). The WMO
  library did not serve the file to an automated request on 6 October 2026.
- **The practices come from a WMO Secretariat presentation.** `practices.md`
  quotes its nine-point definition of an objective seasonal forecast.
  `sources.json` gives its address and the hash of the copy kept under
  `var/private/standards/`.
- **The checklist is our interpretation.** `checklist.yaml` maps each practice
  to steps that can be tested on one calibration task, and lists the practices
  that cannot. The wording of every step is ours, not the WMO's.

## Two things must happen before the checklist counts for a result

1. Obtain WMO-No. 1246 and the long-range verification standard, and keep
   hashed copies.
2. Replace each step's `practice` number with the clause it comes from.
3. Add steps the primary document requires and this draft lacks.
4. Have a domain scientist sign off the checklist.

## The folder contains these files

- `practices.md` — the nine practices, quoted.
- `checklist.yaml` — the draft steps and the practices judged not testable.
- `sources.json` — what was and was not obtained.
