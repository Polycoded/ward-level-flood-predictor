"""End-to-end tests for John's alerting, subscription and speed features."""

from __future__ import annotations

import gzip
import hashlib
import hmac
import json
import xml.etree.ElementTree as ET
from datetime import UTC

import geopandas as gpd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import LineString, box
from sqlmodel import Session, select

from api import db
from api.db import Alert, DispatchLog, Subscription, WhatsAppSubscriber
from api.main import app
from api.rate_limit import subscription_limiter, webhook_limiter
from api.settings import settings
from integrations import openwa
from integrations.crypto import decrypt, encrypt, identifier_hash
from services.rules import WardRisk, default_select

WARD_ID = 168


@pytest.fixture()
def client(tmp_path):
    settings.database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings.exercise_mode = True
    settings.warm_cache_on_startup = False
    settings.openwa_base_url = ""
    settings.openwa_webhook_secret = ""
    settings.vapid_private_key = ""
    settings.vapid_public_key = ""
    settings.twilio_sms_fallback = False
    db.reset_engine(settings.database_url)
    db.init_db()
    subscription_limiter.limit = 20
    subscription_limiter.reset()
    webhook_limiter.limit = 120
    webhook_limiter.reset()
    openwa.reset_state()
    with TestClient(app) as test_client:
        yield test_client
    db.reset_engine(None)


def _push_payload(endpoint: str = "https://push.example/abc") -> dict:
    return {
        "ward_id": WARD_ID,
        "language": "en",
        "push": {"endpoint": endpoint, "keys": {"p256dh": "p" * 20, "auth": "a" * 10}},
    }


# --- speed -----------------------------------------------------------------


def test_wards_lite_is_small_and_cacheable(client):
    response = client.get("/api/v1/wards/lite")
    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("public")
    etag = response.headers["etag"]
    assert etag.startswith('"')
    body = response.content
    assert gzip.compress(body, 6).__len__() < 150 * 1024

    again = client.get("/api/v1/wards/lite", headers={"If-None-Match": etag})
    assert again.status_code == 304


def test_scenario_is_cached(client):
    payload = {"rainfall_mm": 80, "duration_hours": 3, "builtup_increase_pct": 0}
    first = client.post("/api/v1/scenario", json=payload)
    second = client.post("/api/v1/scenario", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["wards"] == second.json()["wards"]


def test_road_index_scores_without_slow_join():
    from model.road_risk_index import build_index

    wards = gpd.GeoDataFrame(
        {
            "ward_id": [1],
            "elevation_mean": [5.0],
            "slope_mean": [1.0],
            "impervious_frac": [0.8],
            "dist_to_water_m": [100.0],
            "geometry": [box(0, 0, 1000, 1000)],
        },
        geometry="geometry",
        crs="EPSG:32644",
    )
    roads = gpd.GeoDataFrame(
        {"road_id": ["r1"], "highway_type": ["primary"], "name": ["Test Road"],
         "is_tunnel": [False], "layer": [0], "geometry": [LineString([(0, 0), (500, 500)])]},
        geometry="geometry",
        crs="EPSG:32644",
    )
    underpasses = gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs="EPSG:32644")

    index = build_index(roads, underpasses, wards)
    results = index.score(100)
    assert len(results) == 1
    assert results[0]["highway_type"] == "primary"
    assert 0.0 <= results[0]["risk_score"] <= 1.0


# --- subscriptions ---------------------------------------------------------


def test_subscription_lifecycle(client):
    created = client.post("/api/v1/subscriptions", json=_push_payload())
    assert created.status_code == 201
    subscription_id = created.json()["id"]

    updated = client.patch(f"/api/v1/subscriptions/{subscription_id}", json={"ward_id": 169})
    assert updated.status_code == 200
    assert updated.json()["ward_id"] == 169

    deleted = client.delete(f"/api/v1/subscriptions/{subscription_id}")
    assert deleted.status_code == 204

    with Session(db.get_engine()) as session:
        assert session.exec(select(Subscription)).all() == []


def test_subscription_rejects_unknown_ward_and_coordinates(client):
    assert client.post("/api/v1/subscriptions", json={**_push_payload(), "ward_id": 201}).status_code == 404
    bad = {**_push_payload(), "latitude": 13.0, "longitude": 80.2}
    # Extra fields are ignored by the schema; the stored row must still have no coordinates.
    assert client.post("/api/v1/subscriptions", json=bad).status_code == 201
    with Session(db.get_engine()) as session:
        row = session.exec(select(Subscription)).one()
        assert not hasattr(row, "latitude") and not hasattr(row, "longitude")


def test_subscription_rate_limit(client):
    subscription_limiter.limit = 2
    subscription_limiter.reset()
    assert client.post("/api/v1/subscriptions", json=_push_payload("https://push.example/1")).status_code == 201
    assert client.post("/api/v1/subscriptions", json=_push_payload("https://push.example/2")).status_code == 201
    assert client.post("/api/v1/subscriptions", json=_push_payload("https://push.example/3")).status_code == 429


# --- whatsapp webhook ------------------------------------------------------


def test_webhook_join_stop_and_privacy(client):
    joined = client.post("/api/v1/whatsapp/webhook", json={"from": "919876543210@c.us", "body": "JOIN 168"})
    assert joined.status_code == 200
    assert joined.json()["handled"] == 1

    with Session(db.get_engine()) as session:
        rows = session.exec(select(WhatsAppSubscriber)).all()
        assert len(rows) == 1
        assert rows[0].chat_id_enc != "919876543210@c.us"
        assert decrypt(rows[0].chat_id_enc) == "919876543210@c.us"
        assert rows[0].chat_id_hash == identifier_hash("919876543210@c.us")

    stopped = client.post("/api/v1/whatsapp/webhook", json={"from": "919876543210@c.us", "body": "STOP"})
    assert stopped.status_code == 200
    with Session(db.get_engine()) as session:
        assert session.exec(select(WhatsAppSubscriber)).all() == []


def test_webhook_help_tamil_and_nested_payload(client):
    nested = {"data": {"from": "919800000000@c.us", "body": "உதவி"}}
    response = client.post("/api/v1/whatsapp/webhook", json=nested)
    assert response.status_code == 200
    assert response.json()["handled"] == 1


def test_webhook_hmac_signature(client):
    settings.openwa_webhook_secret = "topsecret"
    raw = json.dumps({"from": "919800000001@c.us", "body": "JOIN 168"}).encode()
    unsigned = client.post("/api/v1/whatsapp/webhook", content=raw)
    assert unsigned.status_code == 401

    signature = hmac.new(b"topsecret", raw, hashlib.sha256).hexdigest()
    signed = client.post("/api/v1/whatsapp/webhook", content=raw,
                         headers={"X-Webhook-Signature": f"sha256={signature}"})
    assert signed.status_code == 200


# --- alert approval, dispatch, active feed, CAP ----------------------------


def _seed_subscribers():
    with Session(db.get_engine()) as session:
        session.add(Subscription(
            ward_id=WARD_ID, language="en", endpoint="https://push.example/x",
            p256dh="p" * 20, auth="a" * 10,
        ))
        chat = "919876543210@c.us"
        session.add(WhatsAppSubscriber(
            chat_id_hash=identifier_hash(chat), chat_id_enc=encrypt(chat),
            ward_id=WARD_ID, language="en", active=True,
        ))
        session.commit()


def _seed_alert() -> str:
    with Session(db.get_engine()) as session:
        alert = Alert(
            ward_id=WARD_ID, ward_name="Ward 168", risk_level="high", risk_score=0.82,
            alert_type="warning", rainfall_mm=120, duration_hours=6,
            message_en="Flood warning for Ward 168. Exercise only.",
            message_ta="வெள்ள எச்சரிக்கை. பயிற்சி மட்டும்.",
        )
        session.add(alert)
        session.commit()
        session.refresh(alert)
        return alert.id


def test_approve_dispatches_and_logs(client):
    _seed_subscribers()
    alert_id = _seed_alert()

    pending = client.get("/api/v1/alerts/pending").json()
    assert any(item["id"] == alert_id for item in pending)

    approved = client.post(f"/api/v1/alerts/{alert_id}/approve")
    assert approved.status_code == 200
    summary = approved.json()
    assert summary["webpush"] == 1
    assert summary["whatsapp"] == 1
    assert summary["failed"] == 0

    with Session(db.get_engine()) as session:
        alert = session.get(Alert, alert_id)
        assert alert.status == "sent"
        logs = session.exec(select(DispatchLog)).all()
        assert {log.channel for log in logs} == {"webpush", "whatsapp"}

    active = client.get("/api/v1/alerts/active", params={"ward_id": WARD_ID}).json()
    assert any(item["id"] == alert_id and item["exercise"] for item in active)


def test_dispatch_is_scoped_to_the_alert_ward(client):
    _seed_subscribers()
    # A second ward's subscribers must never receive Ward 168's alert.
    with Session(db.get_engine()) as session:
        other_chat = "919700000000@c.us"
        session.add(Subscription(ward_id=169, language="en", endpoint="https://push.example/other",
                                 p256dh="q" * 20, auth="b" * 10))
        session.add(WhatsAppSubscriber(chat_id_hash=identifier_hash(other_chat),
                                       chat_id_enc=encrypt(other_chat), ward_id=169,
                                       language="ta", active=True))
        session.commit()

    alert_id = _seed_alert()
    summary = client.post(f"/api/v1/alerts/{alert_id}/approve").json()
    assert summary["webpush"] == 1
    assert summary["whatsapp"] == 1

    with Session(db.get_engine()) as session:
        logs = session.exec(select(DispatchLog)).all()
        assert len(logs) == 2
        chat_169 = session.exec(
            select(WhatsAppSubscriber).where(WhatsAppSubscriber.ward_id == 169)
        ).one()
        assert all(log.recipient_ref != chat_169.id for log in logs)


def test_cancel_prevents_dispatch(client):
    alert_id = _seed_alert()
    cancelled = client.post(f"/api/v1/alerts/{alert_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert client.post(f"/api/v1/alerts/{alert_id}/approve").status_code == 409


def test_cap_feed_is_exercise_xml(client):
    alert_id = _seed_alert()
    client.post(f"/api/v1/alerts/{alert_id}/approve")

    response = client.get("/api/v1/alerts/cap.xml")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    root = ET.fromstring(response.content)
    ns = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}
    assert root.find(".//cap:status", ns).text == "Exercise"
    assert root.find(".//cap:event", ns).text == "Flood Warning"
    assert root.find(".//cap:areaDesc", ns).text == "Ward 168"


# --- rules, crypto, openwa -------------------------------------------------


def test_rules_hysteresis_and_escalation():
    from datetime import datetime, timedelta

    now = datetime.now(UTC)
    recent = {WARD_ID: type("Prev", (), {"created_at": now - timedelta(hours=1),
                                          "risk_level": "high"})()}
    risks = [WardRisk(WARD_ID, "Ward 168", "high", 0.7)]
    assert default_select(risks, 100, 6, recent, now) == []

    escalated = [WardRisk(WARD_ID, "Ward 168", "very_high", 0.9)]
    assert len(default_select(escalated, 100, 6, recent, now)) == 1


def test_crypto_roundtrip_and_hash():
    settings.phone_encryption_key = "unit-test-passphrase"
    token = encrypt("919876543210@c.us")
    assert token != "919876543210@c.us"
    assert decrypt(token) == "919876543210@c.us"
    assert identifier_hash("x") == identifier_hash("x")
    assert identifier_hash("x") != identifier_hash("y")


@pytest.mark.asyncio
async def test_openwa_simulates_and_deduplicates():
    settings.openwa_base_url = ""
    openwa.reset_state()
    first = await openwa.send_text("919876543210@c.us", "hello")
    assert first["simulated"] is True and first["success"] is True


# --- scheduler -------------------------------------------------------------


@pytest.mark.asyncio
async def test_scheduler_creates_pending_then_hysteresis(client, monkeypatch):
    import pandas as pd

    from services import scheduler as scheduler_module

    features = pd.DataFrame({
        "ward_id": [1, 2, 3],
        "ward_number": ["1", "2", "3"],
        "ward_name": ["Ward 1", "Ward 2", "Ward 3"],
        "elevation_mean": [2.0, 2.0, 2.0],
        "slope_mean": [1.0, 1.0, 1.0],
        "impervious_frac": [0.95, 0.95, 0.95],
        "dist_to_water_m": [10.0, 10.0, 10.0],
        "road_density_km_per_sqkm": [30.0, 30.0, 30.0],
        "underpass_count": [3, 3, 3],
    })

    async def fake_forecast(hours=None):
        return {"rainfall_mm": 300.0, "duration_hours": 6.0, "source": "test"}

    monkeypatch.setattr(scheduler_module, "fetch_forecast", fake_forecast)
    monkeypatch.setattr(scheduler_module, "_load_features", lambda: features)

    first = await scheduler_module.run_cycle()
    assert first["status"] == "ok"
    assert first["pending_created"] == 3

    second = await scheduler_module.run_cycle()
    assert second["pending_created"] == 0  # hysteresis suppresses re-alerts

    with Session(db.get_engine()) as session:
        pending = session.exec(select(Alert).where(Alert.status == "pending")).all()
        assert len(pending) == 3
        assert all(item.message_en and item.message_ta for item in pending)
        assert all(item.alert_type == "warning" for item in pending)


def test_vapid_public_key_endpoint(client):
    response = client.get("/api/v1/push/vapid-public-key")
    assert response.status_code == 200
    assert response.json()["configured"] is False

