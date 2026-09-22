"""Grid search over threshold dataclasses. Used by the rules and Jev stages.

Tuning is done on the tune split only; the caller passes the scoring function.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import fields
from typing import Any, TypeVar

T = TypeVar("T")


def grid(cls: type[T], axes: Mapping[str, Sequence[Any]]) -> list[T]:
    """Every combination of `axes` as an instance of the frozen dataclass `cls`.

    Fields of `cls` that are not in `axes` keep their defaults.
    """
    names = list(axes)
    unknown = set(names) - {f.name for f in fields(cls)}  # type: ignore[arg-type]
    if unknown:
        raise ValueError(f"unknown threshold fields: {sorted(unknown)}")
    return [cls(**dict(zip(names, combo, strict=True))) for combo in itertools.product(*(axes[n] for n in names))]


def best_and_ties(candidates: Iterable[T], score: Callable[[T], float]) -> tuple[float, list[T]]:
    """Highest score and every candidate that reaches it, in input order."""
    scored = [(score(c), c) for c in candidates]
    best = max(s for s, _ in scored)
    return best, [c for s, c in scored if s == best]


def tied_values(ties: Sequence[Any], axes: Mapping[str, Sequence[Any]]) -> dict[str, list[Any]]:
    """For each tuned field, the sorted set of values that appear among the tied candidates."""
    return {name: sorted({getattr(t, name) for t in ties}) for name in axes}
