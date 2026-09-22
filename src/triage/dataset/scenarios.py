"""Easy scenario generators: one function per (label, situation).

Each generator takes a seeded `random.Random` and returns `(alert, label)`.
The structured fields are always consistent with the label, so these are the
cases a rules-only triager should get right; variety comes from randomised
services, values and phrasing.

Do not reorder the random draws inside a generator: the dataset on disk is
regenerated from a fixed seed and must stay byte-identical.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any, Final

from triage.dataset.builders import CUSTOMER_FACING, INTERNAL, make_alert

Scenario = Callable[[random.Random], tuple[dict[str, Any], str]]

# service -> (what customers cannot do, where they see it)
ACTIONS: Final[dict[str, tuple[str, str]]] = {
    "checkout-web": ("complete checkout", "the checkout page"),
    "payments-api": ("pay for their orders", "the payment step"),
    "auth-service": ("log in", "the login page"),
    "search-api": ("get search results", "the search results page"),
    "mobile-bff": ("load the home feed in the app", "the mobile home screen"),
    "cdn-edge": ("load product images", "product pages"),
    "order-service": ("place orders", "the order confirmation page"),
    "storefront-web": ("browse the store", "the storefront"),
    "recommendation-svc": ("see recommendations", "the 'for you' carousel"),
}
ERRORS: Final[list[str]] = [
    "connection refused to postgres-primary",
    "TimeoutError: upstream did not respond",
    "NullPointerException in OrderMapper",
    "too many open files",
    "redis: connection pool exhausted",
    "grpc: DEADLINE_EXCEEDED",
]
TIMES: Final[list[str]] = ["09:12", "10:40", "11:05", "13:47", "14:20", "15:33", "16:58", "18:15"]


def deploy_note(r: random.Random, deployed: bool) -> str:
    """One sentence about recent deploys, consistent with `deployed`."""
    if deployed:
        return r.choice(
            [
                "A deploy went out about 15 minutes before this started.",
                "Timing lines up with the deploy that finished 20 minutes ago.",
                "This started right after the latest rollout; rollback is being discussed in the incident channel.",
            ]
        )
    return r.choice(
        [
            "No deploys in the last few hours.",
            "Nothing was deployed recently; looks like an infrastructure issue.",
            "No config or code changes in the window.",
        ]
    )


def p1_error_rate(r: random.Random) -> tuple[dict[str, Any], str]:
    """Prod, customer-facing 5xx spike with customer reports; fires 1-2 times."""
    svc = r.choice(CUSTOMER_FACING)
    action, page = ACTIONS[svc]
    value, thr = round(r.uniform(6, 40), 1), r.choice([1.0, 2.0, 5.0])
    deployed = r.random() < 0.4
    t = r.choice(TIMES)
    desc = r.choice(
        [
            f"5xx rate on {svc} climbed from a baseline of about 0.2% to {value}% starting {t} and is still rising. "
            f"Support has {r.randint(8, 60)} tickets in the last 15 minutes from customers unable to {action}. "
            f"{deploy_note(r, deployed)}",
            f"{svc} is returning HTTP 500 on roughly {value}% of requests. Every pod is logging '{r.choice(ERRORS)}'. "
            f"The status page is filling with reports of failures on {page}, and the rate is not coming down on its own. "
            f"{deploy_note(r, deployed)}",
            f"Error rate on {svc} has been above {thr}% for the whole window and is currently {value}%. "
            f"Customers are being shown an error page when they try to {action}; conversion on the live dashboard has dropped sharply. "
            f"{deploy_note(r, deployed)}",
        ]
    )
    return make_alert(
        alertname="HighErrorRate",
        service=svc,
        env="prod",
        customer_facing=True,
        severity_tag=r.choice(["critical", "critical", "warning"]),
        summary=f"{svc} 5xx rate {value}% (threshold {thr}%)",
        description=desc,
        metric="http_5xx_rate_pct",
        value=value,
        threshold=thr,
        duration_minutes=r.randint(5, 30),
        fired_count_24h=r.randint(1, 2),
        recent_deploy_30m=deployed,
        related_alerts_firing=[f"{r.choice(['mobile-bff', 'storefront-web'])}: HighErrorRate [warning]"]
        if r.random() < 0.3
        else [],
    ), "P1"


def p1_latency(r: random.Random) -> tuple[dict[str, Any], str]:
    """Prod, customer-facing p99 several times the SLO and climbing."""
    svc = r.choice(CUSTOMER_FACING)
    action, page = ACTIONS[svc]
    thr = r.choice([500, 800, 1000, 1500])
    value = int(thr * r.uniform(3, 8))
    deployed = r.random() < 0.3
    desc = r.choice(
        [
            f"p99 latency on {svc} is {value}ms against a {thr}ms SLO, up from about {int(thr * 0.6)}ms an hour ago and still climbing. "
            f"Mobile clients time out at 10s, so users see endless spinners on {page}. Traffic is normal, so this is not load-driven. "
            f"{deploy_note(r, deployed)}",
            f"{svc} p99 has been over {value}ms for the whole window. Customers are reporting that they cannot {action} because requests hang. "
            f"Database slow-query log shows lock waits on the orders table that are getting longer, not shorter. {deploy_note(r, deployed)}",
        ]
    )
    return make_alert(
        alertname="HighLatencyP99",
        service=svc,
        env="prod",
        customer_facing=True,
        severity_tag=r.choice(["critical", "warning"]),
        summary=f"{svc} p99 latency {value}ms (SLO {thr}ms)",
        description=desc,
        metric="p99_latency_ms",
        value=value,
        threshold=thr,
        duration_minutes=r.randint(8, 35),
        fired_count_24h=1,
        recent_deploy_30m=deployed,
    ), "P1"


def p1_replicas(r: random.Random) -> tuple[dict[str, Any], str]:
    """Prod, customer-facing service down to one healthy replica."""
    svc = r.choice(CUSTOMER_FACING)
    action, _ = ACTIONS[svc]
    thr = r.choice([3, 4, 6])
    value = 1
    desc = (
        f"Only {value} of {thr} {svc} replicas are passing readiness; the rest are crash-looping with "
        f"{r.choice(['OOMKilled', 'a panic on startup', 'failed liveness probes'])}. The load balancer is shedding "
        f"load and customers are getting 503s when they try to {action}. Traffic is at the normal daytime level so the "
        f"single healthy pod cannot keep up. {deploy_note(r, r.random() < 0.5)}"
    )
    return make_alert(
        alertname="AvailableReplicasLow",
        service=svc,
        env="prod",
        customer_facing=True,
        severity_tag="critical",
        summary=f"{svc} has {value}/{thr} healthy replicas",
        description=desc,
        metric="available_replicas",
        value=value,
        threshold=thr,
        duration_minutes=r.randint(4, 20),
        fired_count_24h=1,
        recent_deploy_30m=r.random() < 0.5,
    ), "P1"


def p2_internal(r: random.Random) -> tuple[dict[str, Any], str]:
    """Prod problem on an internal-only service; staff affected, customers not."""
    svc = r.choice(INTERNAL)
    team = r.choice(["finance", "support", "data", "marketing ops", "the fraud team"])
    kind = r.choice(["errors", "job", "lag", "cpu"])
    if kind == "errors":
        value, thr, metric, name = round(r.uniform(3, 15), 1), 1.0, "http_5xx_rate_pct", "HighErrorRate"
        desc = (
            f"{svc} is returning 500s on about {value}% of requests, mostly on the "
            f"{r.choice(['order lookup', 'bulk export', 'customer search', 'refund approval'])} page. "
            f"The {team} team is working around it via the database console for now. "
            f"Customers are not affected; this is an internal tool. {deploy_note(r, r.random() < 0.4)}"
        )
    elif kind == "job":
        thr = r.choice([30, 45, 60, 90])
        value, metric, name = int(thr * r.uniform(1.5, 3.5)), "job_duration_minutes", "JobDurationHigh"
        desc = (
            f"The {r.choice(['nightly', 'hourly', 'end-of-day'])} run on {svc} took {value} minutes against a "
            f"{thr} minute budget and the next run is queued behind it. The {team} team's morning reports will be "
            f"late. No customer-facing systems depend on this job. {deploy_note(r, r.random() < 0.3)}"
        )
    elif kind == "lag":
        thr = r.choice([60, 120, 300])
        value, metric, name = int(thr * r.uniform(2, 6)), "replication_lag_s", "ReplicationLagHigh"
        desc = (
            f"Replica lag on the {svc} database is {value}s and growing. Reads served from the replica are "
            f"stale, so the internal dashboards used by {team} are showing old numbers. The primary is healthy "
            f"and customer traffic does not touch this database. {deploy_note(r, r.random() < 0.3)}"
        )
    else:
        value, thr, metric, name = r.randint(88, 99), 80, "cpu_percent", "CPUHigh"
        desc = (
            f"CPU on {svc} is pinned at {value}% and requests from the internal UI are timing out. "
            f"Looks like a runaway {r.choice(['export', 'reindex', 'backfill'])} started by {team}. "
            f"Internal users only; nothing customer-facing calls this service. {deploy_note(r, r.random() < 0.3)}"
        )
    return make_alert(
        alertname=name,
        service=svc,
        env="prod",
        customer_facing=False,
        severity_tag=r.choice(["critical", "warning", "warning"]),
        summary=f"{svc} {metric} {value} (threshold {thr})",
        description=desc,
        metric=metric,
        value=value,
        threshold=thr,
        duration_minutes=r.randint(10, 90),
        fired_count_24h=r.randint(1, 3),
        recent_deploy_30m=r.random() < 0.3,
    ), "P2"


def p2_small_breach(r: random.Random) -> tuple[dict[str, Any], str]:
    """Prod, customer-facing, only slightly over threshold (1.05-1.3x), short."""
    svc = r.choice(CUSTOMER_FACING)
    action, page = ACTIONS[svc]
    if r.random() < 0.5:
        thr = r.choice([500, 800, 1000])
        value, metric, name, unit = int(thr * r.uniform(1.05, 1.3)), "p99_latency_ms", "HighLatencyP99", "ms"
    else:
        thr = r.choice([1.0, 2.0])
        value, metric, name, unit = round(thr * r.uniform(1.05, 1.3), 2), "http_5xx_rate_pct", "HighErrorRate", "%"
    dur = r.randint(2, 8)
    desc = r.choice(
        [
            f"{metric} on {svc} ticked up to {value}{unit} (threshold {thr}{unit}) for the last {dur} minutes. "
            f"Other metrics are flat and there are no customer reports. Probably the "
            f"{r.choice(['cache warm-up after the scale-down', 'weekly cache flush', 'search reindex', 'noisy neighbour on node 7'])}; "
            f"worth a look today but nobody is being blocked from trying to {action}. {deploy_note(r, r.random() < 0.3)}",
            f"Slightly over threshold on {svc}: {value}{unit} vs {thr}{unit}. A handful of requests on {page} are slower than "
            f"usual, nothing failing outright. Keeping an eye on it; should be looked at during the day. {deploy_note(r, r.random() < 0.3)}",
        ]
    )
    return make_alert(
        alertname=name,
        service=svc,
        env="prod",
        customer_facing=True,
        severity_tag="warning",
        summary=f"{svc} {metric} {value}{unit} (threshold {thr}{unit})",
        description=desc,
        metric=metric,
        value=value,
        threshold=thr,
        duration_minutes=dur,
        fired_count_24h=1,
        recent_deploy_30m=r.random() < 0.3,
    ), "P2"


def p2_recovered_spike(r: random.Random) -> tuple[dict[str, Any], str]:
    """Prod, customer-facing spike that has already recovered."""
    svc = r.choice(CUSTOMER_FACING)
    action, _ = ACTIONS[svc]
    value, thr = round(r.uniform(5, 20), 1), r.choice([1.0, 2.0])
    dur = r.randint(2, 4)
    desc = (
        f"5xx rate on {svc} spiked to {value}% for about {dur} minutes at {r.choice(TIMES)} and is already back to "
        f"baseline. A small number of customers would have seen an error trying to {action} during the spike. "
        f"Cause looks like {r.choice(['a pod being evicted during node maintenance', 'a brief upstream DNS failure', 'a connection pool reset'])}; "
        f"needs a look today to make sure it does not repeat, but nothing is broken right now."
    )
    return make_alert(
        alertname="HighErrorRate",
        service=svc,
        env="prod",
        customer_facing=True,
        severity_tag=r.choice(["warning", "critical"]),
        summary=f"{svc} 5xx rate {value}% (threshold {thr}%), recovering",
        description=desc,
        metric="http_5xx_rate_pct",
        value=value,
        threshold=thr,
        duration_minutes=dur,
        fired_count_24h=1,
        recent_deploy_30m=False,
    ), "P2"


def p3_capacity(r: random.Random) -> tuple[dict[str, Any], str]:
    """Slow capacity trend (disk/memory/pool) days from being a problem."""
    svc = r.choice(INTERNAL + CUSTOMER_FACING)
    metric, name = r.choice(
        [
            ("disk_used_percent", "DiskUsageHigh"),
            ("memory_percent", "MemoryHigh"),
            ("connection_pool_used_percent", "ConnectionPoolNearLimit"),
        ]
    )
    thr = r.choice([75, 80, 85])
    value = int(thr * r.uniform(1.02, 1.12))
    growth = round(r.uniform(0.2, 1.0), 1)
    days = int((98 - value) / growth)
    desc = r.choice(
        [
            f"{metric} on {svc} is at {value}%, growing roughly {growth}% per day. At this rate it reaches capacity in "
            f"about {days} days. Nothing is degraded now; this is a heads-up to add capacity or clean up before it becomes a problem.",
            f"{svc} crossed {thr}% {metric.replace('_', ' ')} overnight and is at {value}%. Growth has been steady for "
            f"{r.randint(2, 6)} weeks and matches the traffic trend. Please ticket a capacity increase for the next sprint; no urgency.",
        ]
    )
    return make_alert(
        alertname=name,
        service=svc,
        env="prod",
        customer_facing=svc in CUSTOMER_FACING,
        severity_tag=r.choice(["warning", "info"]),
        summary=f"{svc} {metric} {value}% (threshold {thr}%)",
        description=desc,
        metric=metric,
        value=value,
        threshold=thr,
        duration_minutes=r.randint(360, 5000),
        fired_count_24h=1,
        recent_deploy_30m=False,
    ), "P3"


def p3_staging(r: random.Random) -> tuple[dict[str, Any], str]:
    """Staging failure that blocks a release; no prod impact."""
    svc = r.choice(CUSTOMER_FACING + INTERNAL)
    ver = f"v{r.randint(2, 9)}.{r.randint(0, 30)}.{r.randint(0, 9)}"
    kind = r.choice(["errors", "latency", "restarts"])
    if kind == "errors":
        value, thr, metric, name = round(r.uniform(5, 60), 1), 1.0, "http_5xx_rate_pct", "HighErrorRate"
    elif kind == "latency":
        thr = r.choice([500, 1000])
        value, metric, name = int(thr * r.uniform(2, 6)), "p99_latency_ms", "HighLatencyP99"
    else:
        value, thr, metric, name = r.randint(6, 30), 3, "pod_restarts_15m", "PodRestartLoop"
    desc = r.choice(
        [
            f"{svc} {ver} is failing in staging: {metric} is {value} against a threshold of {thr}. The release candidate "
            f"cannot be promoted until this is fixed, so the {r.choice(['Thursday', 'Monday', 'end-of-sprint'])} release train is blocked. "
            f"No production impact.",
            f"QA reports that the staging deploy of {svc} ({ver}) is broken since the last merge; {metric} = {value}. "
            f"Release sign-off for this build is due {r.choice(['tomorrow', 'this week', 'Friday'])}. Staging only, prod is on the previous version and healthy.",
        ]
    )
    return make_alert(
        alertname=name,
        service=svc,
        env="staging",
        customer_facing=svc in CUSTOMER_FACING,
        severity_tag=r.choice(["critical", "warning"]),
        summary=f"staging {svc} {metric} {value} (threshold {thr})",
        description=desc,
        metric=metric,
        value=value,
        threshold=thr,
        duration_minutes=r.randint(15, 240),
        fired_count_24h=r.randint(1, 3),
        recent_deploy_30m=r.random() < 0.6,
    ), "P3"


def p3_cert(r: random.Random) -> tuple[dict[str, Any], str]:
    """TLS certificate expiring in 6-13 days after auto-renew failed."""
    svc = r.choice(CUSTOMER_FACING + INTERNAL)
    value, thr = r.randint(6, 13), 14
    desc = (
        f"The TLS certificate for {svc} expires in {value} days. Automatic renewal failed with "
        f"'{r.choice(['DNS challenge timed out', 'ACME account rate limited', 'CAA record mismatch'])}'. "
        f"Needs a manual renewal or a fix to the renewal job this week; nothing is broken today."
    )
    return make_alert(
        alertname="CertExpiringSoon",
        service=svc,
        env="prod",
        customer_facing=svc in CUSTOMER_FACING,
        severity_tag="warning",
        summary=f"{svc} TLS cert expires in {value} days",
        description=desc,
        metric="cert_expiry_days",
        value=value,
        threshold=thr,
        duration_minutes=r.randint(600, 3000),
        fired_count_24h=1,
        recent_deploy_30m=False,
    ), "P3"


def suppress_dev(r: random.Random) -> tuple[dict[str, Any], str]:
    """Anything in the dev cluster."""
    svc = r.choice(CUSTOMER_FACING + INTERNAL)
    metric, name, thr = r.choice(
        [
            ("cpu_percent", "CPUHigh", 80),
            ("http_5xx_rate_pct", "HighErrorRate", 1.0),
            ("pod_restarts_15m", "PodRestartLoop", 3),
            ("memory_percent", "MemoryHigh", 85),
            ("p99_latency_ms", "HighLatencyP99", 500),
        ]
    )
    value = round(thr * r.uniform(1.2, 8), 1) if isinstance(thr, float) else int(thr * r.uniform(1.2, 8))
    desc = r.choice(
        [
            f"{svc} in the dev cluster: {metric} = {value}. A developer is {r.choice(['iterating on a branch', 'running a local load test', 'testing a migration'])} "
            f"in their namespace. Dev has no SLO and is scaled to a single small node.",
            f"Dev environment only. The {svc} dev deployment {r.choice(['was redeployed with debug logging', 'is running an unmerged feature branch', 'has a deliberately broken config for a test'])}. "
            f"Nobody outside the team uses this environment.",
            f"{name} on {svc} (dev). The dev cluster auto-scales down every evening, so alerts like this are expected while pods reschedule.",
        ]
    )
    return make_alert(
        alertname=name,
        service=svc,
        env="dev",
        customer_facing=svc in CUSTOMER_FACING,
        severity_tag=r.choice(["critical", "warning", "info"]),
        summary=f"dev {svc} {metric} {value} (threshold {thr})",
        description=desc,
        metric=metric,
        value=value,
        threshold=thr,
        duration_minutes=r.randint(2, 120),
        fired_count_24h=r.randint(1, 6),
        recent_deploy_30m=r.random() < 0.5,
    ), "SUPPRESS"


def suppress_flapping(r: random.Random) -> tuple[dict[str, Any], str]:
    """Fires and self-resolves many times a day around the threshold."""
    svc = r.choice(CUSTOMER_FACING + INTERNAL)
    metric, name, thr, unit = r.choice(
        [
            ("cpu_percent", "CPUHigh", 80, "%"),
            ("p99_latency_ms", "HighLatencyP99", 500, "ms"),
            ("queue_depth", "QueueDepthHigh", 1000, ""),
            ("memory_percent", "MemoryHigh", 85, "%"),
        ]
    )
    value = int(thr * r.uniform(1.02, 1.25))
    fired = r.randint(8, 40)
    ticket = f"OPS-{r.randint(1000, 9999)}"
    desc = r.choice(
        [
            f"{name} on {svc} has fired and self-resolved {fired} times today, each time for a minute or two. {metric} hovers right "
            f"around the {thr}{unit} threshold ({value}{unit} now). Known noisy alert since the threshold was lowered; {ticket} is open to fix it. Nothing new in the logs.",
            f"Same flap as every day: {svc} {metric} bounces across {thr}{unit} during the "
            f"{r.choice(['hourly cron', 'GC cycle', 'cache refresh', 'log rotation'])} and clears on its own. "
            f"{fired} firings in 24h, no user-visible effect, no change in error rate. Tracked in {ticket}.",
        ]
    )
    return make_alert(
        alertname=name,
        service=svc,
        env="prod",
        customer_facing=svc in CUSTOMER_FACING,
        severity_tag=r.choice(["warning", "info"]),
        summary=f"{svc} {metric} {value}{unit} (threshold {thr}{unit}), flapping",
        description=desc,
        metric=metric,
        value=value,
        threshold=thr,
        duration_minutes=r.randint(1, 4),
        fired_count_24h=fired,
        recent_deploy_30m=False,
    ), "SUPPRESS"


UPSTREAM_PAIRS: Final[list[tuple[str, str, str]]] = [
    # (downstream service, upstream service, upstream alertname)
    ("checkout-web", "payments-api", "HighErrorRate"),
    ("mobile-bff", "search-api", "HighLatencyP99"),
    ("storefront-web", "recommendation-svc", "AvailableReplicasLow"),
    ("order-service", "payments-api", "HighLatencyP99"),
    ("mobile-bff", "auth-service", "HighErrorRate"),
    ("reporting-svc", "data-warehouse", "ReplicationLagHigh"),
    ("internal-admin", "order-service", "HighErrorRate"),
    ("email-relay", "notifications-queue", "QueueDepthHigh"),
]


def suppress_duplicate(r: random.Random) -> tuple[dict[str, Any], str]:
    """Downstream symptom of an upstream alert that is already paged."""
    down, up, up_alert = r.choice(UPSTREAM_PAIRS)
    thr = r.choice([1.0, 2.0])
    value = round(thr * r.uniform(1.2, 3.0), 1)
    inc = f"INC-{r.randint(4000, 4999)}"
    desc = r.choice(
        [
            f"{down} error rate is {value}% because calls to {up} are failing. {up} {up_alert} is already paged as {inc} and the "
            f"on-call is on it. This alert is the same outage seen from {down}; it will clear when {up} recovers.",
            f"Downstream symptom of the {up} incident ({inc}). All of the extra errors on {down} are timeouts waiting on {up}; "
            f"{down} itself is healthy. Nothing to do here separately from the incident.",
        ]
    )
    return make_alert(
        alertname="HighErrorRate",
        service=down,
        env="prod",
        customer_facing=down in CUSTOMER_FACING,
        severity_tag="warning",
        summary=f"{down} 5xx rate {value}% (threshold {thr}%)",
        description=desc,
        metric="http_5xx_rate_pct",
        value=value,
        threshold=thr,
        duration_minutes=r.randint(5, 25),
        fired_count_24h=r.randint(1, 2),
        recent_deploy_30m=False,
        related_alerts_firing=[f"{up}: {up_alert} [critical]"],
    ), "SUPPRESS"


# (generator, weight) per label. Weights control the mix within a label.
EASY_SCENARIOS: Final[dict[str, list[tuple[Scenario, int]]]] = {
    "P1": [(p1_error_rate, 7), (p1_latency, 4), (p1_replicas, 3)],
    "P2": [(p2_internal, 14), (p2_small_breach, 10), (p2_recovered_spike, 5)],
    "P3": [(p3_capacity, 15), (p3_staging, 13), (p3_cert, 7)],
    "SUPPRESS": [(suppress_dev, 15), (suppress_flapping, 17), (suppress_duplicate, 15)],
}
