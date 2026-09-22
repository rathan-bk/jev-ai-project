# Architecture

The project is a five-stage batch pipeline. Every stage is a module with a
`main()` under `src/triage/`, reads its inputs from `data/` and the newest
file of the previous stage in `results/`, and writes one timestamped JSON
file. There is no service, database, or agent framework: the deliverable is
the benchmark, so reproducibility and readability win over features.

```
                 ┌──────────────────────────┐
                 │ triage.dataset.generate  │  seed-deterministic
                 └────────────┬─────────────┘
                              ▼
               data/alerts.json  data/labels.json  data/split.json
                 (no labels)      (id -> label,hard)  (tune / test ids)
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   │
 ┌────────────────┐  ┌────────────────┐           │
 │ triage.rules   │  │ triage.jev     │──API──▶ Jev (jev-1.13.0)
 │ if/else on     │  │ 5 questions    │           │
 │ structured     │  │ per alert,     │           │
 │ fields only    │  │ combine() in   │           │
 └───────┬────────┘  │ code           │           │
         │           └───────┬────────┘           │
         ▼                   ▼                    ▼
 results/rules_*.json  results/jev_*.json   ┌────────────────────┐
         │                   │              │ triage.llm_estimate│ no LLM call;
         │                   ├─────────────▶│ Sonnet 5 prompt +  │ tokenizer +
         │                   │              │ tiktoken + prices  │ price table
         │                   │              └─────────┬──────────┘
         │                   │                        ▼
         │                   │               results/cost_*.json
         └─────────┬─────────┴────────────────────────┘
                   ▼
          ┌────────────────┐
          │ triage.evaluate│  test split only
          └───────┬────────┘
                  ▼
   results/summary.md   results/summary_*.json
```

## Modules

| Module | Responsibility | Talks to the network |
|---|---|---|
| `triage.config` | Paths, label names, the pinned Jev model id | no |
| `triage.io` | `Dataset` loading, timestamped result files, `latest_result()` | no |
| `triage.tuning` | Generic grid search over frozen threshold dataclasses | no |
| `triage.metrics` | Accuracy / precision / recall / confusion with a `NEEDS_HUMAN` bucket; nearest-rank percentile | no |
| `triage.dataset.builders` | The alert record shape (`make_alert`), service catalogue, `breach_ratio` | no |
| `triage.dataset.scenarios` | Template generators for easy cases, one function per situation | no |
| `triage.dataset.hard_cases` | 25 hand-written cases where the description overrides the structured fields | no |
| `triage.dataset.generate` | Assembly, shuffling, id assignment, stratified split, validation | no |
| `triage.rules` | Rules-only baseline (`triage()`), `--tune` | no |
| `triage.jev` | Questions, `Answers`/`Prediction` records, `combine()`, `--tune`, `--recombine` | **yes** (plain run only) |
| `triage.llm_estimate` | Exact Sonnet 5 request builder, token counting, price constants | no |
| `triage.evaluate` | Test-split metrics, markdown report, failure listing | no |

Dependencies point downward only: the stage modules import `config`, `io`,
`tuning`, `metrics`; `evaluate` additionally imports `jev` for the
`Prediction` record type. Nothing imports a stage module's `main()`.

## Key design decisions

**Judgments in the model, policy in code.** Jev is asked five narrow
questions and returns probabilities. The mapping from those probabilities to
`P1/P2/P3/SUPPRESS/NEEDS_HUMAN` is `jev.combine()`, a pure function over a
frozen `Thresholds` dataclass. That keeps the policy explicit, unit-testable,
and re-tunable from the recorded answers without spending API calls.

**Raw answers are the durable artifact.** `results/jev_*.json` stores every
answer, probability distribution, confidence, the response `model` field,
latency and token usage per alert. Labels are re-derived from it
(`--recombine`) and thresholds re-tuned from it (`--tune`); nothing
downstream needs the API.

**Nothing exact is delegated to the model.** Breach ratios, durations, fire
counts and costs are computed in code and passed as fields. The questions
ask for semantic judgments only.

**Labels never travel.** `data/labels.json` is a separate file; `jev.state_for()`
and `llm_estimate.build_request()` build their payloads from `alerts.json`
records and drop the `id`. A test asserts neither `id` nor `label` appears in
what would be sent.

**Tune and test are separated at the data level.** `split.json` is produced
once by the generator; the tuning code only ever iterates `split.tune`, and
`evaluate` only ever iterates `split.test`.

**Deterministic dataset.** `generate.build_dataset(SEED)` is pure. A test
compares its output to the files on disk so that the recorded Jev run can
never silently refer to different alerts.

## Result file contracts

`results/rules_<stamp>.json`
```json
{"triager": "rules", "timestamp": "...", "params": {...RuleThresholds},
 "predictions": {"ALT-001": {"label": "P2"}, ...}}
```

`results/jev_<stamp>.json`
```json
{"triager": "jev", "model_requested": "jev-1.13.0", "timestamp": "...", "params": {...Thresholds},
 "predictions": {"ALT-001": {
    "label": "P3", "model": "jev-1.13.0", "latency_ms": 954.4, "input_tokens": 721, "output_tokens": 123,
    "answers": {
      "user_impact": {"score": 0.4, "confidence": 0.7, "probabilities": {"No user impact": 0.6, ...}},
      "is_noise": 0.05, "is_downstream_symptom": 0.1, "is_actively_degrading": 0.3,
      "urgency": {"choice": "backlog", "confidence": 1.0, "probabilities": {"now": 0.0, ...}}}}, ...}}
```

`results/cost_<stamp>.json` — price constants, assumptions, per-subset
(`all`, `test`) cost blocks for Sonnet 5 (estimated) and Jev (actual), and
per-alert Sonnet 5 token counts.

`results/summary_<stamp>.json` — the `Metrics` records for both triagers,
latency percentiles, models seen, and the test-subset cost blocks.
`results/summary.md` is the human-readable rendering of the same run.

## Extending

- **New scenario**: add a function to `dataset/scenarios.py` returning
  `(alert, label)` and register it in `EASY_SCENARIOS`. Because draws are
  consumed in order, adding one changes every subsequent alert; regenerate
  and re-run Jev.
- **New question**: add it to `jev.QUESTIONS`, extend `Answers` and its
  two constructors, then use it in `combine()`. Old run files will not load
  (they lack the field), which is intended.
- **Different policy**: edit `combine()` and `Thresholds`, add tests, run
  `--tune` then `--recombine`.
