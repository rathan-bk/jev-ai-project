"""Paths and constants shared by every stage."""

from __future__ import annotations

from pathlib import Path
from typing import Final

# src/triage/config.py -> repository root. The package is installed in editable mode.
ROOT: Final = Path(__file__).resolve().parents[2]
DATA_DIR: Final = ROOT / "data"
RESULTS_DIR: Final = ROOT / "results"
ENV_FILE: Final = ROOT / ".env"

ALERTS_FILE: Final = DATA_DIR / "alerts.json"
LABELS_FILE: Final = DATA_DIR / "labels.json"
SPLIT_FILE: Final = DATA_DIR / "split.json"

LABELS: Final[tuple[str, ...]] = ("P1", "P2", "P3", "SUPPRESS")
NEEDS_HUMAN: Final = "NEEDS_HUMAN"

JEV_MODEL: Final = "jev-1.13.0"
