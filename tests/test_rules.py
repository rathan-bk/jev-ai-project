from conftest import alert

from triage.rules import DEFAULT_THRESHOLDS, GRID, RuleThresholds, triage
from triage.tuning import grid


def test_precedence_dev_beats_everything():
    assert triage(alert(env="dev", severity_tag="critical")) == "SUPPRESS"


def test_flapping():
    assert triage(alert(fired_count_24h=DEFAULT_THRESHOLDS.flapping_min_fired)) == "SUPPRESS"
    assert triage(alert(fired_count_24h=DEFAULT_THRESHOLDS.flapping_min_fired - 1)) == "P1"


def test_duplicate_of_critical_upstream():
    assert triage(alert(related_alerts_firing=["payments-api: HighErrorRate [critical]"])) == "SUPPRESS"
    assert triage(alert(related_alerts_firing=["mobile-bff: HighErrorRate [warning]"])) == "P1"


def test_staging_and_trends_are_p3():
    assert triage(alert(env="staging")) == "P3"
    assert triage(alert(duration_minutes=DEFAULT_THRESHOLDS.trend_min_duration)) == "P3"


def test_internal_and_small_breaches_are_p2():
    assert triage(alert(customer_facing=False)) == "P2"
    assert triage(alert(value=2.5, threshold=2.0)) == "P2"  # breach 1.25 <= 1.3
    assert triage(alert(duration_minutes=DEFAULT_THRESHOLDS.short_duration_max)) == "P2"


def test_thresholds_are_respected():
    strict = RuleThresholds(small_breach_max=1.0)
    assert triage(alert(value=2.5, threshold=2.0), strict) == "P1"


def test_grid_covers_every_combination():
    assert len(grid(RuleThresholds, GRID)) == 6 * 4 * 4 * 4
