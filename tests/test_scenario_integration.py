"""Artificial HTTP integration fixtures, never evidence of real flood accuracy."""

import geopandas as gpd
import pytest
from fastapi.testclient import TestClient
from geopandas.testing import assert_geodataframe_equal
from shapely.geometry import box

from api.main import app
from api.routes import main as routes
from model.risk_engine import score_ward


@pytest.fixture
def features(monkeypatch):
    # Deliberately unsorted internal IDs, nonmatching official numbers and row indices.
    frame = gpd.GeoDataFrame([
        {"ward_id": ident, "ward_number": number, "ward_name": f"Artificial {ident}",
         "elevation_mean": 10.0, "slope_mean": 2.0, "impervious_frac": impervious,
         "water_frac": 0.1, "dist_to_water_m": 1000.0,
         "road_density_km_per_sqkm": 5.0, "underpass_count": 0,
         "geometry": box(400000 + ident * 100, 1450000, 400050 + ident * 100, 1450050)}
        for ident, number, impervious in ((8, "099", 0.2), (2, "168", 0.9), (5, "007", 0.55))
    ], index=[42, 11, 90], crs="EPSG:32644")
    monkeypatch.setattr(routes, "load_features", lambda: frame)
    return frame


@pytest.fixture
def client(features):
    with TestClient(app) as http:
        yield http


def post(client, endpoint, payload):
    response = client.post(f"/api/v1/{endpoint}", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def assert_matches_model(data, features, increase, duration):
    assert data["scenario"]["rainfall_mm"] == 100
    assert data["scenario"]["duration_hours"] == duration
    expected = {int(row.ward_id): score_ward(row, 100, increase, duration_hours=duration)
                for _, row in features.iterrows()}
    assert [ward["ward_id"] for ward in data["wards"]] == sorted(
        expected, key=lambda ident: expected[ident][0], reverse=True)
    assert len(data["wards"]) == len(features)
    for ward in data["wards"]:
        original = features.loc[features.ward_id == ward["ward_id"]].iloc[0]
        score, level, _, _, reasons = expected[ward["ward_id"]]
        assert 0 < score < 1  # Avoid saturation masking integration mistakes.
        assert ward["risk_score"] == pytest.approx(score)
        assert ward["risk_level"] == level.value
        assert ward["reasons"] == reasons
        assert ward["ward_number"] == original.ward_number
        assert ward["ward_name"] == original.ward_name


@pytest.mark.parametrize("duration", [1, 3, 12])
def test_zero_scenario_matches_risk(client, features, duration):
    payload = {"rainfall_mm": 100, "duration_hours": duration}
    scenario = post(client, "scenario", {**payload, "builtup_increase_pct": 0})
    risk = post(client, "risk", payload)
    assert_matches_model(scenario, features, 0, duration)
    for left, right in zip(scenario["wards"], risk["wards"], strict=True):
        for key in ("ward_id", "ward_number", "ward_name", "risk_score", "risk_level", "reasons"):
            assert left[key] == right[key]
    # Names intentionally differ; compare only the forcing actually used.
    for key in ("rainfall_mm", "duration_hours"):
        assert scenario["scenario"][key] == risk["scenario"][key]


@pytest.mark.parametrize("duration", [1, 3, 12])
@pytest.mark.parametrize("increase", [15, 30])
def test_scenario_applies_increase_once_and_forwards_duration(client, features, duration, increase):
    data = post(client, "scenario", {"rainfall_mm": 100, "duration_hours": duration,
                                     "builtup_increase_pct": increase})
    assert_matches_model(data, features, increase, duration)
    original = features.loc[features.ward_id == 5].iloc[0]  # Non-capped, sensitive row.
    actual = next(ward for ward in data["wards"] if ward["ward_id"] == 5)
    assert actual["risk_score"] > score_ward(original, 100, 0, duration_hours=duration)[0]


def test_default_and_duration_sensitivity(client, features):
    payload = {"rainfall_mm": 100, "builtup_increase_pct": 30}
    default = post(client, "scenario", payload)
    explicit = [post(client, "scenario", {**payload, "duration_hours": duration})
                for duration in (1, 3, 12)]
    assert default["wards"] == explicit[1]["wards"]
    assert default["scenario"] == explicit[1]["scenario"]
    assert_matches_model(default, features, 30, 3)
    scores = [next(ward["risk_score"] for ward in data["wards"] if ward["ward_id"] == 5)
              for data in explicit]
    assert scores[0] > scores[1] > scores[2]


def test_effective_fraction_cap(client, features):
    data = [post(client, "scenario", {"rainfall_mm": 100, "builtup_increase_pct": increase})
            for increase in (30, 100)]
    capped = features.loc[features.ward_id == 2].iloc[0].copy()
    capped["impervious_frac"] = 1.0
    expected = score_ward(capped, 100, 0, duration_hours=3)
    for result in data:
        ward = next(row for row in result["wards"] if row["ward_id"] == 2)
        assert ward["risk_score"] == pytest.approx(expected[0])
        assert ward["risk_level"] == expected[1].value
        assert ward["reasons"] == expected[4]


def test_requests_are_deterministic_and_do_not_mutate_shared_features(client, features):
    original = features.copy(deep=True)
    payload = {"rainfall_mm": 100, "duration_hours": 12}
    before = post(client, "risk", payload)
    first = post(client, "scenario", {**payload, "builtup_increase_pct": 30})
    second = post(client, "scenario", {**payload, "builtup_increase_pct": 30})
    after = post(client, "risk", payload)
    assert first["wards"] == second["wards"]
    assert first["scenario"] == second["scenario"]
    assert before["wards"] == after["wards"]
    assert before["scenario"] == after["scenario"]
    assert_geodataframe_equal(features, original)


@pytest.mark.parametrize("field,value", [
    ("rainfall_mm", -1), ("rainfall_mm", 501),
    ("duration_hours", 0), ("duration_hours", 25),
    ("builtup_increase_pct", -1), ("builtup_increase_pct", 101),
])
def test_scenario_rejects_out_of_range_requests(client, field, value):
    payload = {"rainfall_mm": 100, "duration_hours": 3, "builtup_increase_pct": 15, field: value}
    response = client.post("/api/v1/scenario", json=payload)
    assert response.status_code == 422
    assert any(error["loc"] == ["body", field] for error in response.json()["detail"])
