from dataclasses import dataclass

import pytest

from triage.tuning import best_and_ties, grid, tied_values


@dataclass(frozen=True, slots=True)
class T:
    a: int = 0
    b: int = 0
    untouched: str = "default"


def test_grid_is_the_cartesian_product():
    assert len(grid(T, {"a": [1, 2], "b": [10, 20, 30]})) == 6


def test_grid_keeps_defaults_for_fields_not_in_the_axes():
    assert all(t.untouched == "default" for t in grid(T, {"a": [1, 2]}))


def test_grid_rejects_a_field_the_dataclass_does_not_have():
    with pytest.raises(ValueError, match="unknown threshold fields"):
        grid(T, {"a": [1], "typo": [2]})


def test_best_and_ties_returns_every_candidate_that_reaches_the_best_score():
    """The tuner must report all optima, not silently pick one: ties mean the data cannot choose."""
    cands = [T(a=1), T(a=2), T(a=3)]
    best, ties = best_and_ties(cands, lambda t: 0.0 if t.a == 3 else 1.0)
    assert best == 1.0
    assert ties == [T(a=1), T(a=2)]  # input order preserved


def test_best_and_ties_with_a_single_winner():
    cands = [T(a=1), T(a=2)]
    best, ties = best_and_ties(cands, lambda t: float(t.a))
    assert (best, ties) == (2.0, [T(a=2)])


def test_tied_values_shows_which_thresholds_the_data_pins_down():
    """A field appearing with every grid value among the ties is one the data does not constrain."""
    ties = [T(a=1, b=10), T(a=2, b=10), T(a=1, b=20)]
    assert tied_values(ties, {"a": [1, 2], "b": [10, 20]}) == {"a": [1, 2], "b": [10, 20]}


def test_tied_values_sorts_and_deduplicates():
    assert tied_values([T(a=2), T(a=1), T(a=2)], {"a": [1, 2]}) == {"a": [1, 2]}
