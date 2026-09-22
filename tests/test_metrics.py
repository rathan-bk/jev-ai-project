import math

from triage.io import Label
from triage.metrics import evaluate, percentile


def test_percentile_nearest_rank():
    values = [10, 20, 30, 40]
    assert percentile(values, 50) == 20
    assert percentile(values, 95) == 40
    assert math.isnan(percentile([], 50))


def test_evaluate_with_a_gated_alert():
    labels = {
        "a": Label("P1", hard=True),
        "b": Label("P1", hard=False),
        "c": Label("P2", hard=False),
        "d": Label("SUPPRESS", hard=False),
    }
    preds = {"a": "P1", "b": "NEEDS_HUMAN", "c": "P1", "d": "SUPPRESS"}
    m = evaluate(preds, labels, ["a", "b", "c", "d"])

    assert m.n == 4 and m.n_gated == 1 and m.n_rest == 3
    assert m.accuracy == 0.5  # strict: b (gated) and c are wrong
    assert m.accuracy_on_rest == 2 / 3
    assert m.accuracy_hard == 1.0 and m.accuracy_easy == 1 / 3
    assert m.p1_recall == 0.5  # gated P1 counts as missed
    assert m.per_class["P1"].precision == 0.5  # a correct, c wrong
    assert m.per_class["P1"].gated == 1
    assert m.confusion["P1"]["NEEDS_HUMAN"] == 1 and m.confusion["P2"]["P1"] == 1
