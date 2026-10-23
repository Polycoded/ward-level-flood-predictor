"""Prototype policy mechanics only, not warning effectiveness."""
from copy import deepcopy

import pytest

from model.alert_rules import evaluate_alerts
from model.risk_engine import score_ward

NOW = "2000-01-01T00:00:00+00:00"


def run(row, rain, policy, state=None, now=NOW):
    return evaluate_alerts([row], rain, policy, state or {}, now=now)


def test_scorer_reuse_and_nonmutation(exercise_row, exercise_rain, exercise_policy):
    args = [exercise_row, exercise_rain, exercise_policy]
    before = deepcopy(args)
    a = run(*args)
    assert a == run(*args)
    c = a["candidates"][0]
    assert c["score"] == score_ward(exercise_row, 100, duration_hours=3)[0]
    assert c["status"] == "pending" and c["mode"] == "Exercise"
    assert c["ward_id"] == 1 and c["ward_number"] == "168"
    assert args == before


def test_dedup_cooldown_and_escalation_are_distinct(exercise_row, exercise_rain, exercise_policy):
    state = run(exercise_row, exercise_rain, exercise_policy)["proposed_state"]
    before = deepcopy(state)
    repeated = run(exercise_row, exercise_rain, exercise_policy, state, "2000-01-01T01:30:00Z")
    assert repeated["suppressed"][0]["reason"] == "deduplicated"
    changed = {**exercise_rain, "rainfall_mm": 110}
    assert run(exercise_row, changed, exercise_policy, state, "2000-01-01T00:30:00Z")["suppressed"][0]["reason"] == "cooldown"
    assert len(run(exercise_row, changed, exercise_policy, state, "2000-01-01T01:00:00Z")["candidates"]) == 1
    heavy = run(exercise_row, {**exercise_rain, "rainfall_mm": 300}, exercise_policy, state, "2000-01-01T00:01:00Z")
    assert heavy["candidates"][0]["cause"] == "escalation"
    assert state == before


def test_hysteresis_release_expiry_and_reentry(exercise_row, exercise_rain, exercise_policy):
    state = run(exercise_row, exercise_rain, exercise_policy)["proposed_state"]
    hold = run(exercise_row, {**exercise_rain, "rainfall_mm": 75}, exercise_policy, state)
    assert hold["suppressed"][0]["reason"] == "hysteresis_hold"
    assert hold["proposed_state"]["1"]["active"]
    release = run(exercise_row, {**exercise_rain, "rainfall_mm": 50}, exercise_policy, state)
    assert not release["proposed_state"]["1"]["active"]
    assert release["lifecycle"][0]["reason"] == "released"
    assert len(run(exercise_row, exercise_rain, exercise_policy, release["proposed_state"])["candidates"]) == 1
    expired = run(exercise_row, exercise_rain, exercise_policy, state, "2000-01-01T02:00:00Z")
    assert expired["lifecycle"][0]["reason"] == "expired"
    assert len(expired["candidates"]) == 1


def test_expired_hysteresis_does_not_reenter_below_trigger(exercise_row, exercise_rain, exercise_policy):
    state = run(exercise_row, exercise_rain, exercise_policy)["proposed_state"]
    result = run(exercise_row, {**exercise_rain, "rainfall_mm": 75}, exercise_policy, state, "2000-01-01T02:00:00Z")
    assert not result["candidates"]
    assert result["suppressed"][0]["reason"] == "below_trigger"


def test_overflow_ties_and_retry_not_silently_dropped(exercise_row, exercise_rain, exercise_policy):
    rows = [{**exercise_row, "ward_id": i, "ward_number": str(200-i)} for i in (3, 1, 2)]
    result = evaluate_alerts(rows, exercise_rain, exercise_policy, {}, now=NOW)
    assert [c["ward_id"] for c in result["candidates"]] == [1, 2]
    assert result["overflow_count"] == 1
    assert result["overflow"][0]["ward_id"] == 3
    assert "3" not in result["proposed_state"]
    retry = evaluate_alerts(rows, exercise_rain, exercise_policy, result["proposed_state"], now=NOW)
    assert [c["ward_id"] for c in retry["candidates"]] == [3]


@pytest.mark.parametrize("rain,reason", [(0, "minimum_rainfall"), (9, "minimum_rainfall"), (50, "below_trigger")])
def test_dry_and_low_scenarios(exercise_row, exercise_rain, exercise_policy, rain, reason):
    result = run(exercise_row, {**exercise_rain, "rainfall_mm": rain}, exercise_policy)
    assert not result["candidates"] and result["suppressed"][0]["reason"] == reason


@pytest.mark.parametrize("field,value", [("trigger_score", 0.1), ("release_score", 0.25),
    ("cooldown_seconds", -1), ("expiry_seconds", 0), ("max_candidates", True), ("max_candidates", 0)])
def test_invalid_policy(exercise_row, exercise_rain, exercise_policy, field, value):
    with pytest.raises(ValueError):
        run(exercise_row, exercise_rain, {**exercise_policy, field: value})


def test_duplicate_identity_and_time_rejected(exercise_row, exercise_rain, exercise_policy):
    with pytest.raises(ValueError, match="Duplicate"):
        evaluate_alerts([exercise_row, exercise_row], exercise_rain, exercise_policy, {}, now=NOW)
    with pytest.raises(ValueError, match="offset"):
        run(exercise_row, exercise_rain, exercise_policy, now="2000-01-01T00:00:00")
    state = run(exercise_row, exercise_rain, exercise_policy)["proposed_state"]
    with pytest.raises(ValueError):
        run(exercise_row, exercise_rain, exercise_policy, state, "1999-12-31T23:00:00Z")
