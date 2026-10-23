"""Artificial alert duration integration, not flood prediction evidence."""
import geopandas as gpd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box

from api.main import app
from api.routes import main as routes
from model.risk_engine import score_ward
from model.alerts import generate_alert_messages


@pytest.fixture
def features(monkeypatch):
    frame = gpd.GeoDataFrame([dict(
        ward_id=1, ward_number="168", ward_name="Artificial ward", elevation_mean=10.0,
        slope_mean=2.0, impervious_frac=0.5, water_frac=0.1, dist_to_water_m=1000.0,
        road_density_km_per_sqkm=5.0, underpass_count=0,
        geometry=box(400000, 1450000, 400100, 1450100),
    )], crs=32644)
    monkeypatch.setattr(routes, "load_features", lambda: frame)
    return frame


@pytest.mark.parametrize("duration", [1, 3, 12, 1.5])
@pytest.mark.parametrize("channel", ["sms", "whatsapp", "voice", "livekit"])
def test_alerts_match_baseline_map_duration(features, duration, channel):
    with TestClient(app) as client:
        mapped = client.post("/api/v1/risk", json={"rainfall_mm": 100, "duration_hours": duration})
        response = client.post("/api/v1/alerts", json={"ward_ids": [1], "rainfall_mm": 100,
                               "duration_hours": duration, "channels": [channel]})
    assert response.status_code == mapped.status_code == 200
    expected = score_ward(features.iloc[0], 100, duration_hours=duration)
    assert mapped.json()["wards"][0]["risk_score"] == pytest.approx(expected[0])
    message = response.json()["alerts"][0]["message"]
    assert f"Uncalibrated index: {expected[1].value.replace('_', ' ')}." in message
    assert f"100mm/{duration:g}h" in message


def test_omitted_alert_duration_is_three_hours(features):
    with TestClient(app) as client:
        payload = {"ward_ids": [1], "rainfall_mm": 100}
        default = client.post("/api/v1/alerts", json=payload)
        explicit = client.post("/api/v1/alerts", json={**payload, "duration_hours": 3})
    assert default.status_code == explicit.status_code == 200
    assert default.json()["alerts"] == explicit.json()["alerts"]


@pytest.mark.parametrize("duration", [0, 25, None])
def test_invalid_alert_duration_rejected(features, duration):
    with TestClient(app) as client:
        response = client.post("/api/v1/alerts", json={"ward_ids": [1], "rainfall_mm": 100,
                                                     "duration_hours": duration})
    assert response.status_code == 422


@pytest.mark.parametrize("language", ["en", "ta"])
@pytest.mark.parametrize("channel", ["sms", "whatsapp"])
def test_fractional_interval_is_not_lost_to_message_truncation(language, channel):
    message, _ = generate_alert_messages("X" * 300, "very_high", "1.0m+", 100.5,
                                         language, channel, duration_hours=1.5)
    assert "100.5mm/1.5h" in message
    assert "1.0m+" not in message
