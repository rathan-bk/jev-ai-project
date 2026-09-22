"""The alert record shape and the service catalogue used by all scenarios."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

# Services that serve end users directly. Everything in INTERNAL is used only by staff or batch jobs.
CUSTOMER_FACING: Final[list[str]] = [
    "checkout-web",
    "payments-api",
    "auth-service",
    "search-api",
    "mobile-bff",
    "cdn-edge",
    "order-service",
    "storefront-web",
    "recommendation-svc",
]
INTERNAL: Final[list[str]] = [
    "internal-admin",
    "reporting-svc",
    "analytics-pipeline",
    "data-warehouse",
    "billing-cron",
    "ci-runners",
    "image-resizer",
    "feature-flag-svc",
    "email-relay",
    "log-ingest",
    "metrics-db",
]

# Metrics where a lower value is the problem. Everything else is "higher is worse".
LOWER_IS_WORSE: Final[frozenset[str]] = frozenset({"cert_expiry_days", "available_replicas"})


def breach_ratio(metric: str, value: float, threshold: float) -> float:
    """How far past the threshold the metric is; >= 1.0 means breached."""
    if metric in LOWER_IS_WORSE:
        return round(threshold / value, 2)
    return round(value / threshold, 2)


def runbook_url(service: str, alertname: str) -> str:
    return f"https://runbooks.internal/{service}/{alertname.lower()}"


def make_alert(
    *,
    alertname: str,
    service: str,
    env: str,
    customer_facing: bool,
    severity_tag: str,
    summary: str,
    description: str,
    metric: str,
    value: float,
    threshold: float,
    duration_minutes: int,
    fired_count_24h: int,
    recent_deploy_30m: bool,
    related_alerts_firing: Sequence[str] = (),
) -> dict[str, Any]:
    """One alert record without an id. breach_ratio and runbook_url are derived, never hand-set."""
    return {
        "alertname": alertname,
        "service": service,
        "env": env,
        "customer_facing": customer_facing,
        "severity_tag": severity_tag,
        "summary": summary,
        "description": description,
        "metric": metric,
        "value": value,
        "threshold": threshold,
        "breach_ratio": breach_ratio(metric, value, threshold),
        "duration_minutes": duration_minutes,
        "fired_count_24h": fired_count_24h,
        "recent_deploy_30m": recent_deploy_30m,
        "related_alerts_firing": list(related_alerts_firing),
        "runbook_url": runbook_url(service, alertname),
    }
