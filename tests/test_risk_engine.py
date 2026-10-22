"""Artificial fixtures test mechanics only, not real geographic or forecast accuracy."""

import math

import numpy as np
import pandas as pd
import pytest

from model.reasons import generate_reasons
from model.risk_engine import (
    DepthBand,
    RiskLevel,
    classify_risk,
    normalize,
    score_ward,
    score_wards,
)
from model.risk_engine import (
    generate_reasons as legacy_reasons,
)


@pytest.fixture
def ward():
    return pd.Series({
        "ward_id": 1, "ward_number": "1", "ward_name": "Artificial test ward",
        "elevation_mean": 10.0, "slope_mean": 2.0, "impervious_frac": 0.55,
        "dist_to_water_m": 1000.0, "road_density_km_per_sqkm": 5.0,
        "underpass_count": 0,
    })


@pytest.mark.parametrize("boundary,below,at", [
    (0.2, RiskLevel.VERY_LOW, RiskLevel.LOW),
    (0.35, RiskLevel.LOW, RiskLevel.MODERATE),
    (0.55, RiskLevel.MODERATE, RiskLevel.HIGH),
    (0.75, RiskLevel.HIGH, RiskLevel.VERY_HIGH),
])
def test_category_edges(boundary, below, at):
    assert classify_risk(math.nextafter(boundary, 0)) == below
    assert classify_risk(boundary) == at
    assert classify_risk(math.nextafter(boundary, 1)) == at


def test_endpoints_and_saturation(ward):
    assert classify_risk(0) == RiskLevel.VERY_LOW
    assert classify_risk(1) == RiskLevel.VERY_HIGH
    ward.update(pd.Series({"elevation_mean": 0, "slope_mean": 0,
                           "impervious_frac": 1, "dist_to_water_m": 0,
                           "road_density_km_per_sqkm": 20, "underpass_count": 1}))
    assert score_ward(ward, 500)[:2] == (1, RiskLevel.VERY_HIGH)


@pytest.mark.parametrize("field", [
    "elevation_mean", "slope_mean", "impervious_frac", "dist_to_water_m",
    "road_density_km_per_sqkm", "underpass_count",
])
@pytest.mark.parametrize("bad", [None, pd.NA, np.nan, np.inf, -np.inf, "0", True])
def test_invalid_measurements_rejected(ward, field, bad):
    ward[field] = bad
    with pytest.raises(ValueError, match=field):
        score_ward(ward, 100)
    with pytest.raises(ValueError, match=field):
        generate_reasons(ward, 100, 0.5)


@pytest.mark.parametrize("field", [
    "elevation_mean", "slope_mean", "impervious_frac", "dist_to_water_m",
    "road_density_km_per_sqkm", "underpass_count",
])
def test_missing_measurements_rejected(ward, field):
    with pytest.raises(ValueError, match=field):
        score_ward(ward.drop(field), 0)


@pytest.mark.parametrize("field,bad", [
    ("slope_mean", -1), ("slope_mean", 91), ("impervious_frac", -0.1),
    ("impervious_frac", 1.1), ("dist_to_water_m", -1),
    ("road_density_km_per_sqkm", -1), ("underpass_count", -1),
    ("underpass_count", 0.5),
])
def test_physical_ranges(ward, field, bad):
    ward[field] = bad
    with pytest.raises(ValueError, match=field):
        score_ward(ward, 100)


@pytest.mark.parametrize("argument,bad", [
    (name, bad) for name in ("rainfall_mm", "duration_hours", "builtup_increase")
    for bad in (None, float("nan"), float("inf"), True, "3", -1)
] + [("rainfall_mm", 501), ("duration_hours", 0), ("duration_hours", 25),
     ("builtup_increase", 101)])
def test_invalid_scenarios(ward, argument, bad):
    args = {"rainfall_mm": 100, argument: bad}
    with pytest.raises(ValueError, match=argument):
        score_ward(ward, **args)
    with pytest.raises(ValueError, match=argument):
        score_wards(pd.DataFrame(), **args)


def test_formula_and_legacy_three_hour_default(ward):
    base = 0.25 * 0.8 + 0.15 * (1 - 2 / 15) + 0.25 * 0.55 + 0.15 * 0.8 + 0.1 * 0.25
    result = score_ward(ward, 100)
    assert result[0] == pytest.approx(base * 0.5)
    assert result == score_ward(ward, 100, 0, duration_hours=3)
    assert isinstance(result[1], RiskLevel)
    assert isinstance(result[2], DepthBand)
    assert isinstance(result[3], int)
    assert len(result) == 5


def test_rainfall_and_duration_sensitivity(ward):
    scores = [score_ward(ward, rain)[0] for rain in (0, 25, 75, 150, 250, 500)]
    assert scores[0] == 0
    assert scores == sorted(scores)
    assert len(set(scores)) == len(scores)
    short = score_ward(ward, 100, duration_hours=1)[0]
    reference = score_ward(ward, 100)[0]
    long = score_ward(ward, 100, duration_hours=24)[0]
    assert short == pytest.approx(reference * 1.5)
    assert long == pytest.approx(reference * 0.5)
    assert short > reference > long
    assert score_ward(ward, 500, duration_hours=1)[0] <= 1


def test_builtup_applied_once_and_explained(ward):
    original = ward.copy(deep=True)
    baseline = score_ward(ward, 100)
    scenario = score_ward(ward, 100, 30)
    assert scenario[0] - baseline[0] == pytest.approx(0.25 * 0.55 * 0.30 * 0.5)
    assert not any("impervious" in reason for reason in baseline[4])
    assert any("71.5%" in reason for reason in scenario[4])
    pd.testing.assert_series_equal(ward, original)
    assert score_ward(ward, 100, 15)[0] < scenario[0]
    ward["impervious_frac"] = 0.9
    assert score_ward(ward, 100, 30) == score_ward(ward, 100, 100)


def test_shared_explanations_and_unused_features(ward):
    ward["vegetation_frac"] = float("nan")  # Not a scored input.
    ward["water_frac"] = None
    for duration in (1, 3, 24):
        score, level, depth, _, reasons = score_ward(ward, 175, 30, duration_hours=duration)
        kwargs = {"builtup_increase": 30, "duration_hours": duration}
        assert reasons == generate_reasons(ward, 175, score, **kwargs)
        assert reasons == legacy_reasons(ward, 175, score, level, depth, **kwargs)
        text = " ".join(reasons)
        assert f"over {duration} h" in text
        assert "Uncalibrated risk index" in text
        assert "drainage capacity" not in text
        assert "vegetation" not in text
    result = score_ward(ward, 100)
    assert generate_reasons(ward, 100, result[0]) == result[4]
    assert legacy_reasons(ward, 100, result[0], result[1], result[2]) == result[4]


def test_batch_forwarding_sorting_and_empty(ward):
    other = ward.copy()
    other["ward_id"] = 2
    other["impervious_frac"] = 0.1
    features = pd.DataFrame([other, ward])
    result = score_wards(features, 100, 30, duration_hours=12)
    assert result.ward_id.tolist() == [1, 2]
    assert result.iloc[0].risk_score == score_ward(ward, 100, 30, duration_hours=12)[0]
    assert result.iloc[0].reasons == score_ward(ward, 100, 30, duration_hours=12)[4]
    assert list(score_wards(features.iloc[:0], 100).columns) == list(result.columns)
    assert score_wards(features.iloc[:0], 100).empty


@pytest.mark.parametrize("bad", [-0.1, 1.1, None, float("nan"), float("inf"), True])
def test_invalid_index(bad):
    with pytest.raises(ValueError):
        classify_risk(bad)


def test_normalization_clipping():
    assert normalize(-10, 0, 50, invert=True) == 1
    assert normalize(100, 0, 50, invert=True) == 0
    with pytest.raises(ValueError):
        normalize(float("nan"), 0, 50)
    with pytest.raises(ValueError):
        normalize(1, 1, 1)


def test_contrasting_artificial_ward_scenarios(ward):
    less_susceptible = ward.copy()
    less_susceptible.update(pd.Series({
        "elevation_mean": 50, "slope_mean": 15, "impervious_frac": 0,
        "dist_to_water_m": 5000, "road_density_km_per_sqkm": 0,
        "underpass_count": 0,
    }))
    more_susceptible = ward.copy()
    more_susceptible.update(pd.Series({
        "elevation_mean": -1, "slope_mean": 0, "impervious_frac": 0.9,
        "dist_to_water_m": 100, "road_density_km_per_sqkm": 18,
        "underpass_count": 2,
    }))
    assert score_ward(less_susceptible, 200)[0] == 0
    result = score_ward(more_susceptible, 200)
    assert result[0] > score_ward(ward, 200)[0]
    assert result[1] == RiskLevel.VERY_HIGH
    assert len(result[4]) == 8  # All six feature triggers plus rainfall and disclaimer.
    assert result[4] == generate_reasons(more_susceptible, 200, result[0])
    assert score_ward(more_susceptible, 0)[0] == 0


def test_known_zero_measurements_and_numpy_scalars(ward):
    for field in ("elevation_mean", "slope_mean", "impervious_frac",
                  "dist_to_water_m", "road_density_km_per_sqkm"):
        ward[field] = np.float64(0)
    ward["underpass_count"] = np.int64(0)
    assert score_ward(ward, np.float64(100))[0] == pytest.approx(0.275)
