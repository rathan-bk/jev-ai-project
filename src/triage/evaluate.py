"""Evaluate the rules baseline and Jev on the test split.

    python -m triage.evaluate

Reads the newest results/rules_*.json, results/jev_*.json and
results/cost_*.json and writes results/summary.md (metrics, confusion
matrices, and every test alert Jev got wrong with its full answers) plus
results/summary_<stamp>.json with the same numbers in machine-readable form.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from typing import Any

from triage.config import LABELS, NEEDS_HUMAN, RESULTS_DIR
from triage.io import Alert, Label, latest_result, load_dataset, timestamp, utc_now, write_json
from triage.jev import Prediction, load_predictions
from triage.metrics import Metrics, evaluate, percentile

SUMMARY_MD = RESULTS_DIR / "summary.md"


def pct(x: float) -> str:
    return "n/a" if math.isnan(x) else f"{100 * x:.1f}%"


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def md_table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def confusion_md(m: Metrics, include_gate: bool) -> str:
    cols = [*LABELS, NEEDS_HUMAN] if include_gate else list(LABELS)
    rows = [[f"**{t}**", *[str(m.confusion[t][p]) for p in cols]] for t in LABELS]
    return md_table(["truth \\ predicted", *cols], rows)


def per_class_md(rules: Metrics, jev: Metrics) -> str:
    rows = []
    for c in LABELS:
        r, j = rules.per_class[c], jev.per_class[c]
        rows.append([c, str(r.support), pct(r.precision), pct(r.recall), pct(j.precision), pct(j.recall), str(j.gated)])
    return md_table(["class", "n", "rules precision", "rules recall", "Jev precision", "Jev recall", "Jev gated"], rows)


def failure_md(alert_id: str, alert: Alert, label: Label, jev: Prediction, rules_label: str) -> str:
    a = jev.answers
    impact_probs = ", ".join(f"{k} {v:.2f}" for k, v in a.user_impact.probabilities.items())
    urgency_probs = ", ".join(f"{k} {v:.2f}" for k, v in a.urgency.probabilities.items())
    heading = f"### {alert_id} — truth **{label.label}**, Jev said **{jev.label}**, rules said {rules_label}"
    if label.hard:
        heading += "  `hard`"
    fields = (
        f"env={alert['env']} customer_facing={alert['customer_facing']} severity={alert['severity_tag']} "
        f"breach={alert['breach_ratio']} duration={alert['duration_minutes']}m fired_24h={alert['fired_count_24h']} "
        f"deploy_30m={alert['recent_deploy_30m']} related={alert['related_alerts_firing'] or '[]'}"
    )
    answers = md_table(
        ["question", "answer"],
        [
            ["user_impact", f"score {a.user_impact.score:.2f} (conf {a.user_impact.confidence:.2f}) — {impact_probs}"],
            ["is_noise", f"{a.is_noise:.2f}"],
            ["is_downstream_symptom", f"{a.is_downstream_symptom:.2f}"],
            ["is_actively_degrading", f"{a.is_actively_degrading:.2f}"],
            ["urgency", f"**{a.urgency.choice}** (conf {a.urgency.confidence:.2f}) — {urgency_probs}"],
            ["latency / input tokens", f"{jev.latency_ms} ms / {jev.input_tokens}"],
        ],
    )
    return "\n".join([heading, "", f"`{alert['summary']}`  ", fields, "", f"> {alert['description']}", "", answers, ""])


def headline_md(rules: Metrics, jev: Metrics, lat_p50: float, lat_p95: float, cost: dict[str, Any]) -> str:
    c_s, c_j = cost["subsets"]["test"]["sonnet5_estimated"], cost["subsets"]["test"]["jev_actual"]
    rows = [
        ["overall accuracy (strict; NEEDS_HUMAN counts as wrong)", pct(rules.accuracy), pct(jev.accuracy)],
        [f"accuracy on hard cases (n={jev.n_hard})", pct(rules.accuracy_hard), pct(jev.accuracy_hard)],
        [f"accuracy on easy cases (n={jev.n - jev.n_hard})", pct(rules.accuracy_easy), pct(jev.accuracy_easy)],
        [
            "**P1 recall** (missing a real P1 is the costliest error)",
            pct(rules.p1_recall),
            f"{pct(jev.p1_recall)} ({jev.per_class['P1'].gated} P1 gated)",
        ],
        ["sent to NEEDS_HUMAN", "—", f"{jev.n_gated} / {jev.n}"],
        ["accuracy on the rest (non-gated)", "—", f"{pct(jev.accuracy_on_rest)} (n={jev.n_rest})"],
        ["latency p50 / p95", "~0 ms (local if/else)", f"{lat_p50:.0f} ms / {lat_p95:.0f} ms"],
        [f"cost, test set ({jev.n} alerts)", "$0", f"${c_j['total_usd']:.5f} (actual)"],
        ["cost per alert", "$0", f"${c_j['per_alert_usd']:.7f} (actual)"],
        [
            "**Sonnet 5, estimated** — test set / per alert",
            "",
            f"${c_s['total_usd']:.5f} / ${c_s['per_alert_usd']:.7f} (est.)",
        ],
    ]
    return md_table(["metric", "rules-only", "Jev"], rows)


def caveats_md(cost: dict[str, Any]) -> str:
    p, a = cost["prices_usd_per_1m"], cost["assumptions"]
    return (
        "Latency was measured from India over the public internet (wall-clock around each SDK call, including TLS "
        f"and the first call's connection setup). Jev cost is actual input tokens x ${p['jev_input']}/1M, output free. "
        "Sonnet 5 cost is an **estimate**: no LLM was called; input tokens were counted with tiktoken "
        f"`{a['tokenizer']}` (Claude's tokenizer differs, so counts are approximate), "
        f"{a['sonnet5_output_tokens_per_alert']} output tokens were assumed per alert, priced at "
        f"${p['sonnet5_input']}/${p['sonnet5_output']} per 1M input/output."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    ds = load_dataset()
    test = list(ds.split.test)
    rules_run, rules_file = latest_result("rules")
    jev_run, jev_file = latest_result("jev")
    cost, cost_file = latest_result("cost")

    rules_preds = {i: rules_run["predictions"][i]["label"] for i in test}
    jev_preds = {i: p for i, p in load_predictions(jev_run).items() if i in set(test)}
    jev_labels = {i: p.label for i, p in jev_preds.items()}

    m_rules, m_jev = evaluate(rules_preds, ds.labels, test), evaluate(jev_labels, ds.labels, test)
    latencies = [p.latency_ms for p in jev_preds.values()]
    lat_p50, lat_p95 = percentile(latencies, 50), percentile(latencies, 95)
    models_seen = sorted({p.model for p in jev_preds.values()})
    wrong = [i for i in test if jev_labels[i] != ds.truth(i)]

    sections = [
        "# Alert triage benchmark — test set results",
        "",
        f"Generated {utc_now().isoformat(timespec='seconds')} from "
        f"`{rules_file.name}`, `{jev_file.name}`, `{cost_file.name}`.  ",
        f"Test set: {len(test)} alerts ({m_jev.n_hard} hard). Jev model (from the response `model` field): "
        f"`{', '.join(models_seen)}`. Thresholds for both systems were tuned on the separate tune split only.",
        "",
        "## Headline",
        "",
        headline_md(m_rules, m_jev, lat_p50, lat_p95, cost),
        "",
        caveats_md(cost),
        "",
        "## Per-class precision / recall",
        "",
        per_class_md(m_rules, m_jev),
        "",
        "## Confusion matrices (rows = truth)",
        "",
        "**Rules-only**",
        "",
        confusion_md(m_rules, include_gate=False),
        "",
        "**Jev**",
        "",
        confusion_md(m_jev, include_gate=True),
        "",
        "## Jev parameters",
        "",
        "```",
        json.dumps(jev_run["params"], indent=2),
        "```",
        "",
        "## Every test alert where Jev was wrong (or gated)",
        "",
        f"{len(wrong)} of {len(test)}. The rules-only prediction is shown for comparison.",
        "",
        *[failure_md(i, ds.by_id()[i], ds.labels[i], jev_preds[i], rules_preds[i]) for i in wrong],
    ]
    SUMMARY_MD.write_text("\n".join(sections) + "\n")

    stamp = timestamp()
    write_json(
        RESULTS_DIR / f"summary_{stamp}.json",
        {
            "timestamp": stamp,
            "inputs": [rules_file.name, jev_file.name, cost_file.name],
            "test_n": len(test),
            "rules": m_rules.to_dict(),
            "jev": {
                **m_jev.to_dict(),
                "latency_ms_p50": lat_p50,
                "latency_ms_p95": lat_p95,
                "models_seen": models_seen,
            },
            "cost_test": cost["subsets"]["test"],
        },
    )

    cut = sections.index("## Jev parameters")
    print("\n".join(sections[:cut]))
    print(f"\n{len(wrong)} Jev errors listed in {SUMMARY_MD.relative_to(RESULTS_DIR.parent)}")


if __name__ == "__main__":
    main()
