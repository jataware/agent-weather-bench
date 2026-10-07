# Critique: Validate and save a seasonal rainfall calibration

Task: seasonal-calibration (review-0.1)
Reviewer: zeek
Recommendation: Needs discussion
Updated: 2026-10-02T10:02:07.471Z
Source fingerprint: caa132fa8f16a2f7a0c31d0f03cf890b9de6843c4011ad83314b6192331d693d

These are review notes, not approval or benchmark results.

## Main changes

needs to actually get and download the data, full workflow seems very natural to have. this would be a logistical nightmare to have to supply all this data. also forcing so explicitly the system to write python code may limit the ability of the system to make use of certain cli-style skills that force the agent to operate in certan ways. Otherwise it seems like a good topic. Not totally sure that's required but yeah, shoudl consider that.

Also the rubric is a little redundant? feel like some of these could be a little synthesized between them.

## Rubric feedback

### provenance

Current criterion: Sources, hashes, scientific processing and stated assumptions are traceable and accurate.

Criterion: Revise

Reason / proposed wording: this seems vague to me? Should have some standard i guess.

### development_metrics

Current criterion: Reported development scores, baseline and reliability diagnostic are independently recomputable with the correct fold-specific targets.

Reason / proposed wording: this sort of thing is good.

## Source hashes

```json
{
  "task.yaml": "72bfd6a2148e7797e64231638f9f3321257c5359dcf9e6d1d69f40ab1515a370",
  "prompt.md": "903b95d653a9e16862a9f721bf1268dbd0e2cb515fd8cc779add64d3f7adc461",
  "rubric.yaml": "5d24ee756aa3cff43ee6e09a0c750508428997a33093ff29a2caaa39642e7664",
  "sources.yaml": "8c06c69b4e91a42d80c2b622811d290da795d355a033bf841d4c8a32bdcefff0",
  "review.md": "fef47bcb8e86370fb1088ac9283f60397825f1a147a93d6c1b9d8f600ac8b83e",
  "input-manifest.json": "ffdeb766b585943b7566ee16a5cfb441532e34928b6fadffb84c5060add235b6"
}
```
