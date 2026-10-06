"""Variant matching: which readings of the brief is a set of results consistent with?

A numerical match supports a diagnosis; it does not prove one. The functions here
therefore report sets of combinations, and leave separating them to the probes.
"""
from .compare import compare
from .outcomes import FAIL, PASS, UNRESOLVED, outcome


def _reference(template, inputs, params, combination, given=None):
    """One reference. `given` carries the submission's free results, for quantities derived from them."""
    if getattr(template.hooks, "REFERENCE_USES_SUBMISSION", False):
        return template.hooks.reference(inputs, params, combination, given)
    return template.hooks.reference(inputs, params, combination)


def table(template, inputs, params, given=None):
    """Reference results under every combination, or the reason a combination has none."""
    rows = []
    for combination in template.combinations():
        try:
            rows.append((combination, _reference(template, inputs, params, combination, given), None))
        except ValueError as error:
            rows.append((combination, None, str(error)))
        except KeyError:                                           # a derived reference needs a free result the answer lacks
            rows.append((combination, _reference(template, inputs, params, combination, None), None))
    return rows


def consistent(template, submitted, rows, names=None):
    """Indices of the combinations whose reference agrees with every submitted result.

    `names` limits the match to some results, for an answer in which others are unusable.
    """
    spec = {name: row for name, row in template.matched().items() if names is None or name in names}
    hits, partial = [], []
    for index, (combination, reference, _) in enumerate(rows):
        if reference is None:
            partial.append({})
            continue
        agrees, detail = compare(spec, submitted, reference)
        partial.append(detail)
        if agrees:
            hits.append(index)
    return hits, partial


def summarise(template, rows, indices):
    """For each convention, the values present among the given combinations."""
    conventions = template.spec.get("conventions", {})
    return {dimension: sorted({rows[i][0][dimension] for i in indices}) for dimension in conventions}


def classes(template, rows, indices):
    """Group combinations whose references are indistinguishable on this instance."""
    groups = []
    for index in indices:
        reference = rows[index][1]
        for group in groups:
            if reference is not None and rows[group[0]][1] is not None and compare(template.matched(), reference, rows[group[0]][1])[0]:
                group.append(index)
                break
        else:
            groups.append([index])
    return groups


def split(template, rows, indices):
    accepted = [i for i in indices if not template.pitfalls_in(rows[i][0])]
    return accepted, [i for i in indices if i not in accepted]


def decide(template, rows, indices, partial=None):
    """Outcome of the variant match for one consistent set, before any probe narrows it."""
    summary = summarise(template, rows, indices)
    if not indices:
        return outcome(UNRESOLVED, "The results match no listed reading of the brief.", "unknown_answer",
                       consistent_with=summary, nearest=_nearest(template, rows, partial or []))
    accepted, pitfall = split(template, rows, indices)
    if not pitfall:
        return outcome(PASS, "The results are consistent only with accepted readings.", consistent_with=summary)
    certain = sorted(set.intersection(*(set(template.pitfalls_in(rows[i][0])) for i in pitfall)))
    possible = sorted(set.union(*(set(template.pitfalls_in(rows[i][0])) for i in pitfall)))
    described = {name: template.spec["pitfalls"][name] for name in possible}
    if not accepted:
        return outcome(FAIL, "The results are consistent only with readings that contain a known pitfall: " + ", ".join(certain or possible) + ".",
                       consistent_with=summary, pitfalls_certain=certain, pitfalls_possible=possible, pitfall_descriptions=described)
    return outcome(UNRESOLVED, "The results fit both an accepted reading and a known pitfall on this instance.", "ambiguous_variant",
                   consistent_with=summary, pitfalls_possible=possible, pitfall_descriptions=described)


def _nearest(template, rows, partial):
    """When nothing matches fully: which results agree under the accepted readings, and the closest readings."""
    scored = []
    for index, detail in enumerate(partial):
        if detail:
            agreeing = sorted(name for name, row in detail.items() if row["agrees"])
            scored.append((len(agreeing), index, agreeing))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [{"conventions": rows[index][0], "pitfalls": template.pitfalls_in(rows[index][0]), "results_agreeing": agreeing,
             "results_differing": {name: partial[index][name]["largest_difference"] for name in partial[index] if not partial[index][name]["agrees"]}}
            for _, index, agreeing in scored[:3]]


def discriminating_instance(template, inputs_for, params, rows, indices):
    """Another instance on which the accepted and pitfall readings in `indices` come apart.

    Returns (instance, True) when one separates every accepted reading from every
    pitfall reading, else the instance that splits the set into the most classes.
    """
    wanted = [rows[i][0] for i in indices] or [rows[0][0]]
    best = None
    for candidate in template.hooks.candidate_instances():
        if candidate["id"] == params.get("id") or any(candidate[key] != params.get(key) for key in getattr(template.hooks, "UNDOCUMENTED_PARAMS", ())):
            continue                                               # never vary a parameter the brief does not explain
        differences = sum(candidate[key] != params.get(key) for key in candidate if key != "id")
        local = []
        for combination in wanted:
            try:
                local.append((combination, _reference(template, inputs_for(candidate), candidate, combination), None))
            except ValueError as error:
                local.append((combination, None, str(error)))
        groups = classes(template, local, list(range(len(local))))
        mixed = any({bool(template.pitfalls_in(local[i][0])) for i in group} == {True, False} for group in groups)
        score = (not mixed, len(groups), differences)     # separate the readings first, then change as much as possible
        if best is None or score > best[0]:
            best = (score, candidate)
    if best is None:
        raise ValueError("The template has no second instance to probe with")
    return best[1], best[0][0]
