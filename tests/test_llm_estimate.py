import json

import tiktoken
from conftest import alert

from triage.llm_estimate import ASSUMED_OUTPUT_TOKENS, TOKENIZER, CostBlock, build_request, count_input_tokens


def test_request_carries_the_alert_but_not_id_or_label():
    req = build_request(alert())
    body = json.loads(req["messages"][0]["content"].removeprefix("Alert:\n"))
    assert "id" not in body and "label" not in body
    assert body["service"] == "checkout-web"
    assert '"label"' in req["system"]  # asks for the JSON shape


def test_token_count_is_positive_and_includes_system_prompt():
    enc = tiktoken.get_encoding(TOKENIZER)
    req = build_request(alert())
    assert count_input_tokens(enc, req) > len(enc.encode(req["system"])) > 0


def test_cost_arithmetic():
    block = CostBlock.compute(
        "m", n=100, input_tokens=1_000_000, output_tokens=100 * ASSUMED_OUTPUT_TOKENS, in_price=2.0, out_price=10.0
    )
    assert block.total_usd == 2.0 + 6000 * 10.0 / 1e6
    assert block.per_alert_usd == round(block.total_usd / 100, 8)
