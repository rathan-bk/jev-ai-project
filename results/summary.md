# Alert triage benchmark — test set results

Generated 2026-09-22T16:51:04+00:00 from `rules_20260922T165104Z.json`, `jev_20260922T164403Z.json`, `cost_20260921T055649Z.json`.  
Test set: 98 alerts (16 hard). Jev model (from the response `model` field): `jev-1.13.0`. Thresholds for both systems were tuned on the separate tune split only.

## Headline

| metric | rules-only | Jev |
|---|---|---|
| overall accuracy (strict; NEEDS_HUMAN counts as wrong) | 86.7% | 78.6% |
| accuracy on hard cases (n=16) | 18.8% | 68.8% |
| accuracy on easy cases (n=82) | 100.0% | 80.5% |
| **P1 recall** (missing a real P1 is the costliest error) | 69.2% | 100.0% (0 P1 gated) |
| sent to NEEDS_HUMAN | — | 8 / 98 |
| accuracy on the rest (non-gated) | — | 85.6% (n=90) |
| latency p50 / p95 | ~0 ms (local if/else) | 354 ms / 445 ms |
| cost, test set (98 alerts) | $0 | $0.00309 (actual) |
| cost per alert | $0 | $0.0000315 (actual) |
| **Sonnet 5, estimated** — test set / per alert |  | $0.15913 / $0.0016238 (est.) |

Latency was measured from India over the public internet (wall-clock around each SDK call, including TLS and the first call's connection setup). Jev cost is actual input tokens x $0.042/1M, output free. Sonnet 5 cost is an **estimate**: no LLM was called; input tokens were counted with tiktoken `o200k_base` (Claude's tokenizer differs, so counts are approximate), 60 output tokens were assumed per alert, priced at $2.0/$10.0 per 1M input/output.

## Per-class precision / recall

| class | n | rules precision | rules recall | Jev precision | Jev recall | Jev gated |
|---|---|---|---|---|---|---|
| P1 | 13 | 69.2% | 69.2% | 100.0% | 100.0% | 0 |
| P2 | 23 | 90.5% | 82.6% | 81.0% | 73.9% | 6 |
| P3 | 26 | 88.9% | 92.3% | 100.0% | 46.2% | 1 |
| SUPPRESS | 36 | 89.2% | 91.7% | 79.5% | 97.2% | 1 |

## Confusion matrices (rows = truth)

**Rules-only**

| truth \ predicted | P1 | P2 | P3 | SUPPRESS |
|---|---|---|---|---|
| **P1** | 9 | 2 | 1 | 1 |
| **P2** | 0 | 19 | 2 | 2 |
| **P3** | 1 | 0 | 24 | 1 |
| **SUPPRESS** | 3 | 0 | 0 | 33 |

**Jev**

| truth \ predicted | P1 | P2 | P3 | SUPPRESS | NEEDS_HUMAN |
|---|---|---|---|---|---|
| **P1** | 13 | 0 | 0 | 0 | 0 |
| **P2** | 0 | 17 | 0 | 0 | 6 |
| **P3** | 0 | 4 | 12 | 9 | 1 |
| **SUPPRESS** | 0 | 0 | 0 | 35 | 1 |

## Jev parameters

```
{
  "noise_min": 0.6,
  "downstream_min": 0.6,
  "p1_impact_min": 2.0,
  "p1_degrading_min": 0.5,
  "urgency_confidence_min": 0.5
}
```

## Every test alert where Jev was wrong (or gated)

21 of 98. The rules-only prediction is shown for comparison.

### ALT-002 — truth **P3**, Jev said **SUPPRESS**, rules said P3

`staging email-relay p99_latency_ms 2726 (threshold 500)`  
env=staging customer_facing=False severity=warning breach=5.45 duration=170m fired_24h=2 deploy_30m=False related=[]

> email-relay v9.0.8 is failing in staging: p99_latency_ms is 2726 against a threshold of 500. The release candidate cannot be promoted until this is fixed, so the Thursday release train is blocked. No production impact.

| question | answer |
|---|---|
| user_impact | score 0.48 (conf 0.52) — No user impact 0.52, Internal users affected 0.48, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.81 |
| is_downstream_symptom | 0.14 |
| is_actively_degrading | 0.81 |
| urgency | **business_hours** (conf 0.87) — ignore 0.00, backlog 0.07, business_hours 0.90, now 0.03 |
| latency / input tokens | 421.2 ms / 750 |

### ALT-004 — truth **P3**, Jev said **P2**, rules said P3

`image-resizer TLS cert expires in 12 days`  
env=prod customer_facing=False severity=warning breach=1.17 duration=1982m fired_24h=1 deploy_30m=False related=[]

> The TLS certificate for image-resizer expires in 12 days. Automatic renewal failed with 'ACME account rate limited'. Needs a manual renewal or a fix to the renewal job this week; nothing is broken today.

| question | answer |
|---|---|
| user_impact | score 0.08 (conf 0.92) — No user impact 0.93, Internal users affected 0.07, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.06 |
| is_downstream_symptom | 0.09 |
| is_actively_degrading | 0.49 |
| urgency | **business_hours** (conf 0.74) — backlog 0.19, business_hours 0.80, now 0.01, ignore 0.00 |
| latency / input tokens | 383.4 ms / 720 |

### ALT-007 — truth **P3**, Jev said **P2**, rules said P3

`log-ingest TLS cert expires in 11 days`  
env=prod customer_facing=False severity=warning breach=1.27 duration=1984m fired_24h=1 deploy_30m=False related=[]

> The TLS certificate for log-ingest expires in 11 days. Automatic renewal failed with 'CAA record mismatch'. Needs a manual renewal or a fix to the renewal job this week; nothing is broken today.

| question | answer |
|---|---|
| user_impact | score 0.05 (conf 0.95) — No user impact 0.95, Internal users affected 0.05, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.05 |
| is_downstream_symptom | 0.09 |
| is_actively_degrading | 0.45 |
| urgency | **business_hours** (conf 0.75) — ignore 0.00, now 0.01, business_hours 0.81, backlog 0.18 |
| latency / input tokens | 337.0 ms / 718 |

### ALT-019 — truth **P2**, Jev said **NEEDS_HUMAN**, rules said P3  `hard`

`metrics-db disk 88% (threshold 80%)`  
env=prod customer_facing=False severity=warning breach=1.1 duration=900m fired_24h=1 deploy_30m=False related=[]

> Disk on the internal metrics database is at 88%. It has been climbing since a new high-cardinality label was added yesterday: growth is 4% per hour now, not the usual 0.5% per day, so it will hit 100% in about three hours. If it fills, dashboards and alerting for all internal teams stop. Someone needs to drop the label or expand the volume this afternoon.

| question | answer |
|---|---|
| user_impact | score 1.00 (conf 0.99) — No user impact 0.01, Internal users affected 0.99, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.03 |
| is_downstream_symptom | 0.08 |
| is_actively_degrading | 0.97 |
| urgency | **business_hours** (conf 0.45) — now 0.41, business_hours 0.59, backlog 0.00, ignore 0.00 |
| latency / input tokens | 323.8 ms / 765 |

### ALT-030 — truth **P3**, Jev said **SUPPRESS**, rules said P3

`staging internal-admin p99_latency_ms 3475 (threshold 1000)`  
env=staging customer_facing=False severity=warning breach=3.48 duration=168m fired_24h=1 deploy_30m=True related=[]

> QA reports that the staging deploy of internal-admin (v4.22.7) is broken since the last merge; p99_latency_ms = 3475. Release sign-off for this build is due Friday. Staging only, prod is on the previous version and healthy.

| question | answer |
|---|---|
| user_impact | score 0.92 (conf 0.92) — No user impact 0.08, Internal users affected 0.92, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.78 |
| is_downstream_symptom | 0.13 |
| is_actively_degrading | 0.87 |
| urgency | **business_hours** (conf 0.87) — ignore 0.00, backlog 0.03, now 0.06, business_hours 0.91 |
| latency / input tokens | 457.6 ms / 752 |

### ALT-032 — truth **SUPPRESS**, Jev said **NEEDS_HUMAN**, rules said P1  `hard`

`legacy-api-v1 error rate 100% (threshold 5%)`  
env=prod customer_facing=True severity=critical breach=20.0 duration=45m fired_24h=1 deploy_30m=False related=[]

> 100% of requests to /v1/orders are returning 410 Gone. The v1 API was decommissioned on Aug 30 and the only remaining caller is a retired partner cron job that was never switched off. No current customer uses v1. This alert rule was supposed to be deleted with the decommission and should be removed.

| question | answer |
|---|---|
| user_impact | score 0.09 (conf 0.91) — No user impact 0.94, Internal users affected 0.03, Some customers affected 0.03, Widespread customer impact 0.00 |
| is_noise | 0.59 |
| is_downstream_symptom | 0.08 |
| is_actively_degrading | 0.76 |
| urgency | **ignore** (conf 0.49) — business_hours 0.05, backlog 0.33, now 0.00, ignore 0.62 |
| latency / input tokens | 385.4 ms / 764 |

### ALT-045 — truth **P2**, Jev said **NEEDS_HUMAN**, rules said P2

`ci-runners cpu_percent 94 (threshold 80)`  
env=prod customer_facing=False severity=warning breach=1.18 duration=59m fired_24h=3 deploy_30m=True related=[]

> CPU on ci-runners is pinned at 94% and requests from the internal UI are timing out. Looks like a runaway reindex started by marketing ops. Internal users only; nothing customer-facing calls this service. A deploy went out about 15 minutes before this started.

| question | answer |
|---|---|
| user_impact | score 1.00 (conf 1.00) — No user impact 0.00, Internal users affected 1.00, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.08 |
| is_downstream_symptom | 0.16 |
| is_actively_degrading | 0.91 |
| urgency | **business_hours** (conf 0.46) — now 0.38, business_hours 0.60, ignore 0.00, backlog 0.02 |
| latency / input tokens | 354.2 ms / 732 |

### ALT-056 — truth **P3**, Jev said **P2**, rules said P3

`auth-service TLS cert expires in 9 days`  
env=prod customer_facing=True severity=warning breach=1.56 duration=2518m fired_24h=1 deploy_30m=False related=[]

> The TLS certificate for auth-service expires in 9 days. Automatic renewal failed with 'CAA record mismatch'. Needs a manual renewal or a fix to the renewal job this week; nothing is broken today.

| question | answer |
|---|---|
| user_impact | score 0.26 (conf 0.74) — No user impact 0.87, Internal users affected 0.01, Some customers affected 0.09, Widespread customer impact 0.03 |
| is_noise | 0.05 |
| is_downstream_symptom | 0.09 |
| is_actively_degrading | 0.48 |
| urgency | **business_hours** (conf 0.78) — now 0.01, backlog 0.16, business_hours 0.83, ignore 0.00 |
| latency / input tokens | 383.8 ms / 711 |

### ALT-066 — truth **P2**, Jev said **NEEDS_HUMAN**, rules said P3  `hard`

`staging session-cache evictions 1200/s (threshold 100/s)`  
env=staging customer_facing=False severity=warning breach=12.0 duration=15m fired_24h=1 deploy_30m=False related=[]

> Eviction rate on the staging session cache is 12x normal. The staging load test is the cause, but we found that staging is pointed at the production Redis cluster because of a misconfigured endpoint. The evictions are dropping real sessions for the internal SSO portal, so employees are being logged out. Customer sessions live in a separate cluster and are fine. Stop the load test and fix the config today.

| question | answer |
|---|---|
| user_impact | score 1.00 (conf 1.00) — No user impact 0.00, Internal users affected 1.00, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.42 |
| is_downstream_symptom | 0.16 |
| is_actively_degrading | 0.92 |
| urgency | **now** (conf 0.48) — backlog 0.00, business_hours 0.39, now 0.61, ignore 0.00 |
| latency / input tokens | 479.0 ms / 780 |

### ALT-068 — truth **P3**, Jev said **SUPPRESS**, rules said P3

`staging reporting-svc http_5xx_rate_pct 33.8 (threshold 1.0)`  
env=staging customer_facing=False severity=critical breach=33.8 duration=159m fired_24h=2 deploy_30m=True related=[]

> QA reports that the staging deploy of reporting-svc (v6.2.9) is broken since the last merge; http_5xx_rate_pct = 33.8. Release sign-off for this build is due tomorrow. Staging only, prod is on the previous version and healthy.

| question | answer |
|---|---|
| user_impact | score 0.90 (conf 0.90) — No user impact 0.10, Internal users affected 0.90, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.71 |
| is_downstream_symptom | 0.12 |
| is_actively_degrading | 0.92 |
| urgency | **now** (conf 0.44) — ignore 0.00, now 0.58, backlog 0.00, business_hours 0.42 |
| latency / input tokens | 374.6 ms / 757 |

### ALT-086 — truth **P3**, Jev said **SUPPRESS**, rules said P3

`staging data-warehouse pod_restarts_15m 27 (threshold 3)`  
env=staging customer_facing=False severity=critical breach=9.0 duration=114m fired_24h=2 deploy_30m=True related=[]

> QA reports that the staging deploy of data-warehouse (v6.18.3) is broken since the last merge; pod_restarts_15m = 27. Release sign-off for this build is due tomorrow. Staging only, prod is on the previous version and healthy.

| question | answer |
|---|---|
| user_impact | score 0.95 (conf 0.95) — No user impact 0.05, Internal users affected 0.95, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.71 |
| is_downstream_symptom | 0.16 |
| is_actively_degrading | 0.93 |
| urgency | **now** (conf 0.41) — business_hours 0.44, now 0.56, backlog 0.00, ignore 0.00 |
| latency / input tokens | 332.2 ms / 753 |

### ALT-103 — truth **P3**, Jev said **SUPPRESS**, rules said P3

`staging reporting-svc p99_latency_ms 5718 (threshold 1000)`  
env=staging customer_facing=False severity=warning breach=5.72 duration=221m fired_24h=2 deploy_30m=True related=[]

> reporting-svc v2.17.9 is failing in staging: p99_latency_ms is 5718 against a threshold of 1000. The release candidate cannot be promoted until this is fixed, so the end-of-sprint release train is blocked. No production impact.

| question | answer |
|---|---|
| user_impact | score 0.55 (conf 0.55) — No user impact 0.45, Internal users affected 0.55, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.78 |
| is_downstream_symptom | 0.14 |
| is_actively_degrading | 0.86 |
| urgency | **business_hours** (conf 0.79) — ignore 0.00, now 0.10, backlog 0.06, business_hours 0.84 |
| latency / input tokens | 381.7 ms / 763 |

### ALT-109 — truth **P3**, Jev said **SUPPRESS**, rules said P3

`staging storefront-web pod_restarts_15m 27 (threshold 3)`  
env=staging customer_facing=True severity=critical breach=9.0 duration=230m fired_24h=3 deploy_30m=False related=[]

> storefront-web v9.24.6 is failing in staging: pod_restarts_15m is 27 against a threshold of 3. The release candidate cannot be promoted until this is fixed, so the Monday release train is blocked. No production impact.

| question | answer |
|---|---|
| user_impact | score 0.54 (conf 0.46) — No user impact 0.49, Internal users affected 0.49, Some customers affected 0.02, Widespread customer impact 0.00 |
| is_noise | 0.63 |
| is_downstream_symptom | 0.16 |
| is_actively_degrading | 0.89 |
| urgency | **business_hours** (conf 0.41) — ignore 0.00, now 0.43, backlog 0.02, business_hours 0.55 |
| latency / input tokens | 372.3 ms / 743 |

### ALT-111 — truth **P3**, Jev said **NEEDS_HUMAN**, rules said P1  `hard`

`search-api error rate 9.5% (threshold 2%)`  
env=prod customer_facing=True severity=critical breach=4.75 duration=22m fired_24h=1 deploy_30m=False related=[]

> search-api error rate is 9.5%. All of the errors are 400s from a single IP sending a malformed 'sort' parameter at about 200 rps; the WAF team has already rate-limited that IP. Error rate for everyone else is 0.1%, unchanged, and no customers are affected. Follow-up: add a permanent WAF rule and exclude 400s from this alert's query.

| question | answer |
|---|---|
| user_impact | score 0.01 (conf 0.99) — No user impact 1.00, Internal users affected 0.00, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.25 |
| is_downstream_symptom | 0.09 |
| is_actively_degrading | 0.42 |
| urgency | **backlog** (conf 0.36) — ignore 0.31, business_hours 0.16, now 0.01, backlog 0.52 |
| latency / input tokens | 378.5 ms / 770 |

### ALT-114 — truth **P2**, Jev said **NEEDS_HUMAN**, rules said SUPPRESS  `hard`

`internal-admin error rate 4.1% (threshold 1%)`  
env=prod customer_facing=False severity=warning breach=4.1 duration=6m fired_24h=11 deploy_30m=True related=[]

> internal-admin error rate normally trips this alert a few times a day from the noisy bulk-export page, which is why the count is high. This time is different: the errors are a new NullPointerException in the refund approval flow that started right after the 14:05 deploy, and the ops team cannot approve refunds at all. Customers are not affected yet, but the refund backlog needs clearing today.

| question | answer |
|---|---|
| user_impact | score 1.02 (conf 0.97) — No user impact 0.00, Internal users affected 0.97, Some customers affected 0.03, Widespread customer impact 0.00 |
| is_noise | 0.05 |
| is_downstream_symptom | 0.11 |
| is_actively_degrading | 0.93 |
| urgency | **now** (conf 0.36) — ignore 0.00, now 0.52, backlog 0.00, business_hours 0.48 |
| latency / input tokens | 321.6 ms / 765 |

### ALT-117 — truth **P3**, Jev said **SUPPRESS**, rules said P3

`staging recommendation-svc p99_latency_ms 5646 (threshold 1000)`  
env=staging customer_facing=True severity=warning breach=5.65 duration=86m fired_24h=1 deploy_30m=True related=[]

> QA reports that the staging deploy of recommendation-svc (v3.26.8) is broken since the last merge; p99_latency_ms = 5646. Release sign-off for this build is due Friday. Staging only, prod is on the previous version and healthy.

| question | answer |
|---|---|
| user_impact | score 0.93 (conf 0.86) — No user impact 0.10, Internal users affected 0.87, Some customers affected 0.03, Widespread customer impact 0.00 |
| is_noise | 0.73 |
| is_downstream_symptom | 0.12 |
| is_actively_degrading | 0.89 |
| urgency | **business_hours** (conf 0.82) — backlog 0.04, now 0.09, ignore 0.00, business_hours 0.87 |
| latency / input tokens | 351.9 ms / 761 |

### ALT-120 — truth **P3**, Jev said **SUPPRESS**, rules said P3

`staging feature-flag-svc pod_restarts_15m 11 (threshold 3)`  
env=staging customer_facing=False severity=critical breach=3.67 duration=83m fired_24h=1 deploy_30m=True related=[]

> QA reports that the staging deploy of feature-flag-svc (v4.16.6) is broken since the last merge; pod_restarts_15m = 11. Release sign-off for this build is due tomorrow. Staging only, prod is on the previous version and healthy.

| question | answer |
|---|---|
| user_impact | score 0.92 (conf 0.92) — No user impact 0.08, Internal users affected 0.92, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.68 |
| is_downstream_symptom | 0.13 |
| is_actively_degrading | 0.92 |
| urgency | **now** (conf 0.35) — business_hours 0.48, now 0.52, backlog 0.00, ignore 0.00 |
| latency / input tokens | 385.4 ms / 755 |

### ALT-121 — truth **P2**, Jev said **NEEDS_HUMAN**, rules said P2

`feature-flag-svc http_5xx_rate_pct 14.6 (threshold 1.0)`  
env=prod customer_facing=False severity=warning breach=14.6 duration=20m fired_24h=2 deploy_30m=True related=[]

> feature-flag-svc is returning 500s on about 14.6% of requests, mostly on the refund approval page. The support team is working around it via the database console for now. Customers are not affected; this is an internal tool. Nothing was deployed recently; looks like an infrastructure issue.

| question | answer |
|---|---|
| user_impact | score 0.95 (conf 0.95) — No user impact 0.05, Internal users affected 0.95, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.10 |
| is_downstream_symptom | 0.19 |
| is_actively_degrading | 0.86 |
| urgency | **business_hours** (conf 0.46) — now 0.37, business_hours 0.59, backlog 0.03, ignore 0.01 |
| latency / input tokens | 335.9 ms / 762 |

### ALT-127 — truth **P3**, Jev said **SUPPRESS**, rules said P3

`staging auth-service pod_restarts_15m 13 (threshold 3)`  
env=staging customer_facing=True severity=critical breach=4.33 duration=208m fired_24h=2 deploy_30m=True related=[]

> auth-service v8.24.5 is failing in staging: pod_restarts_15m is 13 against a threshold of 3. The release candidate cannot be promoted until this is fixed, so the Monday release train is blocked. No production impact.

| question | answer |
|---|---|
| user_impact | score 0.51 (conf 0.49) — No user impact 0.53, Internal users affected 0.44, Some customers affected 0.03, Widespread customer impact 0.00 |
| is_noise | 0.64 |
| is_downstream_symptom | 0.14 |
| is_actively_degrading | 0.90 |
| urgency | **business_hours** (conf 0.38) — ignore 0.00, business_hours 0.54, now 0.45, backlog 0.01 |
| latency / input tokens | 358.5 ms / 737 |

### ALT-129 — truth **P3**, Jev said **P2**, rules said P3

`cdn-edge TLS cert expires in 7 days`  
env=prod customer_facing=True severity=warning breach=2.0 duration=1561m fired_24h=1 deploy_30m=False related=[]

> The TLS certificate for cdn-edge expires in 7 days. Automatic renewal failed with 'ACME account rate limited'. Needs a manual renewal or a fix to the renewal job this week; nothing is broken today.

| question | answer |
|---|---|
| user_impact | score 0.39 (conf 0.61) — No user impact 0.83, Internal users affected 0.00, Some customers affected 0.12, Widespread customer impact 0.05 |
| is_noise | 0.05 |
| is_downstream_symptom | 0.11 |
| is_actively_degrading | 0.48 |
| urgency | **business_hours** (conf 0.79) — backlog 0.14, now 0.02, ignore 0.00, business_hours 0.84 |
| latency / input tokens | 366.8 ms / 714 |

### ALT-144 — truth **P2**, Jev said **NEEDS_HUMAN**, rules said P2

`data-warehouse cpu_percent 94 (threshold 80)`  
env=prod customer_facing=False severity=warning breach=1.18 duration=61m fired_24h=1 deploy_30m=False related=[]

> CPU on data-warehouse is pinned at 94% and requests from the internal UI are timing out. Looks like a runaway reindex started by finance. Internal users only; nothing customer-facing calls this service. Nothing was deployed recently; looks like an infrastructure issue.

| question | answer |
|---|---|
| user_impact | score 1.00 (conf 1.00) — No user impact 0.00, Internal users affected 1.00, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.05 |
| is_downstream_symptom | 0.16 |
| is_actively_degrading | 0.90 |
| urgency | **business_hours** (conf 0.47) — ignore 0.00, now 0.38, business_hours 0.61, backlog 0.01 |
| latency / input tokens | 359.5 ms / 732 |

