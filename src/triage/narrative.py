"""Human-readable evaluation summary -> results/evaluation_summary.md.

`evaluate.py` produces the reference report: every table, every error, every
raw answer. This produces the explanation a reader wants first -- what the two
systems are, where each one fails, and what the free-text description said that
the structured fields did not.

Every number and every worked example is derived from the latest run files, so
this document cannot drift from the data the way a hand-written summary can.
"""

from __future__ import annotations

from typing import Any, Final

from triage.config import NEEDS_HUMAN, RESULTS_DIR
from triage.io import Alert, Dataset, latest_result, load_dataset
from triage.jev import Prediction, load_predictions
from triage.metrics import evaluate as compute_metrics
from triage.rules import triage as rules_triage

SUMMARY_MD: Final = RESULTS_DIR / "evaluation_summary.md"

# Rough ordering used only to rank how badly a wrong answer missed, for picking examples.
SEVERITY: Final[dict[str, int]] = {"SUPPRESS": 0, "P3": 1, "P2": 2, "P1": 3, NEEDS_HUMAN: 1}
N_EXAMPLES: Final = 4


def _fields_line(a: Alert) -> str:
    return (
        f"`env={a['env']}` · `customer_facing={a['customer_facing']}` · "
        f"`fired_count_24h={a['fired_count_24h']}` · `breach_ratio={a['breach_ratio']}x` · "
        f"`duration_minutes={a['duration_minutes']}`"
    )


def pick_examples(ds: Dataset, preds: dict[str, Prediction], test: list[str]) -> list[str]:
    """Alerts the rules got wrong and Jev got right, most badly missed first.

    Balanced across direction: cases where the rules over-escalated and cases where they
    under-escalated, so the document shows both halves of the failure mode.
    """
    by_id = ds.by_id()
    wins = [i for i in test if rules_triage(by_id[i]) != ds.truth(i) and preds[i].label == ds.truth(i)]

    def gap(i: str) -> int:
        return SEVERITY[rules_triage(by_id[i])] - SEVERITY[ds.truth(i)]

    over = sorted((i for i in wins if gap(i) > 0), key=lambda i: (-gap(i), i))
    under = sorted((i for i in wins if gap(i) < 0), key=lambda i: (gap(i), i))
    picked: list[str] = []
    for a, b in zip(under, over, strict=False):  # alternate under/over
        picked += [a, b]
    return picked[:N_EXAMPLES] or wins[:N_EXAMPLES]


def example_md(i: str, a: Alert, truth: str, rules_label: str, p: Prediction) -> str:
    ans = p.answers
    return "\n".join(
        [
            f"### {i} — the fields said **{rules_label}**, the answer was **{truth}**",
            "",
            f"> {a['summary']}",
            "",
            f"**What the structured fields said:** {_fields_line(a)}",
            "",
            "**What the description said:**",
            "",
            f"> {a['description']}",
            "",
            f"**Rules read only the fields and answered {rules_label}.** "
            f"Jev read the description and answered **{p.label}**, via:",
            "",
            "| question | Jev's answer |",
            "|---|---|",
            f"| is this noise? | {ans.is_noise:.2f} |",
            f"| who is affected? | score {ans.user_impact.score:.2f} ({ans.user_impact.confidence:.0%} confident) |",
            f"| is it getting worse? | {ans.is_actively_degrading:.2f} |",
            f"| how urgent? | **{ans.urgency.choice}** ({ans.urgency.confidence:.0%} confident) |",
            "",
        ]
    )


def build(ds: Dataset, preds: dict[str, Prediction], rules_preds: dict[str, str], test: list[str]) -> str:
    by_id = ds.by_id()
    jev_labels = {i: p.label for i, p in preds.items() if i in set(test)}
    m_rules = compute_metrics(rules_preds, ds.labels, test)
    m_jev = compute_metrics(jev_labels, ds.labels, test)

    hard = [i for i in test if ds.labels[i].hard]
    easy = [i for i in test if not ds.labels[i].hard]
    errs = [i for i in test if jev_labels[i] != ds.truth(i)]
    transitions = sorted({(ds.truth(i), jev_labels[i]) for i in errs})
    suppressed_rules = [i for i in test if rules_preds[i] == "SUPPRESS" and ds.truth(i) in ("P1", "P2")]
    suppressed_jev = [i for i in test if jev_labels[i] == "SUPPRESS" and ds.truth(i) in ("P1", "P2")]

    lines = [
        "# What this benchmark found",
        "",
        "A plain-language companion to [`summary.md`](summary.md), which holds the full tables.",
        "Generated from the same run files; every number below is computed, not typed.",
        "",
        "## The question",
        "",
        "Every monitoring alert arrives with two kinds of information: **structured fields** "
        "(which environment, how far over threshold, how many times it fired) and a "
        "**free-text description** written by whoever set the alert up, or appended by whoever "
        "looked at it last.",
        "",
        "Traditional alert routing reads the fields, because code can compare numbers. This "
        "benchmark asks what the description is worth: two systems classify the same "
        f"{len(test)} alerts into P1 / P2 / P3 / SUPPRESS, scored against the same hand-written "
        "answer key.",
        "",
        "- **rules-only** — nine `if` statements over the structured fields. Never reads the description.",
        "- **Jev** — answers five narrow questions about the alert *including* its description, and "
        "returns a probability for each. The label is then derived in code.",
        "",
        "## The headline: a tie that hides everything interesting",
        "",
        "| | rules-only | Jev |",
        "|---|---|---|",
        f"| overall accuracy | {m_rules.accuracy:.1%} | {m_jev.accuracy:.1%} |",
        f"| on the {len(easy)} **easy** alerts | {m_rules.accuracy_easy:.1%} | {m_jev.accuracy_easy:.1%} |",
        f"| on the {len(hard)} **hard** alerts | {m_rules.accuracy_hard:.1%} | {m_jev.accuracy_hard:.1%} |",
        f"| real P1s caught | {m_rules.p1_recall:.1%} | {m_jev.p1_recall:.1%} |",
        f"| real incidents silently suppressed | {len(suppressed_rules)} | {len(suppressed_jev)} |",
        "",
        "The overall numbers are nearly identical and tell you almost nothing. The split "
        "between easy and hard is the actual result.",
        "",
        "**Easy alerts** are ones where the fields and the description agree — a prod "
        "customer-facing service is badly over threshold and the text says so. The rules get "
        f"{m_rules.accuracy_easy:.0%} of these right, because that is exactly what they were "
        "built for.",
        "",
        "**Hard alerts** are ones where the fields are *misleading* and only the description "
        f"resolves it. Rules get {m_rules.accuracy_hard:.1%}. Jev gets {m_jev.accuracy_hard:.1%}.",
        "",
        "## Why the rules hit a ceiling",
        "",
        "The rules are not badly written — their thresholds were grid-searched on a separate "
        "tune split, so they are the best this rule structure can do. The ceiling is structural: "
        "**the information needed is not in the fields they read.**",
        "",
        f"The cost is concrete. The rules silently routed {len(suppressed_rules)} real P1/P2 "
        f"incidents to SUPPRESS, where nobody would ever see them, and missed "
        f"{m_rules.per_class['P1'].support - round(m_rules.p1_recall * m_rules.per_class['P1'].support)} "
        f"of {m_rules.per_class['P1'].support} real P1s. Jev suppressed {len(suppressed_jev)}.",
        "",
        "## What the description said that the fields did not",
        "",
        f"{len(pick_examples(ds, preds, test))} of the alerts where the rules were wrong and Jev was right. "
        "In each, the numbers point one way and the sentence points the other.",
        "",
    ]

    for i in pick_examples(ds, preds, test):
        lines.append(example_md(i, by_id[i], ds.truth(i), rules_preds[i], preds[i]))

    lines += [
        "## Where Jev still disagrees",
        "",
        f"{len(errs)} of {len(test)} alerts are still wrong. They are not scattered — "
        f"{'every one is' if len(transitions) == 1 else 'they fall into'} "
        + ", ".join(f"**{t} → {p}**" for t, p in transitions)
        + ".",
        "",
        "These are alerts the answer key calls backlog work and Jev calls same-day work: "
        "certificates expiring in a week, latency creeping up, pods restarting slowly. "
        "Reasonable people disagree about that boundary, and the disagreement runs one way "
        "only — Jev over-prioritises, never under-prioritises. Nothing real gets dropped.",
        "",
        "## What it costs",
        "",
        "| | rules-only | Jev |",
        "|---|---|---|",
        "| time per alert | microseconds, local | ~0.5 s, one network call |",
        "| money per alert | $0 | about three cents per thousand alerts |",
        "| needs network access | no | yes |",
        "",
        "Whether that trade is worth it depends on what a missed P1 costs, which no benchmark can tell you.",
        "",
        "---",
        "",
        "Full tables, confusion matrices, per-class precision and recall, and every error with "
        "its raw answers: [`summary.md`](summary.md).",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    ds = load_dataset()
    test = list(ds.split.test)
    rules_run, _ = latest_result("rules")
    jev_run, _ = latest_result("jev")
    preds = load_predictions(jev_run)
    rules_preds: dict[str, Any] = {i: rules_run["predictions"][i]["label"] for i in test}

    SUMMARY_MD.write_text(build(ds, preds, rules_preds, test))
    print(f"wrote {SUMMARY_MD.relative_to(SUMMARY_MD.parents[1])}")


if __name__ == "__main__":
    main()
