"""Classification metrics with an explicit NEEDS_HUMAN bucket.

Conventions (see docs/METHODOLOGY.md)
- Strict accuracy counts NEEDS_HUMAN as wrong, so it is comparable across
  triagers that do and do not gate.
- Recall denominators are all true alerts of a class: a gated P1 is a missed P1.
- Precision is over the non-gated predictions of a class.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass

from triage.config import LABELS, NEEDS_HUMAN
from triage.io import Label


def percentile(values: Sequence[float], pct: float) -> float:
    """Nearest-rank percentile (no interpolation)."""
    if not values:
        return math.nan
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def _accuracy(preds: Mapping[str, str], truth: Mapping[str, str], ids: Sequence[str]) -> float:
    return sum(preds[i] == truth[i] for i in ids) / len(ids) if ids else math.nan


@dataclass(frozen=True, slots=True)
class ClassMetrics:
    precision: float
    recall: float
    support: int  # true alerts of this class
    gated: int  # of which sent to NEEDS_HUMAN


@dataclass(frozen=True, slots=True)
class Metrics:
    n: int
    accuracy: float  # strict
    n_hard: int
    accuracy_hard: float
    accuracy_easy: float
    n_gated: int
    n_rest: int
    accuracy_on_rest: float
    p1_recall: float
    per_class: dict[str, ClassMetrics]
    confusion: dict[str, dict[str, int]]  # truth -> predicted -> count

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate(preds: Mapping[str, str], labels: Mapping[str, Label], ids: Iterable[str]) -> Metrics:
    ids = list(ids)
    truth = {i: labels[i].label for i in ids}
    hard = [i for i in ids if labels[i].hard]
    easy = [i for i in ids if not labels[i].hard]
    gated = [i for i in ids if preds[i] == NEEDS_HUMAN]
    rest = [i for i in ids if preds[i] != NEEDS_HUMAN]

    per_class: dict[str, ClassMetrics] = {}
    for c in LABELS:
        tp = sum(1 for i in ids if truth[i] == c and preds[i] == c)
        predicted = sum(1 for i in ids if preds[i] == c)
        actual = sum(1 for i in ids if truth[i] == c)
        per_class[c] = ClassMetrics(
            precision=tp / predicted if predicted else math.nan,
            recall=tp / actual if actual else math.nan,
            support=actual,
            gated=sum(1 for i in ids if truth[i] == c and preds[i] == NEEDS_HUMAN),
        )

    columns = [*LABELS, NEEDS_HUMAN]
    confusion = {t: dict.fromkeys(columns, 0) for t in LABELS}
    for i in ids:
        confusion[truth[i]][preds[i]] += 1

    return Metrics(
        n=len(ids),
        accuracy=_accuracy(preds, truth, ids),
        n_hard=len(hard),
        accuracy_hard=_accuracy(preds, truth, hard),
        accuracy_easy=_accuracy(preds, truth, easy),
        n_gated=len(gated),
        n_rest=len(rest),
        accuracy_on_rest=_accuracy(preds, truth, rest),
        p1_recall=per_class["P1"].recall,
        per_class=per_class,
        confusion=confusion,
    )
