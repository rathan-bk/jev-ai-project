# Methodology

How the numbers in `results/summary.md` are produced, and what they do and
do not mean.

## Systems under test

### Rules-only baseline (`triage.rules`)

Plain if/else over the structured fields; `summary` and `description` are
never read. First matching rule wins:

1. `env == dev` → SUPPRESS
2. `fired_count_24h ≥ flapping_min_fired` → SUPPRESS
3. any `[critical]` in `related_alerts_firing` → SUPPRESS
4. `env == staging` → P3
5. `duration_minutes ≥ trend_min_duration` → P3
6. not `customer_facing` → P2
7. `breach_ratio ≤ small_breach_max` or `duration_minutes ≤ short_duration_max` → P2
8. otherwise → P1

The four thresholds are a frozen `RuleThresholds` dataclass; `--tune` grid
searches 384 combinations on the tune split and prints every tied optimum.

### Jev (`triage.jev`)

One `system_one` request per alert with `state` = the alert record minus
`id`, and five questions asked together (they run in parallel server-side):

| Question | Primitive | What it measures |
|---|---|---|
| `user_impact` | Score over *No user impact / Internal users affected / Some customers affected / Widespread customer impact* | who is hurt |
| `is_noise` | Noul | test/health-check signal, known flapping with nothing new, or non-production |
| `is_downstream_symptom` | Noul | symptom of an already-firing alert |
| `is_actively_degrading` | Noul | ongoing/worsening vs past blip or slow trend |
| `urgency` | Choice over *now / business_hours / backlog / ignore* | when a human is needed |

The model returns probabilities; `combine()` turns them into a label:

```
if is_noise ≥ noise_min or is_downstream_symptom ≥ downstream_min: SUPPRESS
if urgency.confidence < urgency_confidence_min:                   NEEDS_HUMAN
label = {now: P1, business_hours: P2, backlog: P3, ignore: SUPPRESS}[urgency.choice]
if label == P1 and not (user_impact ≥ p1_impact_min and is_actively_degrading ≥ p1_degrading_min): P2
```

The suppression Nouls are checked before the confidence gate on purpose:
they are independent judgments with their own probabilities, and a
confident "this is a duplicate" should not be discarded because the urgency
choice between *ignore* and *backlog* — a distinction that does not matter
for a duplicate — happened to be a coin flip. The gate therefore applies
only to labels that actually depend on the urgency answer.

## Tuning protocol

- Both systems are tuned on the **tune split only** (52 alerts). Nothing
  in the tuning code path reads `split.test`.
- Grid search reports the best accuracy and **every** tied combination,
  plus the set of values each threshold takes among the ties. Wide ties
  mean the tune split does not discriminate that threshold; defaults were
  kept at round values inside the tied region rather than at an edge.
- Jev's label thresholds are tuned with the confidence gate off, so every
  alert is scored. The gate is then chosen separately from a table that
  shows, for each candidate, how many alerts it diverts and what their
  accuracy *would have been* without gating. A gate is only useful if the
  diverted alerts are worse than the rest.
- Jev tuning never calls the API: it re-reads the recorded answers.

## Metrics

All on the 98-alert test split.

| Metric | Definition |
|---|---|
| overall accuracy (strict) | correct / n, with `NEEDS_HUMAN` counted as wrong. Comparable across systems that do and do not gate. |
| accuracy on hard / easy | same, restricted to `hard == true` / `false` |
| P1 recall | true P1 predicted P1 / true P1. A gated P1 is a missed P1. This is the headline safety number: missing a real P1 is the costliest error. |
| per-class precision | correct predictions of class / all (non-gated) predictions of class |
| per-class recall | correct predictions of class / true members of class |
| sent to NEEDS_HUMAN | count of gated alerts; reported next to accuracy on the remainder |
| confusion matrix | rows truth, columns prediction, with a `NEEDS_HUMAN` column for Jev |

## Latency

Wall-clock (`time.perf_counter`) around each SDK call, including TLS and
— for the first call — connection setup. Measured from India over the
public internet against `api.typesafe.ai`; a colocated deployment would be
faster. Percentiles are nearest-rank (no interpolation) over the test
split's calls. Calls are sequential, so this is per-request latency, not
throughput.

## Cost

**Jev (actual)**: `input_tokens` from every response × $0.042 per 1M;
output tokens are free. The token count includes the five questions, which
is why Jev's per-alert input (~750 tokens) is *higher* than the Sonnet
prompt's (~510): it is cheaper on price per token, not on tokens.

**Claude Sonnet 5 (estimated — no call is made)**: for each alert the exact
Messages API request is built (`triage.llm_estimate.build_request`): a
system prompt with the label rules and field notes, the alert as JSON, and
a request for `{"label": ..., "reason": ...}`. Input tokens are counted
with tiktoken `o200k_base`; Claude's tokenizer differs, so the count is an
approximation. 60 output tokens per alert are assumed. Priced at $2 / $10
per 1M input / output, checked on Anthropic's pricing page on 2026-09-21
(constant and date in the source). No prompt caching, batch discount, or
thinking tokens are modelled; caching the system prompt would lower the
Sonnet figure, thinking would raise it.

Both figures are also given per 1,000 alerts, which is the scale at which
the difference becomes tangible.

## Reproducibility

- `python -m triage.dataset.generate` is deterministic; `tests/test_dataset.py`
  asserts the files on disk equal the generator output.
- Every result file is timestamped and records the parameters used.
- The Jev run file stores every raw answer, so labels can be re-derived and
  thresholds re-tuned offline.
- The Jev model is pinned (`jev-1.13.0`); the `model` field of each
  response is stored and the evaluation prints the set of models seen.
- `make all` re-runs everything that does not spend API credits.

## Known limitations of this benchmark

- **Question wording vs label rules.** The `is_noise` question as written
  includes "a non-production environment", while the label rules make
  staging-blocking-a-release a P3. Jev follows the question, so those
  alerts are suppressed. This is the largest single error source and a
  question-design finding, not a model-capability one.
- **Label boundaries.** Cert-expiry alerts (6–13 days out, renewal failed)
  are labelled P3; Jev rates them *business_hours* (P2). Reasonable people
  disagree here.
- **Sample size.** 16 hard cases in the test split; one alert is 6 points.
- **The confidence gate is weak on this data.** On the tune split the
  gated alerts were only modestly less accurate than the rest.
- **Synthetic data**, see `docs/DATASET.md`.
