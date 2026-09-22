# Dataset

150 synthetic monitoring alerts with a hand-defined ground truth. Regenerate
with `python -m triage.dataset.generate`; the output is byte-identical on
every run (fixed seed, ordered random draws).

## Files

| File | Content |
|---|---|
| `data/alerts.json` | list of alert records; **no label field** |
| `data/labels.json` | `{alert_id: {"label": "P1"|"P2"|"P3"|"SUPPRESS", "hard": bool}}` |
| `data/split.json` | `{"tune": [ids], "test": [ids]}` |

## Alert record

| Field | Type | Meaning |
|---|---|---|
| `id` | `ALT-001`… | Assigned after shuffling, so it carries no label information |
| `alertname` | str | Prometheus-style rule name, e.g. `HighErrorRate` |
| `service` | str | Owning service |
| `env` | `prod` / `staging` / `dev` | As labelled by the alert router (can be wrong in hard cases) |
| `customer_facing` | bool | Whether the service serves end users directly |
| `severity_tag` | `critical` / `warning` / `info` | Static severity on the rule |
| `summary` | str | One-line title |
| `description` | str | 2–4 sentences as an on-call engineer or log excerpt would write |
| `metric`, `value`, `threshold` | str, number, number | What breached |
| `breach_ratio` | float | `value/threshold`, or `threshold/value` for lower-is-worse metrics (`cert_expiry_days`, `available_replicas`); ≥ 1.0 means breached |
| `duration_minutes` | int | How long the condition has held for this firing |
| `fired_count_24h` | int | Firings of this rule in the last 24 h (1 = first today) |
| `recent_deploy_30m` | bool | A deploy of this service in the last 30 min |
| `related_alerts_firing` | list[str] | Alerts the router grouped with this one, as `"<service>: <alertname> [<severity>]"` |
| `runbook_url` | str | Derived from service and alertname |

`breach_ratio` and `runbook_url` are always derived by `make_alert()`; they
are never hand-set.

## Label rules

| Label | Rule |
|---|---|
| **P1** | prod, customer-facing, actively degrading user experience, not flapping |
| **P2** | prod but internal-only impact, **or** customer-facing with a small / short breach |
| **P3** | real but non-urgent: capacity trends, cert expiry, staging issues blocking a release |
| **SUPPRESS** | flapping, dev environment, or a duplicate symptom of an already-firing P1 |

## Composition

| | P1 | P2 | P3 | SUPPRESS | total |
|---|---|---|---|---|---|
| easy (templated) | 14 | 29 | 35 | 47 | 125 |
| hard (hand-written) | 6 | 6 | 5 | 8 | 25 |
| **all** | 20 | 35 | 40 | 55 | 150 |

### Easy cases

Generated from scenario templates in `triage.dataset.scenarios`, one
function per situation. Services, values, timings and phrasing are drawn
from a seeded RNG; the structured fields are always consistent with the
label. Exact duplicate descriptions are re-drawn.

| Label | Scenarios (weight) |
|---|---|
| P1 | 5xx spike with customer reports (7), p99 several × SLO (4), replicas down (3) |
| P2 | internal-service problem (14), customer-facing small breach 1.05–1.3× (10), recovered spike (5) |
| P3 | capacity trend, days from full (15), staging blocking a release (13), cert expiring in 6–13 days (7) |
| SUPPRESS | dev cluster (15), flapping 8–40×/day (17), downstream duplicate with upstream `[critical]` (15) |

Because these fields agree with the label by construction, a rules-only
triager scores near 100 % on easy cases. That is intended: the baseline is a
ceiling on the easy cases, and the benchmark asks whether a model can win
the hard cases without giving the easy ones up.

### Hard cases

25 alerts in `triage.dataset.hard_cases` where the structured fields point
one way and the description points the other. They are marked
`"hard": true` in `labels.json` so accuracy can be reported on them
separately. The patterns:

| Structured fields say | Description says | Label |
|---|---|---|
| critical, prod, customer-facing health check failing | synthetic prober only, no user traffic, network team already fixing | SUPPRESS |
| same, but the deploy renamed the endpoint and the probe needs updating | no user impact, fix next working day | P3 |
| critical 5xx / latency / queue on a customer-facing service | every error is from an upstream service that is already paged (INC-…) | SUPPRESS |
| critical error rate | traffic is a scheduled load test / a single bot IP already rate-limited / a decommissioned endpoint | SUPPRESS / P3 |
| `env: prod` | cluster is actually the chaos-experiment mirror | SUPPRESS |
| `env: staging`, critical | planned maintenance window announced in advance | SUPPRESS |
| `env: staging`, critical | the label is wrong; this is the prod-eu cluster and EU customers cannot log in | P1 |
| `env: dev` | shared CI runners starving tomorrow's prod release / external partner sandbox failing | P3 / P2 |
| `fired_count_24h` 11–18 (looks flapping) | this occurrence has a new error signature | P1 / P2 |
| `severity: warning`, breach only 1.15× | support tickets pouring in; the metric under-counts because timeouts never reach the service | P1 |
| `customer_facing: false` | the internal service is the storefront's only source of product data; customers see empty pages | P1 |
| `severity: info`, 4 restarts | OOM kills rotating through every pod, ~40 % capacity down, login failures on the status page | P1 |
| `related_alerts_firing` has a `[critical]` upstream | not the same incident: that one was mitigated 20 min ago, this is a new root cause | P1 / P2 |
| internal disk 88 %, long duration (looks like a trend) | growth is 4 %/hour, full in ~3 hours, all dashboards stop | P2 |
| internal disk 94 %, critical | archive node off the request path, retention job Sunday reclaims it | P3 |

A handful of these are judgment calls (e.g. the partner sandbox as P2 vs
P3, the metrics DB as P2 vs P1). They were reviewed as acceptable for the
purpose of the benchmark; relabelling is a one-line change followed by
`make data` and a re-run of the downstream stages.

## Split

52 tune / 98 test, stratified by `(label, hard)`: each stratum contributes
`round(n / 3)` alerts to tune. Rules thresholds and Jev combination
thresholds are tuned on the tune split only; every reported number is on
the test split.

| split | P1 | P2 | P3 | SUPPRESS | n |
|---|---|---|---|---|---|
| tune | 7 (2 hard) | 12 (2) | 14 (2) | 19 (3) | 52 |
| test | 13 (4) | 23 (4) | 26 (3) | 36 (5) | 98 |

## Limitations

- Synthetic. Descriptions are written to be realistic but are shorter and
  cleaner than real alert text; there is no OCR noise, no half-finished
  sentences, no ambiguity about which incident channel is meant.
- The easy/hard dichotomy is by construction; real alert streams have a
  continuum.
- 150 alerts is small. Differences of one or two alerts on the hard subset
  (n = 16 in test) are within noise, so results are reported as counts as well
  as percentages.
- Only English, only one alerting convention.
