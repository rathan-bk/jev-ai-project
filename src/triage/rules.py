"""Rules-only baseline: plain if/else over the structured fields.

    python -m triage.rules          # predict every alert, write results/rules_<stamp>.json
    python -m triage.rules --tune   # grid-search RuleThresholds on the tune split

Plain if/else on the structured fields only; `summary` and `description` are
never read. `DEFAULT_THRESHOLDS` is the outcome of `--tune`, which only ever
sees the tune split.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any, Final

from triage.io import Alert, Dataset, load_dataset, utc_now, write_result
from triage.tuning import best_and_ties, grid, tied_values


@dataclass(frozen=True, slots=True)
class RuleThresholds:
    flapping_min_fired: int = 6  # fired_count_24h at or above this is flapping
    small_breach_max: float = 1.3  # breach_ratio at or below this is a small breach
    short_duration_max: int = 4  # duration_minutes at or below this is a short breach
    trend_min_duration: int = 300  # duration_minutes at or above this is a slow trend


DEFAULT_THRESHOLDS: Final = RuleThresholds()

GRID: Final[dict[str, list[Any]]] = {
    "flapping_min_fired": [4, 5, 6, 8, 10, 12],
    "small_breach_max": [1.2, 1.3, 1.5, 2.0],
    "short_duration_max": [2, 3, 4, 5],
    "trend_min_duration": [120, 240, 300, 360],
}


def triage(alert: Alert, t: RuleThresholds = DEFAULT_THRESHOLDS) -> str:
    """P1 / P2 / P3 / SUPPRESS from structured fields only. Order matters: first match wins."""
    if alert["env"] == "dev":
        return "SUPPRESS"
    if alert["fired_count_24h"] >= t.flapping_min_fired:
        return "SUPPRESS"  # flapping
    if any("[critical]" in related for related in alert["related_alerts_firing"]):
        return "SUPPRESS"  # duplicate of an already-firing critical alert
    if alert["env"] == "staging":
        return "P3"
    if alert["duration_minutes"] >= t.trend_min_duration:
        return "P3"  # slow trend: capacity, cert expiry
    if not alert["customer_facing"]:
        return "P2"  # prod, internal-only impact
    if alert["breach_ratio"] <= t.small_breach_max or alert["duration_minutes"] <= t.short_duration_max:
        return "P2"  # customer-facing but a small or short breach
    return "P1"


def accuracy(ds: Dataset, ids: Iterable[str], t: RuleThresholds) -> float:
    by_id = ds.by_id()
    ids = list(ids)
    return sum(triage(by_id[i], t) == ds.truth(i) for i in ids) / len(ids)


def tune(ds: Dataset) -> None:
    candidates = grid(RuleThresholds, GRID)
    best, ties = best_and_ties(candidates, lambda t: accuracy(ds, ds.split.tune, t))
    print(
        f"tune split n={len(ds.split.tune)}, grid size {len(candidates)}, "
        f"best accuracy {best:.3f}, {len(ties)} combos tie"
    )
    print("values of each threshold among the tied combos:")
    for name, values in tied_values(ties, GRID).items():
        print(f"  {name}: {values}  (grid {GRID[name]})")


def run(ds: Dataset) -> None:
    predictions = {a["id"]: {"label": triage(a)} for a in ds.alerts}
    path = write_result(
        "rules",
        {
            "triager": "rules",
            "timestamp": utc_now().isoformat(timespec="seconds"),
            "params": asdict(DEFAULT_THRESHOLDS),
            "predictions": predictions,
        },
    )
    print(f"wrote {path.relative_to(path.parents[1])}")
    print(f"tune accuracy: {accuracy(ds, ds.split.tune, DEFAULT_THRESHOLDS):.3f}  (n={len(ds.split.tune)})")
    print(
        f"test accuracy: {accuracy(ds, ds.split.test, DEFAULT_THRESHOLDS):.3f}  (n={len(ds.split.test)})  "
        "[breakdown in evaluate]"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tune", action="store_true", help="grid-search thresholds on the tune split")
    args = parser.parse_args()
    ds = load_dataset()
    tune(ds) if args.tune else run(ds)


if __name__ == "__main__":
    main()
