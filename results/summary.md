# Alert triage benchmark — test set results

Generated 2026-09-23T12:32:22+00:00 from `rules_20260923T123222Z.json`, `jev_20260923T122657Z.json`, `cost_20260923T123222Z.json`.  
Test set: 98 alerts (16 hard). Jev model (from the response `model` field): `jev-1.13.0`. Thresholds for both systems were tuned on the separate tune split only.

## Headline

| metric | rules-only | Jev |
|---|---|---|
| overall accuracy (strict; NEEDS_HUMAN counts as wrong) | 86.7% | 86.7% |
| accuracy on hard cases (n=16) | 18.8% | 100.0% |
| accuracy on easy cases (n=82) | 100.0% | 84.1% |
| **P1 recall** (missing a real P1 is the costliest error) | 69.2% | 100.0% (0 P1 gated) |
| sent to NEEDS_HUMAN | — | 0 / 98 |
| accuracy on the rest (non-gated) | — | 86.7% (n=98) |
| latency p50 / p95 | ~0 ms (local if/else) | 469 ms / 701 ms |
| cost, test set (98 alerts) | $0 | $0.00313 (actual) |
| cost per alert | $0 | $0.0000320 (actual) |
| **Sonnet 5, estimated** — test set / per alert |  | $0.15913 / $0.0016238 (est.) |

Latency was measured from India over the public internet (wall-clock around each SDK call, including TLS and the first call's connection setup). Jev cost is actual input tokens x $0.042/1M, output free. Sonnet 5 cost is an **estimate**: no LLM was called; input tokens were counted with tiktoken `o200k_base` (Claude's tokenizer differs, so counts are approximate), 60 output tokens were assumed per alert, priced at $2.0/$10.0 per 1M input/output.

## Per-class precision / recall

| class | n | rules precision | rules recall | Jev precision | Jev recall | Jev gated |
|---|---|---|---|---|---|---|
| P1 | 13 | 69.2% | 69.2% | 100.0% | 100.0% | 0 |
| P2 | 23 | 90.5% | 82.6% | 63.9% | 100.0% | 0 |
| P3 | 26 | 88.9% | 92.3% | 100.0% | 50.0% | 0 |
| SUPPRESS | 36 | 89.2% | 91.7% | 100.0% | 100.0% | 0 |

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
| **P2** | 0 | 23 | 0 | 0 | 0 |
| **P3** | 0 | 13 | 13 | 0 | 0 |
| **SUPPRESS** | 0 | 0 | 0 | 36 | 0 |

## Jev parameters

```
{
  "noise_min": 0.6,
  "downstream_min": 0.6,
  "p1_impact_min": 2.0,
  "p1_degrading_min": 0.5,
  "urgency_confidence_min": 0.0
}
```

## Every test alert where Jev was wrong (or gated)

13 of 98. The rules-only prediction is shown for comparison.

### ALT-002 — truth **P3**, Jev said **P2**, rules said P3

`staging email-relay p99_latency_ms 2726 (threshold 500)`  
env=staging customer_facing=False severity=warning breach=5.45 duration=170m fired_24h=2 deploy_30m=False related=[]

> email-relay v9.0.8 is failing in staging: p99_latency_ms is 2726 against a threshold of 500. The release candidate cannot be promoted until this is fixed, so the Thursday release train is blocked. No production impact.

| question | answer |
|---|---|
| user_impact | score 0.47 (conf 0.53) — No user impact 0.53, Internal users affected 0.47, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.24 |
| is_downstream_symptom | 0.13 |
| is_actively_degrading | 0.81 |
| urgency | **business_hours** (conf 0.84) — backlog 0.09, now 0.03, ignore 0.00, business_hours 0.88 |
| latency / input tokens | 415.0 ms / 761 |

### ALT-004 — truth **P3**, Jev said **P2**, rules said P3

`image-resizer TLS cert expires in 12 days`  
env=prod customer_facing=False severity=warning breach=1.17 duration=1982m fired_24h=1 deploy_30m=False related=[]

> The TLS certificate for image-resizer expires in 12 days. Automatic renewal failed with 'ACME account rate limited'. Needs a manual renewal or a fix to the renewal job this week; nothing is broken today.

| question | answer |
|---|---|
| user_impact | score 0.08 (conf 0.92) — No user impact 0.93, Internal users affected 0.07, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.05 |
| is_downstream_symptom | 0.10 |
| is_actively_degrading | 0.48 |
| urgency | **business_hours** (conf 0.73) — backlog 0.20, business_hours 0.79, now 0.01, ignore 0.00 |
| latency / input tokens | 496.2 ms / 731 |

### ALT-007 — truth **P3**, Jev said **P2**, rules said P3

`log-ingest TLS cert expires in 11 days`  
env=prod customer_facing=False severity=warning breach=1.27 duration=1984m fired_24h=1 deploy_30m=False related=[]

> The TLS certificate for log-ingest expires in 11 days. Automatic renewal failed with 'CAA record mismatch'. Needs a manual renewal or a fix to the renewal job this week; nothing is broken today.

| question | answer |
|---|---|
| user_impact | score 0.05 (conf 0.95) — No user impact 0.95, Internal users affected 0.05, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.06 |
| is_downstream_symptom | 0.08 |
| is_actively_degrading | 0.47 |
| urgency | **business_hours** (conf 0.78) — now 0.01, business_hours 0.84, ignore 0.00, backlog 0.15 |
| latency / input tokens | 456.7 ms / 729 |

### ALT-030 — truth **P3**, Jev said **P2**, rules said P3

`staging internal-admin p99_latency_ms 3475 (threshold 1000)`  
env=staging customer_facing=False severity=warning breach=3.48 duration=168m fired_24h=1 deploy_30m=True related=[]

> QA reports that the staging deploy of internal-admin (v4.22.7) is broken since the last merge; p99_latency_ms = 3475. Release sign-off for this build is due Friday. Staging only, prod is on the previous version and healthy.

| question | answer |
|---|---|
| user_impact | score 0.90 (conf 0.89) — No user impact 0.11, Internal users affected 0.89, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.19 |
| is_downstream_symptom | 0.13 |
| is_actively_degrading | 0.86 |
| urgency | **business_hours** (conf 0.88) — business_hours 0.91, ignore 0.00, now 0.05, backlog 0.04 |
| latency / input tokens | 458.1 ms / 763 |

### ALT-056 — truth **P3**, Jev said **P2**, rules said P3

`auth-service TLS cert expires in 9 days`  
env=prod customer_facing=True severity=warning breach=1.56 duration=2518m fired_24h=1 deploy_30m=False related=[]

> The TLS certificate for auth-service expires in 9 days. Automatic renewal failed with 'CAA record mismatch'. Needs a manual renewal or a fix to the renewal job this week; nothing is broken today.

| question | answer |
|---|---|
| user_impact | score 0.36 (conf 0.64) — No user impact 0.83, Internal users affected 0.01, Some customers affected 0.12, Widespread customer impact 0.04 |
| is_noise | 0.05 |
| is_downstream_symptom | 0.09 |
| is_actively_degrading | 0.47 |
| urgency | **business_hours** (conf 0.78) — backlog 0.15, business_hours 0.84, now 0.01, ignore 0.00 |
| latency / input tokens | 889.3 ms / 722 |

### ALT-068 — truth **P3**, Jev said **P2**, rules said P3

`staging reporting-svc http_5xx_rate_pct 33.8 (threshold 1.0)`  
env=staging customer_facing=False severity=critical breach=33.8 duration=159m fired_24h=2 deploy_30m=True related=[]

> QA reports that the staging deploy of reporting-svc (v6.2.9) is broken since the last merge; http_5xx_rate_pct = 33.8. Release sign-off for this build is due tomorrow. Staging only, prod is on the previous version and healthy.

| question | answer |
|---|---|
| user_impact | score 0.91 (conf 0.91) — No user impact 0.09, Internal users affected 0.91, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.16 |
| is_downstream_symptom | 0.12 |
| is_actively_degrading | 0.92 |
| urgency | **now** (conf 0.47) — now 0.61, ignore 0.00, backlog 0.00, business_hours 0.39 |
| latency / input tokens | 858.8 ms / 768 |

### ALT-086 — truth **P3**, Jev said **P2**, rules said P3

`staging data-warehouse pod_restarts_15m 27 (threshold 3)`  
env=staging customer_facing=False severity=critical breach=9.0 duration=114m fired_24h=2 deploy_30m=True related=[]

> QA reports that the staging deploy of data-warehouse (v6.18.3) is broken since the last merge; pod_restarts_15m = 27. Release sign-off for this build is due tomorrow. Staging only, prod is on the previous version and healthy.

| question | answer |
|---|---|
| user_impact | score 0.94 (conf 0.94) — No user impact 0.06, Internal users affected 0.94, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.21 |
| is_downstream_symptom | 0.15 |
| is_actively_degrading | 0.93 |
| urgency | **now** (conf 0.43) — ignore 0.00, business_hours 0.43, backlog 0.00, now 0.57 |
| latency / input tokens | 409.5 ms / 764 |

### ALT-103 — truth **P3**, Jev said **P2**, rules said P3

`staging reporting-svc p99_latency_ms 5718 (threshold 1000)`  
env=staging customer_facing=False severity=warning breach=5.72 duration=221m fired_24h=2 deploy_30m=True related=[]

> reporting-svc v2.17.9 is failing in staging: p99_latency_ms is 5718 against a threshold of 1000. The release candidate cannot be promoted until this is fixed, so the end-of-sprint release train is blocked. No production impact.

| question | answer |
|---|---|
| user_impact | score 0.55 (conf 0.55) — No user impact 0.45, Internal users affected 0.55, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.23 |
| is_downstream_symptom | 0.14 |
| is_actively_degrading | 0.85 |
| urgency | **business_hours** (conf 0.83) — business_hours 0.88, now 0.05, backlog 0.07, ignore 0.00 |
| latency / input tokens | 577.1 ms / 774 |

### ALT-109 — truth **P3**, Jev said **P2**, rules said P3

`staging storefront-web pod_restarts_15m 27 (threshold 3)`  
env=staging customer_facing=True severity=critical breach=9.0 duration=230m fired_24h=3 deploy_30m=False related=[]

> storefront-web v9.24.6 is failing in staging: pod_restarts_15m is 27 against a threshold of 3. The release candidate cannot be promoted until this is fixed, so the Monday release train is blocked. No production impact.

| question | answer |
|---|---|
| user_impact | score 0.51 (conf 0.49) — No user impact 0.54, Internal users affected 0.43, Some customers affected 0.03, Widespread customer impact 0.00 |
| is_noise | 0.18 |
| is_downstream_symptom | 0.14 |
| is_actively_degrading | 0.89 |
| urgency | **business_hours** (conf 0.46) — now 0.38, ignore 0.00, backlog 0.02, business_hours 0.60 |
| latency / input tokens | 469.7 ms / 754 |

### ALT-117 — truth **P3**, Jev said **P2**, rules said P3

`staging recommendation-svc p99_latency_ms 5646 (threshold 1000)`  
env=staging customer_facing=True severity=warning breach=5.65 duration=86m fired_24h=1 deploy_30m=True related=[]

> QA reports that the staging deploy of recommendation-svc (v3.26.8) is broken since the last merge; p99_latency_ms = 5646. Release sign-off for this build is due Friday. Staging only, prod is on the previous version and healthy.

| question | answer |
|---|---|
| user_impact | score 0.97 (conf 0.88) — No user impact 0.08, Internal users affected 0.88, Some customers affected 0.04, Widespread customer impact 0.00 |
| is_noise | 0.18 |
| is_downstream_symptom | 0.13 |
| is_actively_degrading | 0.89 |
| urgency | **business_hours** (conf 0.83) — backlog 0.04, business_hours 0.86, ignore 0.01, now 0.09 |
| latency / input tokens | 742.9 ms / 772 |

### ALT-120 — truth **P3**, Jev said **P2**, rules said P3

`staging feature-flag-svc pod_restarts_15m 11 (threshold 3)`  
env=staging customer_facing=False severity=critical breach=3.67 duration=83m fired_24h=1 deploy_30m=True related=[]

> QA reports that the staging deploy of feature-flag-svc (v4.16.6) is broken since the last merge; pod_restarts_15m = 11. Release sign-off for this build is due tomorrow. Staging only, prod is on the previous version and healthy.

| question | answer |
|---|---|
| user_impact | score 0.89 (conf 0.89) — No user impact 0.11, Internal users affected 0.89, Some customers affected 0.00, Widespread customer impact 0.00 |
| is_noise | 0.18 |
| is_downstream_symptom | 0.13 |
| is_actively_degrading | 0.92 |
| urgency | **business_hours** (conf 0.42) — business_hours 0.57, ignore 0.00, now 0.43, backlog 0.00 |
| latency / input tokens | 462.0 ms / 766 |

### ALT-127 — truth **P3**, Jev said **P2**, rules said P3

`staging auth-service pod_restarts_15m 13 (threshold 3)`  
env=staging customer_facing=True severity=critical breach=4.33 duration=208m fired_24h=2 deploy_30m=True related=[]

> auth-service v8.24.5 is failing in staging: pod_restarts_15m is 13 against a threshold of 3. The release candidate cannot be promoted until this is fixed, so the Monday release train is blocked. No production impact.

| question | answer |
|---|---|
| user_impact | score 0.55 (conf 0.53) — No user impact 0.46, Internal users affected 0.53, Some customers affected 0.01, Widespread customer impact 0.00 |
| is_noise | 0.17 |
| is_downstream_symptom | 0.16 |
| is_actively_degrading | 0.89 |
| urgency | **business_hours** (conf 0.36) — ignore 0.00, business_hours 0.52, now 0.47, backlog 0.01 |
| latency / input tokens | 408.3 ms / 748 |

### ALT-129 — truth **P3**, Jev said **P2**, rules said P3

`cdn-edge TLS cert expires in 7 days`  
env=prod customer_facing=True severity=warning breach=2.0 duration=1561m fired_24h=1 deploy_30m=False related=[]

> The TLS certificate for cdn-edge expires in 7 days. Automatic renewal failed with 'ACME account rate limited'. Needs a manual renewal or a fix to the renewal job this week; nothing is broken today.

| question | answer |
|---|---|
| user_impact | score 0.36 (conf 0.64) — No user impact 0.85, Internal users affected 0.00, Some customers affected 0.10, Widespread customer impact 0.05 |
| is_noise | 0.05 |
| is_downstream_symptom | 0.10 |
| is_actively_degrading | 0.49 |
| urgency | **business_hours** (conf 0.80) — backlog 0.14, business_hours 0.84, now 0.02, ignore 0.00 |
| latency / input tokens | 500.3 ms / 725 |

