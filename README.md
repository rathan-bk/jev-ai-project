# Alert triage with Jev — proof of concept and benchmark

Classifies monitoring alerts into **P1 / P2 / P3 / SUPPRESS** with
[Jev](https://docs.typesafe.ai) (TypeSafe's System One model, pinned to
`jev-1.13.0`) and benchmarks it against a rules-only baseline on accuracy,
latency and cost, with an estimated cost comparison against Claude Sonnet 5.

Jev answers five narrow questions per alert and returns probabilities; the
label is derived in code. No LLM is called anywhere in the pipeline.

## What Jev is, and why it suits this problem

Jev is a [System One](https://docs.typesafe.ai/concepts/system-one) model:
a class of model built to make *fast, structured decisions that software can
use directly*. It does not write replies, produce code, or explain its
reasoning. It returns **typed answers and calibrated probabilities** —
probabilities trained against outcomes, so 0.9 is meant to behave like 0.9.

That constraint is the reason it fits alert triage. The judgment that is hard
to automate here is semantic: *does this description say the thing is actually
broken?* Everything else — comparing a breach ratio, counting firings,
deciding what P1 means — is arithmetic and policy, which belong in code where
they can be read, tested and argued with.

So this project asks Jev five questions per alert and derives the label
itself:

| question | type | what it returns |
|---|---|---|
| who is affected? | `Score` | a position on four ordered impact levels |
| is this noise? | `Noul` | P(yes) |
| is it a downstream symptom? | `Noul` | P(yes) |
| is it actively degrading? | `Noul` | P(yes) |
| how urgent? | `Choice` | one of now / business_hours / backlog / ignore |

[`combine()`](src/triage/jev.py) turns those five numbers into a label. It is
an ordinary pure function with named thresholds — no model decides what P1
means. Change the policy and you re-run `combine()` over the recorded answers
for free, with no API calls; the raw judgments are the durable artifact.

Whether this beats a pile of if-statements is an empirical question, which is
what the rest of this repo measures.

## Results (98-alert test split)

| | rules-only | Jev |
|---|---|---|
| overall accuracy (strict) | 86.7% | 86.7% |
| hard cases, n=16 | 18.8% | **100%** |
| easy cases, n=82 | **100%** | 84.1% |
| **P1 recall** | 69.2% | **100%** |
| real P1/P2 silently suppressed | 3 | **0** |
| latency p50 / p95 (India → public API) | ~0 | 469 / 701 ms |
| cost per alert | $0 | $0.0000320 actual · Sonnet 5 est. $0.0016 |

The two tie on headline accuracy and fail in completely different places.
Rules are perfect on the 82 easy alerts, where the structured fields alone
decide the label, and collapse to 18.8% on the 16 hard ones, where the
fields are misleading and only the description carries the answer. Jev
gets **all 16 hard cases right**, including three real incidents the rules
silently suppress.

All 13 of Jev's remaining errors are the same transition, P3 → P2: alerts
it rates *business_hours* where the label rules say *backlog* (cert expiry,
latency trends, restart loops). It never under-prioritises — no missed P1,
no suppressed incident.

**Two write-ups of the same run.**
[`results/evaluation_summary.md`](results/evaluation_summary.md) is the
plain-language one: what the two systems do differently, and the alerts where
the description overturned the metrics.
[`results/summary.md`](results/summary.md) is the reference: full tables,
confusion matrices, and every error with its raw answers. Both are generated
from the run files, so neither can drift from the data.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
make install                       # pip install -e ".[dev]"
echo "TYPESAFE_API_KEY=..." > .env  # git-ignored

make all                           # data → rules → cost → eval, no API credits spent
make jev                           # 150 Jev calls (~1 min, ~$0.005), then `make cost eval`
make test lint
```

Each stage is a module with a `main()`; `make` targets are one-liners around
`python -m triage.<stage>`. See `make help` or the `Makefile`.

## Layout

```
src/triage/
  config.py, io.py, tuning.py, metrics.py     shared: paths, dataset/result I/O, grid search, metrics
  dataset/  builders.py scenarios.py hard_cases.py generate.py   synthetic dataset
  rules.py                                    rules-only baseline
  jev.py                                      Jev questions + combine()
  llm_estimate.py                             Sonnet 5 cost estimate (no calls)
  evaluate.py                                 test-split report
  narrative.py                                plain-language write-up
data/       alerts.json (no labels) · labels.json · split.json
results/    timestamped run files + summary.md + evaluation_summary.md
tests/      unit tests incl. a reproducibility guard for the dataset
docs/       ARCHITECTURE.md · DATASET.md · METHODOLOGY.md
```

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — pipeline, modules, design decisions, result file contracts
- [docs/DATASET.md](docs/DATASET.md) — fields, label rules, how easy and hard cases are built, split
- [docs/METHODOLOGY.md](docs/METHODOLOGY.md) — tuning protocol, metric definitions, latency and cost measurement, limitations

## Ground rules this code follows

- Labels are never sent to a model; `alerts.json` and `labels.json` are separate files and a test checks the outgoing payload.
- Anything exact (ratios, counts, costs) is computed in code. The model is asked for judgments only.
- Thresholds are named constants in frozen dataclasses, tuned on the tune split only, and every tied optimum is printed.
- Every result file is timestamped and records its parameters; the Jev run stores every raw answer so labels can be re-derived offline.
- The dataset is regenerated byte-identically from a fixed seed.
