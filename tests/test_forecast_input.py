"""Exact hourly forecast windows, with no live service dependency."""
from copy import deepcopy

import pytest

from model.forecast_input import aggregate_forecast, validate_forecast


@pytest.fixture
def forecast_args():
    return dict(records=[{"interval_end": f"2000-01-01T0{i}:00:00Z", "precipitation_mm": i} for i in (0, 1, 2, 3)],
        interval_start="2000-01-01T00:00:00Z", interval_end="2000-01-01T03:00:00Z",
        issued_at="1999-12-31T23:00:00Z", retrieved_at="2000-01-01T00:00:00Z",
        valid_from="1999-12-31T23:00:00Z", valid_until="2000-01-02T00:00:00Z",
        now="2000-01-01T00:00:00Z", source="artificial:hourly-test", max_age_seconds=7200,
        max_retrieval_age_seconds=3600)


def test_preceding_hour_semantics_exactly_excludes_start_label(forecast_args):
    before = deepcopy(forecast_args)
    result = aggregate_forecast(**forecast_args)
    assert result["rainfall_mm"] == 6
    assert result["series_mm"] == [1, 2, 3]
    assert result["duration_hours"] == 3 and result["timezone"] == "UTC"
    assert result["kind"] == "forecast"
    assert forecast_args == before


@pytest.mark.parametrize("field,value", [("interval_start", "2000-01-01T00:30:00Z"),
    ("interval_end", "2000-01-01T03:30:00Z"), ("interval_end", "2000-01-02T01:00:00Z"),
    ("issued_at", "1999-12-30T00:00:00Z"), ("retrieved_at", "1999-12-31T22:00:00Z"),
    ("max_retrieval_age_seconds", -1), ("interval_start", "2000-01-01T00:00:00"),
    ("valid_until", "2000-01-01T02:00:00Z")])
def test_invalid_forecast_envelope(forecast_args, field, value):
    with pytest.raises(ValueError):
        aggregate_forecast(**{**forecast_args, field: value})


@pytest.mark.parametrize("value", [None, True, "2", -1, float("nan"), float("inf"), 501])
def test_missing_invalid_values_never_become_zero(forecast_args, value):
    forecast_args["records"][2]["precipitation_mm"] = value
    with pytest.raises(ValueError):
        aggregate_forecast(**forecast_args)


def test_missing_duplicate_and_total_overflow(forecast_args):
    for records in (forecast_args["records"][:-1], forecast_args["records"] * 2,
                    [{**r, "precipitation_mm": 200} for r in forecast_args["records"]]):
        with pytest.raises(ValueError):
            aggregate_forecast(**{**forecast_args, "records": records})


def test_explicit_offsets_and_zero_rain_are_valid(forecast_args):
    forecast_args["records"][1]["interval_end"] = "2000-01-01T06:30:00+05:30"
    forecast_args["records"][1]["precipitation_mm"] = 0
    assert aggregate_forecast(**forecast_args)["rainfall_mm"] == 5


def test_policy_rechecks_forecast_at_decision_time(forecast_args, exercise_row, exercise_policy):
    from model.alert_rules import evaluate_alerts
    forcing = aggregate_forecast(**forecast_args)
    # Issued/retrieved forecast was fresh at normalization but its interval has now started.
    with pytest.raises(ValueError, match="started"):
        evaluate_alerts([exercise_row], forcing, exercise_policy, {}, now="2000-01-01T00:01:00Z")
    with pytest.raises(ValueError):
        validate_forecast({**forcing, "series_mm": [100]}, now=forecast_args["now"])


def test_normalized_forecast_cannot_bypass_hour_alignment(forecast_args):
    forcing = aggregate_forecast(**forecast_args)
    with pytest.raises(ValueError, match="align"):
        validate_forecast({**forcing, "interval_start": "2000-01-01T00:30:00Z",
                           "interval_end": "2000-01-01T03:30:00Z"}, now=forecast_args["now"])


def test_forecast_candidate_expiry_is_capped(forecast_args, exercise_row, exercise_policy):
    from model.alert_rules import evaluate_alerts
    forecast_args["records"] = [{**r, "precipitation_mm": 40} for r in forecast_args["records"]]
    forecast_args["valid_until"] = forecast_args["interval_end"]
    forcing = aggregate_forecast(**forecast_args)
    result = evaluate_alerts([exercise_row], forcing, {**exercise_policy, "expiry_seconds": 14400}, {},
                            now=forecast_args["now"])
    assert result["candidates"][0]["expires_at"] == "2000-01-01T03:00:00+00:00"
