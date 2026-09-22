"""Build the synthetic dataset: data/alerts.json, data/labels.json and data/split.json.

    python -m triage.dataset.generate

Fully deterministic: `build_dataset(SEED)` returns the same records every time,
and a test guards that the files on disk match it. Alert ids are assigned
after shuffling so they carry no information about the label.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Final

from triage.config import ALERTS_FILE, LABELS, LABELS_FILE, SPLIT_FILE
from triage.dataset.hard_cases import HARD_CASES
from triage.dataset.scenarios import EASY_SCENARIOS
from triage.io import write_json

SEED: Final = 20260921
# Easy cases per label; hard cases (25) are added on top. Total = 150.
EASY_COUNTS: Final[dict[str, int]] = {"P1": 14, "P2": 29, "P3": 35, "SUPPRESS": 47}
TUNE_FRACTION: Final = 1 / 3  # ~50 tune / ~100 test, stratified by (label, hard)


@dataclass(frozen=True, slots=True)
class Row:
    alert: dict[str, Any]
    label: str
    hard: bool


@dataclass(frozen=True, slots=True)
class BuiltDataset:
    alerts: list[dict[str, Any]]  # with ids
    labels: dict[str, dict[str, Any]]  # id -> {"label", "hard"}
    tune: list[str]
    test: list[str]


def generate_easy(r: random.Random) -> list[Row]:
    """Draw EASY_COUNTS[label] alerts per label from the weighted scenario mix, re-drawing exact duplicates."""
    rows: list[Row] = []
    seen: set[str] = set()
    for label, count in EASY_COUNTS.items():
        gens, weights = zip(*EASY_SCENARIOS[label], strict=True)
        for gen in r.choices(gens, weights=weights, k=count):
            alert, lab = gen(r)
            while alert["description"] in seen:
                alert, lab = gen(r)
            if lab != label:
                raise AssertionError(f"scenario for {label} returned {lab}")
            seen.add(alert["description"])
            rows.append(Row(alert, label, False))
    return rows


def stratified_split(
    r: random.Random, ids_by_stratum: dict[tuple[str, bool], list[str]]
) -> tuple[list[str], list[str]]:
    """Put round(n * TUNE_FRACTION) ids of every (label, hard) stratum in tune, the rest in test."""
    tune: list[str] = []
    test: list[str] = []
    for key in sorted(ids_by_stratum):
        ids = sorted(ids_by_stratum[key])
        r.shuffle(ids)
        n_tune = round(len(ids) * TUNE_FRACTION)
        tune += ids[:n_tune]
        test += ids[n_tune:]
    return sorted(tune), sorted(test)


def build_dataset(seed: int = SEED) -> BuiltDataset:
    r = random.Random(seed)
    rows = generate_easy(r) + [Row(alert, label, True) for alert, label in HARD_CASES]
    r.shuffle(rows)

    alerts, labels = [], {}
    strata: dict[tuple[str, bool], list[str]] = {}
    for i, row in enumerate(rows, start=1):
        alert_id = f"ALT-{i:03d}"
        alerts.append({"id": alert_id, **row.alert})
        labels[alert_id] = {"label": row.label, "hard": row.hard}
        strata.setdefault((row.label, row.hard), []).append(alert_id)
    tune, test = stratified_split(r, strata)
    return BuiltDataset(alerts, labels, tune, test)


def validate(ds: BuiltDataset) -> None:
    """Invariants the rest of the pipeline relies on."""
    n = len(ds.alerts)
    assert n == sum(EASY_COUNTS.values()) + len(HARD_CASES), n
    assert len({a["id"] for a in ds.alerts}) == n, "duplicate ids"
    assert len({a["description"] for a in ds.alerts}) == n, "duplicate descriptions"
    assert not any("label" in a for a in ds.alerts), "label leaked into alerts"
    assert set(ds.tune).isdisjoint(ds.test) and len(ds.tune) + len(ds.test) == n
    assert {v["label"] for v in ds.labels.values()} <= set(LABELS)


def distribution_table(ds: BuiltDataset) -> str:
    def row(name: str, ids: Iterable[str]) -> str:
        ids = list(ids)
        total = Counter(ds.labels[i]["label"] for i in ids)
        hard = Counter(ds.labels[i]["label"] for i in ids if ds.labels[i]["hard"])
        cells = "  ".join(f"{total[lab]:>8} ({hard[lab]:>2})" for lab in LABELS)
        return f"{name:<6} {len(ids):>4}  {cells}"

    header = f"{'split':<6} {'n':>4}  " + "  ".join(f"{lab:>13}" for lab in LABELS) + "   (hard in parens)"
    return "\n".join([header, row("tune", ds.tune), row("test", ds.test), row("all", ds.tune + ds.test)])


def main() -> None:
    ds = build_dataset()
    validate(ds)
    write_json(ALERTS_FILE, ds.alerts)
    write_json(LABELS_FILE, ds.labels)
    write_json(SPLIT_FILE, {"tune": ds.tune, "test": ds.test})
    print(f"wrote {len(ds.alerts)} alerts to {ALERTS_FILE.parent}\n")
    print(distribution_table(ds))


if __name__ == "__main__":
    main()
