# What this benchmark found

A plain-language companion to [`summary.md`](summary.md), which holds the full tables.
Generated from the same run files; every number below is computed, not typed.

## The question

Every monitoring alert arrives with two kinds of information: **structured fields** (which environment, how far over threshold, how many times it fired) and a **free-text description** written by whoever set the alert up, or appended by whoever looked at it last.

Traditional alert routing reads the fields, because code can compare numbers. This benchmark asks what the description is worth: two systems classify the same 98 alerts into P1 / P2 / P3 / SUPPRESS, scored against the same hand-written answer key.

- **rules-only** — nine `if` statements over the structured fields. Never reads the description.
- **Jev** — answers five narrow questions about the alert *including* its description, and returns a probability for each. The label is then derived in code.

## The headline: a tie that hides everything interesting

| | rules-only | Jev |
|---|---|---|
| overall accuracy | 86.7% | 86.7% |
| on the 82 **easy** alerts | 100.0% | 84.1% |
| on the 16 **hard** alerts | 18.8% | 100.0% |
| real P1s caught | 69.2% | 100.0% |
| real incidents silently suppressed | 3 | 0 |

The overall numbers are nearly identical and tell you almost nothing. The split between easy and hard is the actual result.

**Easy alerts** are ones where the fields and the description agree — a prod customer-facing service is badly over threshold and the text says so. The rules get 100% of these right, because that is exactly what they were built for.

**Hard alerts** are ones where the fields are *misleading* and only the description resolves it. Rules get 18.8%. Jev gets 100.0%.

## Why the rules hit a ceiling

The rules are not badly written — their thresholds were grid-searched on a separate tune split, so they are the best this rule structure can do. The ceiling is structural: **the information needed is not in the fields they read.**

The cost is concrete. The rules silently routed 3 real P1/P2 incidents to SUPPRESS, where nobody would ever see them, and missed 4 of 13 real P1s. Jev suppressed 0.

## What the description said that the fields did not

4 of the alerts where the rules were wrong and Jev was right. In each, the numbers point one way and the sentence points the other.

### ALT-013 — the fields said **SUPPRESS**, the answer was **P1**

> payments-api 5xx rate 6% (threshold 1%)

**What the structured fields said:** `env=prod` · `customer_facing=True` · `fired_count_24h=18` · `breach_ratio=6.0x` · `duration_minutes=8`

**What the description said:**

> This alert fires every night around 02:00 when the settlement batch retries, and the team normally ignores it, which explains the 18 firings. This one is at 14:20 with a signature we have never seen: TLS handshake failures to the card processor on every request. Card payments are failing for all customers right now.

**Rules read only the fields and answered SUPPRESS.** Jev read the description and answered **P1**, via:

| question | Jev's answer |
|---|---|
| is this noise? | 0.05 |
| who is affected? | score 3.00 (100% confident) |
| is it getting worse? | 0.94 |
| how urgent? | **now** (100% confident) |

### ALT-003 — the fields said **P1**, the answer was **SUPPRESS**

> search-api error rate 12% (threshold 2%)

**What the structured fields said:** `env=prod` · `customer_facing=True` · `fired_count_24h=1` · `breach_ratio=6.0x` · `duration_minutes=18`

**What the description said:**

> Error rate on search-api is 12%, but all of the errors come from the perf-test tenant. The performance team announced a scheduled load test in #ops at 13:00 and is deliberately sending malformed queries to exercise the validation path. Error rate for real tenants is 0.1%. The test ends at 15:00.

**Rules read only the fields and answered P1.** Jev read the description and answered **SUPPRESS**, via:

| question | Jev's answer |
|---|---|
| is this noise? | 0.89 |
| who is affected? | score 0.29 (71% confident) |
| is it getting worse? | 0.59 |
| how urgent? | **ignore** (96% confident) |

### ALT-010 — the fields said **P3**, the answer was **P1**

> staging auth-service login failure rate 85% (threshold 5%)

**What the structured fields said:** `env=staging` · `customer_facing=True` · `fired_count_24h=1` · `breach_ratio=17.0x` · `duration_minutes=20`

**What the description said:**

> The env label on this alert says staging, but the cluster is prod-eu: yesterday's label migration rewrote the environment tag on the EU cluster and it has not been fixed yet. 85% of logins in the EU region have been failing since the 09:10 deploy and EU customers are reporting that they cannot sign in. Treat this as production.

**Rules read only the fields and answered P3.** Jev read the description and answered **P1**, via:

| question | Jev's answer |
|---|---|
| is this noise? | 0.04 |
| who is affected? | score 2.80 (80% confident) |
| is it getting worse? | 0.95 |
| how urgent? | **now** (100% confident) |

### ALT-032 — the fields said **P1**, the answer was **SUPPRESS**

> legacy-api-v1 error rate 100% (threshold 5%)

**What the structured fields said:** `env=prod` · `customer_facing=True` · `fired_count_24h=1` · `breach_ratio=20.0x` · `duration_minutes=45`

**What the description said:**

> 100% of requests to /v1/orders are returning 410 Gone. The v1 API was decommissioned on Aug 30 and the only remaining caller is a retired partner cron job that was never switched off. No current customer uses v1. This alert rule was supposed to be deleted with the decommission and should be removed.

**Rules read only the fields and answered P1.** Jev read the description and answered **SUPPRESS**, via:

| question | Jev's answer |
|---|---|
| is this noise? | 0.58 |
| who is affected? | score 0.07 (93% confident) |
| is it getting worse? | 0.74 |
| how urgent? | **ignore** (39% confident) |

## Where Jev still disagrees

13 of 98 alerts are still wrong. They are not scattered — every one is **P3 → P2**.

These are alerts the answer key calls backlog work and Jev calls same-day work: certificates expiring in a week, latency creeping up, pods restarting slowly. Reasonable people disagree about that boundary, and the disagreement runs one way only — Jev over-prioritises, never under-prioritises. Nothing real gets dropped.

## What it costs

| | rules-only | Jev |
|---|---|---|
| time per alert | microseconds, local | ~0.5 s, one network call |
| money per alert | $0 | about three cents per thousand alerts |
| needs network access | no | yes |

Whether that trade is worth it depends on what a missed P1 costs, which no benchmark can tell you.

---

Full tables, confusion matrices, per-class precision and recall, and every error with its raw answers: [`summary.md`](summary.md).
