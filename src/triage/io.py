"""Reading the dataset and reading/writing timestamped result files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from triage.config import ALERTS_FILE, LABELS_FILE, RESULTS_DIR, SPLIT_FILE

Alert = dict[str, Any]
"""One alert record as stored in data/alerts.json (includes "id")."""


@dataclass(frozen=True, slots=True)
class Label:
    label: str
    hard: bool


@dataclass(frozen=True, slots=True)
class Split:
    tune: tuple[str, ...]
    test: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Dataset:
    alerts: tuple[Alert, ...]
    labels: dict[str, Label]
    split: Split

    def by_id(self) -> dict[str, Alert]:
        return {a["id"]: a for a in self.alerts}

    def truth(self, alert_id: str) -> str:
        return self.labels[alert_id].label


def load_dataset() -> Dataset:
    alerts = json.loads(ALERTS_FILE.read_text())
    labels = {k: Label(**v) for k, v in json.loads(LABELS_FILE.read_text()).items()}
    split = json.loads(SPLIT_FILE.read_text())
    return Dataset(tuple(alerts), labels, Split(tuple(split["tune"]), tuple(split["test"])))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp() -> str:
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def write_result(prefix: str, payload: dict[str, Any]) -> Path:
    """Write results/<prefix>_<utc stamp>.json and return its path."""
    return write_json(RESULTS_DIR / f"{prefix}_{timestamp()}.json", payload)


def latest_result(prefix: str) -> tuple[dict[str, Any], Path]:
    """Newest results/<prefix>_*.json by name (names sort chronologically)."""
    runs = sorted(RESULTS_DIR.glob(f"{prefix}_*.json"))
    if not runs:
        raise FileNotFoundError(f"no results/{prefix}_*.json; run the earlier stage first")
    return json.loads(runs[-1].read_text()), runs[-1]
