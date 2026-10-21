import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/v1/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_ready_check():
    response = client.get("/api/v1/readyz")
    assert response.status_code == 200
    data = response.json()
    assert "ready" in data
    assert "checks" in data


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data


def test_risk_endpoint_structure():
    response = client.post("/api/v1/risk", json={"rainfall_mm": 100, "duration_hours": 3})
    assert response.status_code in [200, 503]


def test_scenario_endpoint_structure():
    response = client.post("/api/v1/scenario", json={
        "rainfall_mm": 100,
        "duration_hours": 3,
        "builtup_increase_pct": 15
    })
    assert response.status_code in [200, 503]


def test_alerts_endpoint_structure():
    response = client.post("/api/v1/alerts", json={
        "ward_ids": [1, 2, 3],
        "rainfall_mm": 100,
        "language": "en",
        "channels": ["sms", "whatsapp"]
    })
    assert response.status_code in [200, 503]


def test_shelters_endpoint_structure():
    response = client.post("/api/v1/shelters", json={
        "latitude": 13.0827,
        "longitude": 80.2707,
        "max_distance_km": 5,
        "max_results": 5
    })
    assert response.status_code in [200, 503]


def test_roads_risk_endpoint_structure():
    response = client.get("/api/v1/roads/risk", params={"rainfall_mm": 100})
    assert response.status_code in [200, 503]


def test_validation_endpoint():
    response = client.get("/api/v1/validation")
    assert response.status_code in [200, 404]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])