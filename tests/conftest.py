"""Named artificial Exercise fixtures; never historical observations."""
import pytest


@pytest.fixture
def exercise_row():
    return {"ward_id": 1, "ward_number": "168", "ward_name": "Artificial ward",
            "elevation_mean": 10.0, "slope_mean": 2.0, "impervious_frac": 0.5,
            "dist_to_water_m": 1000.0, "road_density_km_per_sqkm": 5.0, "underpass_count": 0}


@pytest.fixture
def exercise_policy():
    return {"version": "artificial-policy-v1", "model_version": "test-model-v1",
            "trigger_score": 0.25, "release_score": 0.2, "escalation_score": 0.6,
            "cooldown_seconds": 3600, "expiry_seconds": 7200, "min_rainfall_mm": 10,
            "max_candidates": 2}


@pytest.fixture
def exercise_rain():
    return {"kind": "manual_scenario", "source": "artificial:test-only", "rainfall_mm": 100,
            "duration_hours": 3, "interval_start": "2000-01-01T00:00:00+00:00",
            "interval_end": "2000-01-01T03:00:00+00:00"}


@pytest.fixture
def exercise_candidate(exercise_row, exercise_rain, exercise_policy):
    from model.alert_rules import evaluate_alerts
    return evaluate_alerts([exercise_row], exercise_rain, exercise_policy, {},
                           now="2000-01-01T00:00:00+00:00")["candidates"][0]
