"""Triage with Jev: five questions per alert, label derived in code.

    python -m triage.jev                 # one call per alert -> results/jev_<stamp>.json
    python -m triage.jev --limit 5       # smoke test on the first 5 alerts
    python -m triage.jev --tune          # grid-search Thresholds on the tune split from recorded
                                         #   answers (no API calls)
    python -m triage.jev --recombine     # re-derive labels in the latest run with DEFAULT_THRESHOLDS
                                         #   (no API calls)

Design
- The whole alert minus `id` is sent as `state`; labels are never sent.
- Five questions go in ONE request; they run in parallel server-side.
- Jev returns judgments (probabilities), not a label. `combine()` turns them
  into P1 / P2 / P3 / SUPPRESS / NEEDS_HUMAN in code, so the policy is
  explicit, testable and re-tunable without new API calls.
- Every raw answer, the response `model` field, latency and token usage are
  stored per alert in the run file.
"""

from __future__ import annotations

import argparse
import statistics
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Final

from dotenv import load_dotenv
from typesafe_sdk import Choice, Noul, Score, SystemOneResponse, TypeSafeClient

from triage.config import ENV_FILE, JEV_MODEL, NEEDS_HUMAN
from triage.io import Alert, Dataset, latest_result, load_dataset, utc_now, write_json, write_result
from triage.metrics import percentile
from triage.tuning import best_and_ties, grid, tied_values

REQUEST_TIMEOUT_S: Final = 30.0  # public internet from India; the SDK default of 10s is tight

# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------

USER_IMPACT_LEVELS: Final[list[str]] = [
    "No user impact",
    "Internal users affected",
    "Some customers affected",
    "Widespread customer impact",
]
URGENCY_TO_LABEL: Final[dict[str, str]] = {
    "now": "P1",
    "business_hours": "P2",
    "backlog": "P3",
    "ignore": "SUPPRESS",
}

QUESTIONS: Final = {
    "user_impact": Score(
        instructions=(
            "Who is affected by the problem this alert describes, taking the free-text description into account?"
        ),
        criteria=USER_IMPACT_LEVELS,
    ),
    "is_noise": Noul(
        instructions=(
            "This alert is noise: a test/health-check signal, a known flapping pattern with nothing new, "
            "or a development (dev) environment. A staging environment is not by itself noise"
        ),
    ),
    "is_downstream_symptom": Noul(
        instructions=(
            "This alert is a downstream symptom of another alert that is already firing, not an independent problem"
        ),
    ),
    "is_actively_degrading": Noul(
        instructions=(
            "The described problem is actively getting worse or ongoing right now, not a past blip or slow trend"
        ),
    ),
    "urgency": Choice(
        instructions="How urgently does this alert need a human?",
        criteria={
            "now": "Needs a human immediately",
            "business_hours": "Needs attention today",
            "backlog": "Can be ticketed",
            "ignore": "Needs no action",
        },
    ),
}

# ---------------------------------------------------------------------------
# Answers and the combination policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScoreAnswer:
    score: float  # probability-weighted position on USER_IMPACT_LEVELS (0..3)
    confidence: float
    probabilities: dict[str, float]  # level name -> probability


@dataclass(frozen=True, slots=True)
class ChoiceAnswer:
    choice: str
    confidence: float
    probabilities: dict[str, float]  # option -> probability


@dataclass(frozen=True, slots=True)
class Answers:
    """The five raw judgments for one alert, exactly as Jev returned them."""

    user_impact: ScoreAnswer
    is_noise: float
    is_downstream_symptom: float
    is_actively_degrading: float
    urgency: ChoiceAnswer

    @classmethod
    def from_response(cls, r: SystemOneResponse) -> Answers:
        a = r.answers
        return cls(
            user_impact=ScoreAnswer(
                score=a["user_impact"].score,
                confidence=a["user_impact"].confidence,
                probabilities={USER_IMPACT_LEVELS[k]: v for k, v in a["user_impact"].probabilities.items()},
            ),
            is_noise=a["is_noise"].noul,
            is_downstream_symptom=a["is_downstream_symptom"].noul,
            is_actively_degrading=a["is_actively_degrading"].noul,
            urgency=ChoiceAnswer(
                choice=a["urgency"].choice,
                confidence=a["urgency"].confidence,
                probabilities=dict(a["urgency"].probabilities),
            ),
        )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Answers:
        return cls(
            user_impact=ScoreAnswer(**d["user_impact"]),
            is_noise=d["is_noise"],
            is_downstream_symptom=d["is_downstream_symptom"],
            is_actively_degrading=d["is_actively_degrading"],
            urgency=ChoiceAnswer(**d["urgency"]),
        )


@dataclass(frozen=True, slots=True)
class Thresholds:
    """How answers become a label. Tuned on the tune split only (`--tune`)."""

    noise_min: float = 0.6  # P(is_noise) at or above this -> SUPPRESS
    downstream_min: float = 0.6  # P(is_downstream_symptom) at or above this -> SUPPRESS
    p1_impact_min: float = 2.0  # user_impact score needed for P1 (2 = "Some customers affected")
    p1_degrading_min: float = 0.5  # P(is_actively_degrading) needed for P1
    # Tuned on the tune split: every positive gate cost strict accuracy monotonically
    # (0.885 at <=0.4, 0.846 at 0.6), so the gate is off. See docs/METHODOLOGY.md.
    urgency_confidence_min: float = 0.0  # urgency confidence below this -> NEEDS_HUMAN


DEFAULT_THRESHOLDS: Final = Thresholds()

GRID: Final[dict[str, list[Any]]] = {
    "noise_min": [0.5, 0.6, 0.7, 0.8],
    "downstream_min": [0.5, 0.6, 0.7, 0.8],
    "p1_impact_min": [1.5, 2.0, 2.5],
    "p1_degrading_min": [0.4, 0.5, 0.6],
}
GATE_CANDIDATES: Final[list[float]] = [0.0, 0.3, 0.4, 0.5, 0.6, 0.7]


def combine(ans: Answers, t: Thresholds = DEFAULT_THRESHOLDS) -> str:
    """Turn one alert's answers into P1 / P2 / P3 / SUPPRESS / NEEDS_HUMAN.

    The two suppression Nouls are checked first: they are independent
    judgments with their own probabilities, and a confident "this is a
    duplicate" should win even when the urgency choice is unsure (ignore vs
    backlog is a distinction that does not matter for a duplicate). The
    confidence gate then applies only to labels that depend on the urgency
    answer.
    """
    if ans.is_noise >= t.noise_min or ans.is_downstream_symptom >= t.downstream_min:
        return "SUPPRESS"
    if ans.urgency.confidence < t.urgency_confidence_min:
        return NEEDS_HUMAN
    label = URGENCY_TO_LABEL[ans.urgency.choice]
    if label == "P1" and not (
        ans.user_impact.score >= t.p1_impact_min and ans.is_actively_degrading >= t.p1_degrading_min
    ):
        return "P2"  # urgent, but not a customer-facing active degradation
    return label


# ---------------------------------------------------------------------------
# Calling Jev
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Prediction:
    label: str
    model: str  # `model` field of the response, recorded per alert
    latency_ms: float  # wall-clock around the SDK call
    input_tokens: int | None
    output_tokens: int | None
    answers: Answers

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Prediction:
        return cls(
            label=d["label"],
            model=d["model"],
            latency_ms=d["latency_ms"],
            input_tokens=d["input_tokens"],
            output_tokens=d["output_tokens"],
            answers=Answers.from_dict(d["answers"]),
        )


def state_for(alert: Alert) -> dict[str, Any]:
    """Everything except the id. Labels live in a separate file and never get here."""
    return {k: v for k, v in alert.items() if k != "id"}


def triage_alert(client: TypeSafeClient, alert: Alert, t: Thresholds = DEFAULT_THRESHOLDS) -> Prediction:
    started = time.perf_counter()
    r = client.system_one(state=state_for(alert), questions=QUESTIONS)
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    answers = Answers.from_response(r)
    return Prediction(
        label=combine(answers, t),
        model=r.model,
        latency_ms=latency_ms,
        input_tokens=r.usage.input_tokens,
        output_tokens=r.usage.output_tokens,
        answers=answers,
    )


def run(ds: Dataset, limit: int | None) -> None:
    load_dotenv(ENV_FILE)
    client = TypeSafeClient(model=JEV_MODEL, timeout=REQUEST_TIMEOUT_S)
    predictions: dict[str, Prediction] = {}
    for i, alert in enumerate(ds.alerts[:limit] if limit else ds.alerts, start=1):
        p = triage_alert(client, alert)
        predictions[alert["id"]] = p
        if p.model != JEV_MODEL:
            print(f"  WARNING: requested {JEV_MODEL}, response model field is {p.model}")
        print(
            f"[{i:>3}] {alert['id']} -> {p.label:<11} {p.latency_ms:>7.1f} ms  {p.input_tokens} tok  "
            f"urgency={p.answers.urgency.choice}({p.answers.urgency.confidence:.2f})"
        )
    # A smoke run gets its own prefix so latest_result("jev") never picks it up as the real run.
    path = write_result("jev-smoke" if limit else "jev", run_payload(predictions))
    print(f"\nwrote {path.name}")
    summarize(predictions, ds)


def run_payload(predictions: dict[str, Prediction]) -> dict[str, Any]:
    return {
        "triager": "jev",
        "model_requested": JEV_MODEL,
        "timestamp": utc_now().isoformat(timespec="seconds"),
        "params": asdict(DEFAULT_THRESHOLDS),
        "predictions": {k: p.to_dict() for k, p in predictions.items()},
    }


def load_predictions(run: dict[str, Any]) -> dict[str, Prediction]:
    return {k: Prediction.from_dict(v) for k, v in run["predictions"].items()}


# ---------------------------------------------------------------------------
# Reporting, tuning, recombining (all offline)
# ---------------------------------------------------------------------------


def accuracy_excluding_gated(preds: dict[str, Prediction], ds: Dataset, ids: Iterable[str]) -> tuple[int, int, float]:
    """(gated count, non-gated count, accuracy on the non-gated) for `ids` that have predictions."""
    ids = [i for i in ids if i in preds]
    gated = [i for i in ids if preds[i].label == NEEDS_HUMAN]
    rest = [i for i in ids if preds[i].label != NEEDS_HUMAN]
    acc = sum(preds[i].label == ds.truth(i) for i in rest) / len(rest) if rest else float("nan")
    return len(gated), len(rest), acc


def summarize(preds: dict[str, Prediction], ds: Dataset) -> None:
    latencies = [p.latency_ms for p in preds.values()]
    tokens = [p.input_tokens for p in preds.values() if p.input_tokens is not None]
    print(f"\n{len(preds)} alerts, models seen: {sorted({p.model for p in preds.values()})}")
    print(
        f"latency p50 {percentile(latencies, 50):.0f} ms, p95 {percentile(latencies, 95):.0f} ms, "
        f"input tokens total {sum(tokens)} (mean {statistics.mean(tokens):.0f})"
    )
    for name, ids in (("tune", ds.split.tune), ("test", ds.split.test)):
        n_gated, n_rest, acc = accuracy_excluding_gated(preds, ds, ids)
        if n_gated + n_rest:
            print(f"{name}: n={n_gated + n_rest}  NEEDS_HUMAN={n_gated}  accuracy on the rest={acc:.3f}")


def tune(preds: dict[str, Prediction], ds: Dataset) -> None:
    ids = [i for i in ds.split.tune if i in preds]

    def acc(t: Thresholds) -> float:
        return sum(combine(preds[i].answers, t) == ds.truth(i) for i in ids) / len(ids)

    # Label thresholds first, with the gate off so every alert is scored.
    candidates = [replace(t, urgency_confidence_min=0.0) for t in grid(Thresholds, GRID)]
    best, ties = best_and_ties(candidates, acc)
    print(
        f"tune split n={len(ids)}, grid size {len(candidates)}, "
        f"best accuracy (gate off) {best:.3f}, {len(ties)} combos tie"
    )
    print("values of each threshold among the tied combos:")
    for name, values in tied_values(ties, GRID).items():
        print(f"  {name}: {values}  (grid {GRID[name]})")

    # Then the gate, on the first tied combo: how many alerts it diverts and whether they were the wrong ones.
    base = ties[0]
    print("\nconfidence gate (using the first tied combo above):")
    print(f"  {'gate':>5} {'to_human':>9} {'acc_rest':>9} {'acc_if_not_gated':>17}")
    for gate in GATE_CANDIDATES:
        t = replace(base, urgency_confidence_min=gate)
        labels = {i: combine(preds[i].answers, t) for i in ids}
        gated = [i for i in ids if labels[i] == NEEDS_HUMAN]
        rest = [i for i in ids if labels[i] != NEEDS_HUMAN]
        acc_rest = sum(labels[i] == ds.truth(i) for i in rest) / len(rest) if rest else float("nan")
        would_have = [combine(preds[i].answers, base) == ds.truth(i) for i in gated]
        acc_gated = sum(would_have) / len(would_have) if would_have else float("nan")
        print(f"  {gate:>5.1f} {len(gated):>9} {acc_rest:>9.3f} {acc_gated:>17.3f}")


def recombine(run: dict[str, Any], path: Path, ds: Dataset) -> None:
    preds = load_predictions(run)
    preds = {k: replace(p, label=combine(p.answers)) for k, p in preds.items()}
    run["params"] = asdict(DEFAULT_THRESHOLDS)
    run["predictions"] = {k: p.to_dict() for k, p in preds.items()}
    write_json(path, run)
    print(f"recombined {path.name} with {run['params']}")
    summarize(preds, ds)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None, help="only call Jev for the first N alerts")
    parser.add_argument("--tune", action="store_true", help="grid-search thresholds from the latest run (no API calls)")
    parser.add_argument("--recombine", action="store_true", help="re-derive labels in the latest run (no API calls)")
    args = parser.parse_args()

    ds = load_dataset()
    if args.tune:
        run_data, _ = latest_result("jev")
        tune(load_predictions(run_data), ds)
    elif args.recombine:
        run_data, path = latest_result("jev")
        recombine(run_data, path, ds)
    else:
        run(ds, args.limit)


if __name__ == "__main__":
    main()
