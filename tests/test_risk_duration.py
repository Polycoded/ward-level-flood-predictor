"""Artificial feature fixtures verify HTTP duration integration, not flood accuracy."""

import geopandas as gpd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box

from api.main import app
from api.routes import main as routes
from model.risk_engine import score_ward


@pytest.fixture
def artificial_features(monkeypatch):
    features = gpd.GeoDataFrame([{
        "ward_id": 1, "ward_number": "099", "ward_name": "Artificial ward",
        "elevation_mean": 10.0, "slope_mean": 2.0, "impervious_frac": 0.5,
        "water_frac": 0.1, "dist_to_water_m": 1000.0,
        "road_density_km_per_sqkm": 5.0, "underpass_count": 0,
        "geometry": box(400000, 1450000, 400100, 1450100),
    }], crs="EPSG:32644")
    monkeypatch.setattr(routes, "load_features", lambda: features)
    return features


@pytest.mark.parametrize("duration", [1, 3, 12, None])
def test_risk_duration_matches_direct_model(artificial_features, duration):
    payload = {"rainfall_mm": 100}
    if duration is not None:
        payload["duration_hours"] = duration
    actual_duration = 3 if duration is None else duration
    expected = score_ward(artificial_features.iloc[0], 100, duration_hours=actual_duration)
    with TestClient(app) as client:
        response = client.post("/api/v1/risk", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["scenario"]["duration_hours"] == actual_duration
    assert data["scenario"]["rainfall_mm"] == 100
    assert len(data["wards"]) == 1
    ward = data["wards"][0]
    assert ward["risk_score"] == pytest.approx(expected[0])
    assert ward["risk_level"] == expected[1].value
    assert ward["reasons"] == expected[4]


def test_risk_duration_is_sensitive_and_default_is_three_hours(artificial_features):
    with TestClient(app) as client:
        responses = [client.post("/api/v1/risk", json={"rainfall_mm": 100, "duration_hours": duration})
                     for duration in (1, 3, 12)]
        default = client.post("/api/v1/risk", json={"rainfall_mm": 100})
    assert all(response.status_code == 200 for response in [*responses, default])
    scores = [response.json()["wards"][0]["risk_score"] for response in responses]
    assert 0 < scores[2] < scores[1] < scores[0] < 1
    assert default.json()["wards"] == responses[1].json()["wards"]
    assert default.json()["scenario"] == responses[1].json()["scenario"]
