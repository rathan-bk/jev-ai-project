"""Dataset invariants and the reproducibility guard."""

import json
from collections import Counter

from triage.config import ALERTS_FILE, LABELS, LABELS_FILE, SPLIT_FILE
from triage.dataset.builders import breach_ratio
from triage.dataset.generate import EASY_COUNTS, SEED, build_dataset, validate
from triage.dataset.hard_cases import HARD_CASES
from triage.dataset.scenarios import EASY_SCENARIOS


def test_breach_ratio_direction():
    assert breach_ratio("http_5xx_rate_pct", 4.0, 2.0) == 2.0
    assert breach_ratio("cert_expiry_days", 7, 14) == 2.0  # lower is worse
    assert breach_ratio("available_replicas", 1, 3) == 3.0


def test_every_scenario_returns_its_label(rng):
    for label, scenarios in EASY_SCENARIOS.items():
        for gen, _weight in scenarios:
            alert, got = gen(rng)
            assert got == label
            assert "label" not in alert and "id" not in alert


def test_hard_cases_are_labelled_and_marked():
    labels = Counter(label for _, label in HARD_CASES)
    assert sum(labels.values()) == 25
    assert set(labels) == set(LABELS)


def test_build_dataset_invariants():
    ds = build_dataset()
    validate(ds)
    counts = Counter(v["label"] for v in ds.labels.values())
    hard = Counter(label for _, label in HARD_CASES)
    for label in LABELS:
        assert counts[label] == EASY_COUNTS[label] + hard[label]


def test_split_is_stratified_by_label_and_hardness():
    ds = build_dataset()
    tune = set(ds.tune)
    for label in LABELS:
        for is_hard in (True, False):
            ids = [i for i, v in ds.labels.items() if v["label"] == label and v["hard"] is is_hard]
            n_tune = sum(i in tune for i in ids)
            assert n_tune == round(len(ids) / 3), (label, is_hard)


def test_ids_carry_no_label_information():
    ds = build_dataset()
    first_50 = [ds.labels[f"ALT-{i:03d}"]["label"] for i in range(1, 51)]
    assert len(set(first_50)) == len(LABELS)  # a sorted-by-label layout would fail this


def test_files_on_disk_match_the_generator():
    """Guards reproducibility: results/jev_*.json refers to these exact records."""
    ds = build_dataset(SEED)
    assert json.loads(ALERTS_FILE.read_text()) == ds.alerts
    assert json.loads(LABELS_FILE.read_text()) == ds.labels
    assert json.loads(SPLIT_FILE.read_text()) == {"tune": ds.tune, "test": ds.test}
