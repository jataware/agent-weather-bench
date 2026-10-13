"""The directions ladder: how much of the centre's practice the agent is told, rung by rung.

A rung withholds parts of what the template hands the agent (sections of its practice sheet, sentences of its
brief) while the task, the grader and the reference stay fixed. The run record stores the rung and the texts the
agent actually saw (`task/brief.md`, the input manifest), and certification's test 5 leaves such runs out: an agent
that was told less answered a different contract, and its unknown answers are the measurement, not a defect.

The rungs are defined per template here, in the controller, so that the template's deciding files and their
fingerprint do not change when a rung is added.
"""
import re

FULL = "full"

LADDERS = {
    "objective-seasonal-outlook": {
        FULL: {},
        # 2. The agent keeps the inputs, the categories and the combination rules and must know how the three streams are built.
        "no-streams": {"practice_drop_sections": ["Stream 1: WVG", "Stream 2: eReg", "Stream 3: CCA"]},
        # 3. The brief alone: the practice sheet is withheld and the brief no longer points at it.
        "brief-only": {"practice": False,
                       "brief_edits": [(" described in `practice.md`", "")]},
        # 4. The task and the deliverables only: no practice sheet, no stream list, no leave-one-year-out rule.
        "minimal": {"practice": False,
                    "brief_edits": [(" described in `practice.md`", "")],
                    "brief_drop_sentences": [r"Follow the centre's three-stream practice.*?combined with equal weight\.\s*",
                                             r"Every historical forecast must be made as if.*?that year's model fields alone\.\s*"]},
    },
}


def rungs(template_name):
    return list(LADDERS.get(template_name, {FULL: {}}))


def apply(template_name, rung, brief, practice):
    """(brief, practice) as the agent sees them at `rung`; practice None when withheld. `full` returns both unchanged."""
    ladder = LADDERS.get(template_name, {FULL: {}})
    if rung not in ladder:
        raise ValueError(f"Template {template_name} has no directions rung {rung!r}; it has {', '.join(ladder)}")
    rule = ladder[rung]
    for old, new in rule.get("brief_edits", []):
        if old not in brief:
            raise ValueError(f"The brief no longer contains {old!r}; the rung {rung!r} needs updating")
        brief = brief.replace(old, new)
    for pattern in rule.get("brief_drop_sentences", []):
        brief, n = re.subn(pattern, "", brief, flags=re.S)
        if n != 1:
            raise ValueError(f"The brief matched {pattern!r} {n} times, expected once; the rung {rung!r} needs updating")
    if rule.get("practice", True) is False:
        practice = None
    elif practice is not None and rule.get("practice_drop_sections"):
        practice = drop_sections(practice, rule["practice_drop_sections"])
    return brief, practice


def drop_sections(text, titles):
    """`text` without the `## title` sections named, each running to the next `## ` heading or the end."""
    parts = re.split(r"(?m)^(?=## )", text)
    kept, found = [], set()
    for part in parts:
        heading = part.split("\n", 1)[0]
        title = heading[3:].strip() if heading.startswith("## ") else None
        if title in titles:
            found.add(title)
            continue
        kept.append(part)
    missing = [t for t in titles if t not in found]
    if missing:
        raise ValueError(f"The practice sheet has no section titled {missing[0]!r}")
    return "".join(kept)
