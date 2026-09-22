import random
from typing import Any

import pytest

from triage.dataset.builders import make_alert
from triage.jev import Answers, ChoiceAnswer, ScoreAnswer


@pytest.fixture
def rng() -> random.Random:
    return random.Random(1)


def alert(**overrides: Any) -> dict[str, Any]:
    """A prod, customer-facing, clearly-breached alert; override fields per test."""
    base = dict(
        alertname="HighErrorRate",
        service="checkout-web",
        env="prod",
        customer_facing=True,
        severity_tag="critical",
        summary="s",
        description="d",
        metric="http_5xx_rate_pct",
        value=20.0,
        threshold=2.0,
        duration_minutes=15,
        fired_count_24h=1,
        recent_deploy_30m=False,
    )
    return {"id": "ALT-000", **make_alert(**{**base, **overrides})}


def answers(
    *,
    impact: float = 2.8,
    noise: float = 0.05,
    downstream: float = 0.05,
    degrading: float = 0.9,
    urgency: str = "now",
    confidence: float = 0.95,
) -> Answers:
    return Answers(
        user_impact=ScoreAnswer(score=impact, confidence=0.9, probabilities={}),
        is_noise=noise,
        is_downstream_symptom=downstream,
        is_actively_degrading=degrading,
        urgency=ChoiceAnswer(choice=urgency, confidence=confidence, probabilities={}),
    )
