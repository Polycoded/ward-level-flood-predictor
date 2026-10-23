"""Hostile-client tests for the public API.

Each test is a request a real attacker or a buggy client can send. They run against the real
app and the real processed data in data/processed, so they also catch contract drift.
"""

import gzip
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.main import app  # noqa: E402

client = TestClient(app)
API = "/api/v1"
JSON = {"content-type": "application/json"}


def raw_post(path: str, body: bytes):
    return client.post(API + path, content=body, headers=JSON)


# --- numbers that are not numbers -------------------------------------------

@pytest.mark.parametrize("path", ["/risk", "/scenario"])
@pytest.mark.parametrize("value", [b"1e999", b"-1e999", b"NaN", b"Infinity"])
def test_non_finite_rainfall_is_a_clean_422(path, value):
    r = raw_post(path, b'{"rainfall_mm": ' + value + b"}")
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/json")


@pytest.mark.parametrize("rain", [-500, 1e9])
def test_alerts_reject_out_of_range_rainfall(rain):
    r = client.post(f"{API}/alerts", json={"ward_ids": [1], "rainfall_mm": rain})
    assert r.status_code == 422


# --- amplification ----------------------------------------------------------

def test_scenario_name_is_bounded():
    r = client.post(f"{API}/risk", json={"rainfall_mm": 100, "scenario_name": "A" * 1_000_000})
    assert r.status_code == 422


def test_alert_ward_list_is_bounded():
    r = client.post(f"{API}/alerts", json={"ward_ids": list(range(1, 100_001)), "rainfall_mm": 100})
    assert r.status_code == 422


def test_duplicate_channels_cannot_amplify_the_response():
    # 7.9 KB of request used to produce a 43 MB response
    body = {"ward_ids": list(range(1, 201)), "rainfall_mm": 100, "channels": ["sms"] * 1000}
    r = client.post(f"{API}/alerts", json=body)
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        assert len(r.json()["alerts"]) <= 200
        assert len(r.content) < 1_000_000


def test_duplicate_ward_ids_are_collapsed():
    r = client.post(f"{API}/alerts", json={"ward_ids": [1, 1, 1, 1], "rainfall_mm": 100, "channels": ["sms"]})
    assert r.status_code == 200
    assert len(r.json()["alerts"]) == 1


@pytest.mark.parametrize("body", [
    {"latitude": 9999, "longitude": 80},
    {"latitude": 13.08, "longitude": 999},
    {"latitude": 13.08, "longitude": 80.27, "max_results": 10_000_000},
    {"latitude": 13.08, "longitude": 80.27, "max_results": -5},
    {"latitude": 13.08, "longitude": 80.27, "max_distance_km": -1},
    {"latitude": 13.08, "longitude": 80.27, "max_distance_km": 100_000},
])
def test_shelter_search_is_bounded(body):
    assert client.post(f"{API}/shelters", json=body).status_code == 422


def test_shelter_search_still_works(monkeypatch):
    import geopandas as gpd
    from shapely.geometry import Point
    import api.routes.main as routes

    # Artificial route fixture; independent of an optional canonical shelter file.
    shelters = gpd.GeoDataFrame([{
        "shelter_id": 1, "name": "Test shelter", "latitude": 13.0827,
        "longitude": 80.2707, "capacity": 50, "geometry": Point(80.2707, 13.0827),
    }], crs="EPSG:4326")
    monkeypatch.setattr(routes, "load_shelters", lambda: shelters)
    r = client.post(f"{API}/shelters", json={"latitude": 13.0827, "longitude": 80.2707, "max_distance_km": 10, "max_results": 5})
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["name"] == "Test shelter"


def test_missing_shelters_return_empty_without_inventing_locations(monkeypatch):
    import geopandas as gpd
    import api.routes.main as routes

    monkeypatch.setattr(routes, "load_shelters", lambda: gpd.GeoDataFrame())
    r = client.post(f"{API}/shelters", json={"latitude": 13.0827, "longitude": 80.2707})
    assert r.status_code == 200
    assert r.json() == []


# --- error handling and headers ---------------------------------------------

def test_unhandled_errors_return_json_without_internals(monkeypatch):
    import api.routes.main as routes

    def boom():
        raise RuntimeError("secret detail: /home/deploy/.env DATABASE_PASSWORD")

    monkeypatch.setattr(routes, "load_features", boom)
    c = TestClient(app, raise_server_exceptions=False)
    r = c.post(f"{API}/risk", json={"rainfall_mm": 100})
    assert r.status_code == 500
    assert r.headers["content-type"].startswith("application/json")
    assert "secret" not in r.text and "PASSWORD" not in r.text


def test_cors_does_not_grant_credentials_to_any_origin():
    r = client.options(
        f"{API}/risk",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert r.headers.get("access-control-allow-credentials") != "true"


def test_large_responses_are_compressed():
    r = client.get(f"{API}/wards", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"


# --- correctness bugs a user can trigger ------------------------------------

def _avg(resp):
    wards = resp.json()["wards"]
    return sum(w["risk_score"] for w in wards) / len(wards)


def test_risk_honours_duration():
    short = client.post(f"{API}/risk", json={"rainfall_mm": 150, "duration_hours": 3})
    long = client.post(f"{API}/risk", json={"rainfall_mm": 150, "duration_hours": 12})
    assert _avg(long) < _avg(short)


def test_risk_and_zero_scenario_agree():
    risk = client.post(f"{API}/risk", json={"rainfall_mm": 150, "duration_hours": 12})
    scen = client.post(f"{API}/scenario", json={"rainfall_mm": 150, "duration_hours": 12, "builtup_increase_pct": 0})
    assert _avg(risk) == pytest.approx(_avg(scen))


def test_more_paving_never_lowers_risk_for_long_storms():
    today = {w["ward_id"]: w["risk_score"] for w in
             client.post(f"{API}/risk", json={"rainfall_mm": 150, "duration_hours": 12}).json()["wards"]}
    future = client.post(f"{API}/scenario", json={"rainfall_mm": 150, "duration_hours": 12, "builtup_increase_pct": 15})
    for w in future.json()["wards"]:
        assert w["risk_score"] >= today[w["ward_id"]] - 1e-12


def test_wards_geojson_route_is_reachable():
    r = client.get(f"{API}/wards/geojson", headers={"Accept-Encoding": "identity"})
    assert r.status_code == 200
    body = r.json() if r.headers.get("content-encoding") != "gzip" else __import__("json").loads(gzip.decompress(r.content))
    assert body["type"] == "FeatureCollection"
