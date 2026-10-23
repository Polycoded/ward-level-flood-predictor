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
POST   /api/v1/alerts/{id}/approve     header X-Admin-Token required
POST   /api/v1/alerts/{id}/cancel      header X-Admin-Token required
GET    /api/v1/alerts/cap.xml
```

### Operator authentication

Approving an alert broadcasts it to every subscriber in a ward, and cancelling
one suppresses a warning, so both require the operator token:

- Set `ADMIN_API_TOKEN` on the server to a long random value
  (`python -c "import secrets; print(secrets.token_urlsafe(32))"`).
- Officials paste it once into **Approve alerts → Operator key** in the
  dashboard. It stays in that browser only and is sent as `X-Admin-Token` on
  approve/cancel — it is never built into the website.
- Missing or wrong token: `401`. No token configured on the server: `503`
  (fails closed — approvals are refused, never left open).

### Push endpoint SSRF guard

The server makes outbound requests to each subscription's push `endpoint`, so
`POST /subscriptions` only accepts `https` endpoints that cannot point inside
the network: private, loopback, link-local (cloud metadata `169.254.169.254`)
and reserved IPs, obfuscated forms such as `2130706433` or `0x7f000001`, and
`localhost`/`metadata.google.internal` are rejected with `422`. Before every
real send the endpoint is checked again with DNS, so a public name that
resolves to an internal address (or an old row stored before this check) is
blocked and deactivated instead of contacted.

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
dispatch logging, active feed, CAP XML, hysteresis, the scheduler cycle,
operator-token checks on approve/cancel (401/503, fail closed), and the push
endpoint SSRF guard at input and send time.

## Limits and risks

- Browsers cannot track location in the background; the PWA resolves the ward
  while open and falls back to the saved home ward.
- iPhone push requires "Add to Home Screen" (iOS 16.4+).
- OpenWA is unofficial and can get the number banned — dedicated SIM, inbound
  opt-in, pacing, push/SMS fallbacks, official Cloud API for production.
- `STOP` deletes the WhatsApp subscriber row; `DELETE /subscriptions/{id}`
  removes the browser subscription.
