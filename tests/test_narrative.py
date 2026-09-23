from conftest import alert, answers

from triage.io import Dataset, Label, Split
from triage.jev import Prediction
from triage.narrative import build, pick_examples

# The rules answer SUPPRESS on a flapping alert and P1 on a big prod breach; the
# truth is the other way round in both cases, so each is a "rules wrong, Jev right".
UNDER = {**alert(fired_count_24h=20), "id": "ALT-001"}  # rules: SUPPRESS, truth P1
OVER = {**alert(), "id": "ALT-002"}  # rules: P1, truth SUPPRESS


def dataset() -> Dataset:
    return Dataset(
        alerts=[UNDER, OVER],
        labels={
            "ALT-001": Label(label="P1", hard=True),
            "ALT-002": Label(label="SUPPRESS", hard=False),
        },
        split=Split(tune=[], test=["ALT-001", "ALT-002"]),
    )


def predictions() -> dict[str, Prediction]:
    def pred(label: str) -> Prediction:
        return Prediction(
            label=label, model="jev-test", latency_ms=1.0, input_tokens=1, output_tokens=0, answers=answers()
        )

    return {"ALT-001": pred("P1"), "ALT-002": pred("SUPPRESS")}


def test_pick_examples_returns_only_rules_wrong_jev_right():
    ds, preds = dataset(), predictions()
    picked = pick_examples(ds, preds, ["ALT-001", "ALT-002"])
    assert set(picked) == {"ALT-001", "ALT-002"}


def test_build_reports_computed_numbers_not_hardcoded_ones():
    ds, preds = dataset(), predictions()
    rules_preds = {"ALT-001": "SUPPRESS", "ALT-002": "P1"}
    md = build(ds, preds, rules_preds, ["ALT-001", "ALT-002"])

    # Jev is right on both, the rules on neither.
    assert "| overall accuracy | 0.0% | 100.0% |" in md
    # The rules sent a real P1 to SUPPRESS; Jev sent none.
    assert "silently routed 1 real P1/P2" in md
    assert "Jev suppressed 0." in md


def test_build_quotes_the_description_that_decided_the_call():
    ds, preds = dataset(), predictions()
    rules_preds = {"ALT-001": "SUPPRESS", "ALT-002": "P1"}
    md = build(ds, preds, rules_preds, ["ALT-001", "ALT-002"])
    assert UNDER["description"] in md
