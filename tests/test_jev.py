from conftest import answers

from triage.config import NEEDS_HUMAN
from triage.jev import DEFAULT_THRESHOLDS, Answers, Prediction, Thresholds, combine, state_for


def test_clear_p1():
    assert combine(answers()) == "P1"


def test_p1_demoted_to_p2_without_customer_impact_or_active_degradation():
    assert combine(answers(impact=1.0)) == "P2"
    assert combine(answers(degrading=0.2)) == "P2"


def test_urgency_maps_to_labels():
    assert combine(answers(urgency="business_hours")) == "P2"
    assert combine(answers(urgency="backlog")) == "P3"
    assert combine(answers(urgency="ignore")) == "SUPPRESS"


def test_suppression_nouls_win_over_urgency():
    assert combine(answers(noise=0.9)) == "SUPPRESS"
    assert combine(answers(downstream=0.9)) == "SUPPRESS"


def test_confident_duplicate_is_not_gated():
    """A low urgency confidence must not hide a confident suppression judgment."""
    assert combine(answers(downstream=0.97, urgency="ignore", confidence=0.3)) == "SUPPRESS"


def test_low_urgency_confidence_is_gated():
    assert combine(answers(confidence=DEFAULT_THRESHOLDS.urgency_confidence_min - 0.01)) == NEEDS_HUMAN
    assert combine(answers(confidence=0.3), Thresholds(urgency_confidence_min=0.0)) == "P1"


def test_thresholds_are_respected():
    assert combine(answers(noise=0.65), Thresholds(noise_min=0.7)) == "P1"


def test_state_never_contains_id_or_label():
    state = state_for({"id": "ALT-001", "env": "prod", "summary": "x"})
    assert "id" not in state and "label" not in state and state["env"] == "prod"


def test_prediction_round_trips_through_json_shape():
    p = Prediction(
        label="P1", model="jev-1.13.0", latency_ms=300.0, input_tokens=700, output_tokens=100, answers=answers()
    )
    restored = Prediction.from_dict(p.to_dict())
    assert restored == p
    assert isinstance(restored.answers, Answers)
