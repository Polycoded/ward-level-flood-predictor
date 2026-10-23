# Alerts, subscriptions and speed (John's implementation)

Everything here is **Exercise** mode by default (`EXERCISE_MODE=true`). No raw
coordinates are accepted or stored; only a ward ID is persisted.

## What was built

| Area | Implementation |
|---|---|
| Fast ward shapes | `GET /api/v1/wards/lite` — simplified (~10 m), coords rounded to 5 dp, `ETag` + `Cache-Control: public, max-age=86400`, `304` on `If-None-Match` |
| Road speed | `model/road_risk_index.py` precomputes the road→ward join, underpass distance, base score and WGS84 geometry once; per request only applies the rainfall factor |
| Scenario speed | bounded TTL cache keyed by (dataset, rainfall, duration, built-up %) |
| Database | SQLModel: `Subscription`, `WhatsAppSubscriber`, `Alert`, `DispatchLog` (`api/db.py`); SQLite locally, `DATABASE_URL` for Postgres on Render |
| Subscriptions | `POST/PATCH/DELETE /api/v1/subscriptions` (rate-limited, ward-only) |
| Push | `integrations/webpush.py` with VAPID; expired endpoints (404/410) are deactivated |
| OpenWA | `integrations/openwa.py` — paced (3–5 s + jitter), retries, idempotency keys, health probe |
| WhatsApp webhook | `POST /api/v1/whatsapp/webhook` — HMAC-SHA256, `JOIN <ward>` / `STOP` / `HELP` in English and Tamil |
| Scheduler | `services/scheduler.py` every 15 min: Open-Meteo → `score_wards` → Mit's rules → pending alerts |
| Dispatcher | `services/dispatcher.py` on approval: push + WhatsApp + SMS fallback, every attempt logged |
| Approval | `GET /alerts/pending`, `POST /alerts/{id}/approve`, `POST /alerts/{id}/cancel`, `GET /alerts/active` |
| CAP feed | `GET /api/v1/alerts/cap.xml`, CAP 1.2, `status=Exercise` until changed |
| Privacy | WhatsApp IDs encrypted at rest (`integrations/crypto.py`); `STOP` deletes the row |
| Readiness | `/readyz` now reports `database`, `openwa`, `exercise_mode` |

## Endpoints

```
GET    /api/v1/wards/lite
GET    /api/v1/push/vapid-public-key
POST   /api/v1/subscriptions
PATCH  /api/v1/subscriptions/{id}
DELETE /api/v1/subscriptions/{id}
POST   /api/v1/whatsapp/webhook
GET    /api/v1/alerts/pending
GET    /api/v1/alerts/active?ward_id=
GET    /api/v1/alerts/{id}
POST   /api/v1/alerts/{id}/approve
POST   /api/v1/alerts/{id}/cancel
GET    /api/v1/alerts/cap.xml
```

## Local run

```bash
# 1. Database (SQLite by default)
cp .env.example .env        # set PHONE_ENCRYPTION_KEY, VAPID keys, OpenWA values

# 2. Generate VAPID keys once
uv run python -m py_vapid --gen --applicationServerKey

# 3. API (scheduler off by default)
uv run uvicorn api.main:app --reload

# 4. Optional OpenWA sidecar (unofficial; dedicated SIM)
docker compose -f docker-compose.openwa.yml up -d
```

Enable the scheduler with `ENABLE_SCHEDULER=true`. It will create **pending**
alerts only; nothing is sent until an official approves.

## OpenWA contract expected by `integrations/openwa.py`

```
GET  {OPENWA_BASE_URL}/health
POST {OPENWA_BASE_URL}/messages/send
     headers: X-API-Key, Idempotency-Key
     body:    {"session": "...", "chatId": "...", "text": "..."}
```

If the chosen fork uses different paths, adapt the two URLs in
`integrations/openwa.py` (and `probe()`).

## Testing

```bash
.venv\Scripts\python.exe -m pytest tests/test_alerting_features.py -v
```

Covers: lite-shape size/ETag, scenario cache, road index, subscription CRUD and
rate limiting, webhook JOIN/STOP/HELP + HMAC, encrypted identifiers, approval
dispatch logging, active feed, CAP XML, hysteresis, and the scheduler cycle.

## Limits and risks

- Browsers cannot track location in the background; the PWA resolves the ward
  while open and falls back to the saved home ward.
- iPhone push requires "Add to Home Screen" (iOS 16.4+).
- OpenWA is unofficial and can get the number banned — dedicated SIM, inbound
  opt-in, pacing, push/SMS fallbacks, official Cloud API for production.
- `STOP` deletes the WhatsApp subscriber row; `DELETE /subscriptions/{id}`
  removes the browser subscription.
