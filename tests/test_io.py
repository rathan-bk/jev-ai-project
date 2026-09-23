import json

import pytest

from triage import io


@pytest.fixture
def results_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(io, "RESULTS_DIR", tmp_path)
    return tmp_path


def test_latest_result_picks_the_newest_stamp(results_dir):
    """Every downstream stage reads whatever this returns, so picking the wrong file is silent."""
    for stamp, acc in [("20260921T000000Z", 1), ("20260923T000000Z", 3), ("20260922T000000Z", 2)]:
        (results_dir / f"jev_{stamp}.json").write_text(json.dumps({"acc": acc}))
    run, path = io.latest_result("jev")
    assert run["acc"] == 3
    assert path.name == "jev_20260923T000000Z.json"


def test_latest_result_does_not_confuse_prefixes(results_dir):
    (results_dir / "rules_20260923T000000Z.json").write_text(json.dumps({"who": "rules"}))
    (results_dir / "jev_20260921T000000Z.json").write_text(json.dumps({"who": "jev"}))
    assert io.latest_result("jev")[0]["who"] == "jev"


def test_latest_result_explains_which_stage_to_run(results_dir):
    with pytest.raises(FileNotFoundError, match="run the earlier stage first"):
        io.latest_result("jev")


def test_write_result_round_trips_through_latest_result(results_dir):
    io.write_result("rules", {"predictions": {"ALT-001": {"label": "P1"}}})
    run, _ = io.latest_result("rules")
    assert run["predictions"]["ALT-001"]["label"] == "P1"


def test_timestamp_sorts_chronologically_as_a_string():
    """latest_result relies on name order, which only holds for zero-padded UTC stamps."""
    assert "20260901T000000Z" < "20260921T000000Z" < "20261001T000000Z"
    assert io.timestamp().endswith("Z")


def test_dataset_truth_and_by_id():
    ds = io.Dataset(
        alerts=({"id": "ALT-001", "env": "prod"},),
        labels={"ALT-001": io.Label(label="P1", hard=True)},
        split=io.Split(tune=(), test=("ALT-001",)),
    )
    assert ds.truth("ALT-001") == "P1"
    assert ds.by_id()["ALT-001"]["env"] == "prod"
