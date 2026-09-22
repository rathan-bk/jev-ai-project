"""Estimated cost of the same triage with Claude Sonnet 5. No LLM is called.

    python -m triage.llm_estimate                      # results/cost_<stamp>.json + table
    python -m triage.llm_estimate --show-prompt ALT-001

For each alert we build the exact Messages API request we *would* send
(system prompt with the label rules + the alert as JSON, asking for
{"label": ..., "reason": ...}), count its input tokens with a local tokenizer,
assume a fixed output length, and price it. Jev's cost uses the real
input-token counts recorded in the latest results/jev_*.json.

Token caveat: tiktoken's o200k_base is not Claude's tokenizer. Counts are
approximate (typically within tens of percent), which is adequate for a cost
comparison at this scale and must not be quoted as exact.
"""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import asdict, dataclass
from typing import Any, Final

import tiktoken

from triage.io import Alert, Dataset, latest_result, load_dataset, utc_now, write_result

# --- Prices, USD per 1M tokens -----------------------------------------------
# Sonnet 5: checked 2026-09-21 on https://docs.claude.com/en/docs/about-claude/pricing
# (standard API rate; the page notes the $2/$10 launch price is now the standard price).
SONNET5_MODEL: Final = "claude-sonnet-5"
SONNET5_INPUT_PER_M: Final = 2.00
SONNET5_OUTPUT_PER_M: Final = 10.00
# Jev: published System One rate at the time of the benchmark; output tokens are free.
JEV_INPUT_PER_M: Final = 0.042
JEV_OUTPUT_PER_M: Final = 0.0

ASSUMED_OUTPUT_TOKENS: Final = 60  # per alert, for {"label": ..., "reason": "..."}
TOKENIZER: Final = "o200k_base"  # approximation only, see module docstring

SYSTEM_PROMPT: Final = """You are an on-call triage assistant. Classify the monitoring alert into exactly one label.

Labels:
- P1: production, customer-facing, actively degrading user experience, not flapping. Needs a human immediately.
- P2: production but internal-only impact, OR customer-facing with a small or short breach. Needs attention today.
- P3: real but non-urgent: capacity trends, cert expiry, staging issues blocking a release. Can be ticketed.
- SUPPRESS: noise: flapping alerts, dev environments, synthetic/health-check signals with no user impact, or a duplicate symptom of another alert that is already firing.

Read the free-text summary and description carefully: they can override what the structured fields suggest (for example, an env label that is wrong, a "warning" that customers are already reporting, or a high fire count where this occurrence is genuinely new).

Field notes: breach_ratio is how far past the threshold the metric is (>= 1.0 means breached). fired_count_24h is how many times this alert fired in the last 24 hours. related_alerts_firing lists other alerts currently firing, as "<service>: <alertname> [<severity>]".

Respond with only a JSON object of the form {"label": "<P1|P2|P3|SUPPRESS>", "reason": "<one sentence>"}."""


def build_request(alert: Alert) -> dict[str, Any]:
    """The exact Messages API request for one alert. Built, counted, never sent."""
    state = {k: v for k, v in alert.items() if k != "id"}
    return {
        "model": SONNET5_MODEL,
        "max_tokens": 256,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": "Alert:\n" + json.dumps(state, indent=2)}],
    }


def count_input_tokens(enc: tiktoken.Encoding, request: dict[str, Any]) -> int:
    """System + user text. The small per-message framing overhead Claude adds is ignored."""
    return len(enc.encode(request["system"])) + sum(len(enc.encode(m["content"])) for m in request["messages"])


@dataclass(frozen=True, slots=True)
class CostBlock:
    system: str
    alerts: int
    input_tokens: int
    output_tokens: int
    total_usd: float
    per_alert_usd: float
    per_1000_alerts_usd: float

    @classmethod
    def compute(
        cls, system: str, n: int, input_tokens: int, output_tokens: int, in_price: float, out_price: float
    ) -> CostBlock:
        total = (input_tokens * in_price + output_tokens * out_price) / 1e6
        return cls(
            system, n, input_tokens, output_tokens, round(total, 6), round(total / n, 8), round(total / n * 1000, 4)
        )


def estimate(ds: Dataset, jev_run: dict[str, Any]) -> dict[str, Any]:
    enc = tiktoken.get_encoding(TOKENIZER)
    sonnet_tokens = {a["id"]: count_input_tokens(enc, build_request(a)) for a in ds.alerts}
    jev_tokens = {i: p["input_tokens"] for i, p in jev_run["predictions"].items()}

    subsets: dict[str, dict[str, Any]] = {}
    for name, ids in (("all", [a["id"] for a in ds.alerts]), ("test", list(ds.split.test))):
        n = len(ids)
        subsets[name] = {
            "sonnet5_estimated": asdict(
                CostBlock.compute(
                    SONNET5_MODEL,
                    n,
                    sum(sonnet_tokens[i] for i in ids),
                    n * ASSUMED_OUTPUT_TOKENS,
                    SONNET5_INPUT_PER_M,
                    SONNET5_OUTPUT_PER_M,
                )
            ),
            "jev_actual": asdict(
                CostBlock.compute(
                    jev_run["model_requested"], n, sum(jev_tokens[i] for i in ids), 0, JEV_INPUT_PER_M, JEV_OUTPUT_PER_M
                )
            ),
        }
    return {
        "timestamp": utc_now().isoformat(timespec="seconds"),
        "prices_usd_per_1m": {
            "sonnet5_input": SONNET5_INPUT_PER_M,
            "sonnet5_output": SONNET5_OUTPUT_PER_M,
            "jev_input": JEV_INPUT_PER_M,
            "jev_output": JEV_OUTPUT_PER_M,
        },
        "assumptions": {
            "sonnet5_output_tokens_per_alert": ASSUMED_OUTPUT_TOKENS,
            "tokenizer": TOKENIZER,
            "note": "Sonnet 5 input tokens are counted with tiktoken, not Claude's tokenizer; approximate.",
            "sonnet5_system_prompt_tokens": len(enc.encode(SYSTEM_PROMPT)),
            "sonnet5_mean_input_tokens_per_alert": round(statistics.mean(sonnet_tokens.values()), 1),
            "jev_mean_input_tokens_per_alert": round(statistics.mean(jev_tokens.values()), 1),
        },
        "subsets": subsets,
        "per_alert_sonnet5_input_tokens": sonnet_tokens,
    }


def print_table(report: dict[str, Any]) -> None:
    a = report["assumptions"]
    print(
        f"Sonnet 5 prompt: system {a['sonnet5_system_prompt_tokens']} tok, mean {a['sonnet5_mean_input_tokens_per_alert']} "
        f"input tok/alert ({a['tokenizer']} approximation), {report['assumptions']['sonnet5_output_tokens_per_alert']} output tok assumed"
    )
    print(
        f"Jev: actual input tokens from the run file, mean {a['jev_mean_input_tokens_per_alert']} tok/alert, output free\n"
    )
    print(
        f"{'subset':<6} {'system':<16} {'n':>4} {'in tok':>9} {'out tok':>8} {'total $':>10} {'per alert $':>12} {'per 1k $':>9}"
    )
    for subset, blocks in report["subsets"].items():
        for key, tag in (("sonnet5_estimated", "Sonnet 5 (est.)"), ("jev_actual", "Jev (actual)")):
            b = blocks[key]
            print(
                f"{subset:<6} {tag:<16} {b['alerts']:>4} {b['input_tokens']:>9} {b['output_tokens']:>8} "
                f"{b['total_usd']:>10.5f} {b['per_alert_usd']:>12.7f} {b['per_1000_alerts_usd']:>9.4f}"
            )
        ratio = blocks["sonnet5_estimated"]["total_usd"] / blocks["jev_actual"]["total_usd"]
        print(f"{'':<6} Sonnet 5 / Jev cost ratio: {ratio:.0f}x\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--show-prompt", metavar="ALERT_ID", help="print the exact request for one alert and exit")
    args = parser.parse_args()

    ds = load_dataset()
    if args.show_prompt:
        print(json.dumps(build_request(ds.by_id()[args.show_prompt]), indent=2))
        return

    jev_run, jev_path = latest_result("jev")
    report = estimate(ds, jev_run)
    report["jev_run"] = jev_path.name
    path = write_result("cost", report)
    print_table(report)
    print(f"wrote {path.name}")


if __name__ == "__main__":
    main()
