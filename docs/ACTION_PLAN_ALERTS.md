# Action plan: phone alerts, WhatsApp alerts, resident UX and speed

Goal: when a ward crosses a flood-risk threshold, people **in that ward** get an alert on their phone (push notification and WhatsApp) telling them what to do and where the nearest shelter is, in Tamil or English. Officials approve each broadcast. The app is fast and simple enough for any resident.

Based on `main` at `de4cb04`. Measurements below were taken on that commit.

---

## 1. How the real-world systems work, and what we can build

| System | How it reaches phones | Needs an app? | Uses your location? |
|---|---|---|---|
| Japan J-Alert / ETWS, US & Hawaii WEA, Israel | **Cell Broadcast**: the mobile operator broadcasts to every phone connected to towers in the danger area | No | No, the tower area decides |
| Israel Home Front Command app | App + push notification for the user's current and chosen areas | Yes | Yes, on the device |
| India | NDMA **SACHET** (CAP format) → operators' cell broadcast (C-DOT system), SMS, TV/DTH | No | No |
| Where Is My Train | Works out position **on the phone** (from cell towers, offline) and only uses data it already has | Yes | Yes, but processed on the device |

**What a hackathon team can build:** we can't send cell broadcasts (only the government and operators can). We build two things:

1. **Our own location-based alerts:** an installable web app (PWA). The phone works out its ward **on the device**, like Where Is My Train, and the server only learns *"someone in Ward 168 wants alerts"*, never their coordinates. Alerts arrive as push notifications and WhatsApp messages.
2. **A CAP feed** (`/alerts/cap.xml`): the standard format SACHET and cell broadcast accept. It's the honest bridge to the Israel/Japan-style system, which only the authorities can switch on.

### Limits to state up front
- Browsers **cannot track location in the background**. The app updates the user's ward while it's open and falls back to their saved "home ward" otherwise. True background geofencing needs a native wrapper (Capacitor) later.
- iPhone push works only after the user installs the app to the home screen (iOS 16.4+). Android Chrome works in the browser.
- **OpenWA is unofficial.** It drives WhatsApp Web (whatsapp-web.js or Baileys), and its README warns of a non-zero risk of the number being banned. Mitigations: a dedicated SIM; people **opt in by messaging us first**; paced sending; push and SMS as fallbacks; Meta's official Cloud API for any production use.

---

## 2. Architecture

```
                    ┌──────────── every 15 min ────────────┐
Open-Meteo forecast ─► Alert engine (score wards, thresholds,├─► Pending alerts ──► Official approves in dashboard
                    │  hysteresis, de-duplicate)           │                       │
                    └──────────────────────────────────────┘                       ▼
                                                                         Dispatcher (queue, pacing, retries)
                                                                ┌────────────────┼──────────────────┐
                                                                ▼                ▼                  ▼
                                                     Web Push (VAPID)   OpenWA → WhatsApp   CAP feed (/alerts/cap.xml)
                                                                │                │
Resident's phone (PWA) ◄────────────────────────────────────────┘                │
  • location → ward on device (cached ward shapes, works offline)                │
  • sends only {ward_id, language, push subscription}                            │
  • full-screen alert: what to do + nearest shelter                              │
WhatsApp user ── "JOIN 168" ──► OpenWA webhook ──► subscribe ward 168 ◄──────────┘
```

### New API contracts (agree on these first, on day 0)

| Endpoint | Owner | Purpose |
|---|---|---|
| `GET /api/v1/wards/lite` | John | Simplified ward shapes for the phone (target < 150 KB gzipped), long cache |
| `POST /api/v1/subscriptions` `{ward_id, language, push: {endpoint, keys}}` → `{id}` | John | Subscribe this device to a ward. **No coordinates.** |
| `PATCH /api/v1/subscriptions/{id}` `{ward_id}` | John | Phone moved to another ward (rate-limited) |
| `DELETE /api/v1/subscriptions/{id}` | John | Unsubscribe and delete data |
| `POST /api/v1/whatsapp/webhook` | John | OpenWA inbound messages (HMAC-verified): `JOIN <ward>`, `STOP`, `HELP` |
| `GET /api/v1/alerts/pending` · `POST /api/v1/alerts/{id}/approve` · `.../cancel` | John (API), Mit (rules) | Human-in-the-loop broadcast |
| `GET /api/v1/alerts/active?ward_id=` | John | What the resident screen shows |
| `GET /api/v1/alerts/cap.xml` | Mit (content), John (endpoint) | CAP 1.2 feed for SACHET, `status=Exercise` until approved for real |

Storage: a small database for subscriptions and alerts. SQLite locally; **Postgres on Render** (its disk is wiped on redeploy). Phone numbers are encrypted at rest.

---

## 3. Speed: measured now and targets

| Item | Now | Target | Fix |
|---|---|---|---|
| `GET /wards` | **931 KB gzip / 2.9 MB raw, 199 ms** | < 150 KB gzip | Simplify shapes (~10 m tolerance), round to 5 decimals, drop the junk Z coordinate, `Cache-Control` + ETag |
| `GET /roads/risk` | **1,716 ms** | < 50 ms | Precompute the road-to-ward join once at startup; cache per rainfall |
| `POST /scenario` | 13 ms | keep | Small cache per (rain, duration, built-up) |
| Frontend main bundle | 138 KB gzip | ≤ 120 KB | Lazy-load the map on the resident screen; service worker caches the app and ward shapes, so repeat visits load instantly and work offline |
| Lighthouse mobile | 91–94 | ≥ 95 | All of the above |

---

## 4. Resident UX (simple for locals)

A **Resident** screen becomes the default on phones; the current dashboard becomes the **Official** view.

- One big card: **"Your ward: Ward 168 · HIGH risk tonight"**, colour-coded, in Tamil or English (the whole app is translated, not just the alerts).
- Three actions, large buttons: **Where do I go?** (nearest shelter with walking directions) · **Get alerts** (location or choose ward, push and/or WhatsApp) · **Call helpline** (GCC 1913).
- Plain words: say "Avoid underpasses and low roads tonight", not "uncalibrated index". The technical wording moves behind an info icon.
- The alert itself is a **full-screen** page: what's happening, what to do now, nearest shelter, "I'm safe" button.
- Accessibility: large text, high contrast, icons with labels, works one-handed, readable by screen readers, works on cheap Android phones and slow 3G.

---

## 5. Work split

### John: pipeline, API, deploy, integrations
1. **Backend speed:** `/wards/lite` with simplified shapes; caching headers; precompute roads (1.7 s → < 50 ms); scenario cache.
2. **Database and models:** subscriptions, WhatsApp subscribers, alerts, dispatch log (SQLModel). Postgres on Render.
3. **OpenWA service:** Docker deploy with a dedicated SIM, persistent session volume, API key and webhook secret in env; health check in `/readyz`.
4. **`integrations/openwa.py`:** `send_text(chat_id, text)` with pacing (one message every 3–5 s with jitter), retries, idempotency keys; a status probe.
5. **Webhook:** HMAC check; `JOIN <ward>` / `STOP` / `HELP` in English and Tamil; confirmation reply.
6. **Web Push:** VAPID keys and `pywebpush` sender; remove expired subscriptions.
7. **Scheduler:** every 15 min, fetch the Open-Meteo forecast, call Mit's alert rules, create pending alerts.
8. **Dispatcher:** on approval, fan out to push, WhatsApp, the CAP feed and the existing Twilio SMS fallback; log every delivery.
9. **Security:** rate limits on the subscription endpoints, encrypted phone numbers, `CORS_ORIGINS` set to the Vercel URL, deletion on `STOP`/unsubscribe.

### Mit: model, alert rules, validation, message content
1. **Alert rules (`model/alert_rules.py`):** which risk level triggers which alert type (Watch / Warning); **hysteresis**, so a ward isn't re-alerted unless it worsens or after N hours; minimum rainfall; maximum wards per broadcast.
2. **False-alarm review:** run the rules on Dec 2023 rainfall and a few dry days; report how many wards would have been alerted; tune before the demo.
3. **Message content:** short EN and TA texts that fit one SMS where possible (Tamil = 70 characters), one action per message, shelter link; native-speaker review.
4. **CAP 1.2 mapping:** event, severity from risk level, certainty `Possible` (uncalibrated), area polygon from the ward, `status=Exercise`; schema validation tests.
5. **Ward lookup correctness:** test point-in-polygon on the simplified shapes against the full shapes (points near boundaries, gaps between wards, outside Chennai), so simplification never puts someone in the wrong ward.
6. **Forecast input:** decide forecast window and duration (e.g. next 6 h) and how Open-Meteo totals map to `rainfall_mm` and `duration_hours`.

### Ronit: UI, UX, alerts experience, PWA, demo, observability
1. **PWA:** manifest, icons, service worker caching the app shell, `wards/lite` and the last results, so it works offline and opens instantly. Install prompt.
2. **On-device location → ward:** point-in-polygon in the browser on cached shapes; `watchPosition` while open; only the ward ID leaves the phone; "choose my ward" fallback; clear permission explanations.
3. **Subscribe flow:** push permission, ward, language; WhatsApp opt-in via a "Message us JOIN 168" deep link (the user messages first, which lowers ban risk); unsubscribe.
4. **Resident screen** (default on phones) and the full-screen **alert page**, with shelter directions.
5. **Full Tamil/English translation** of the UI (i18n), plain-language copy, large touch targets.
6. **Official view:** pending-alerts queue with "Approve & send" / "Cancel", ward list, preview of the exact messages, and delivery status per channel.
7. **Frontend speed:** lazy-load the map for residents; trim the bundle; Lighthouse ≥ 95 mobile.
8. **Tests:** ward-lookup tests on the client, subscription flow, offline mode, the alert page, the approval flow; keep the hostile-input tests passing.
9. **Demo:** two phones (Android + iPhone with the app installed) subscribed to different wards; a dedicated WhatsApp demo number; **Exercise** mode banner on everything.

---

## 6. Order of work

| Phase | John | Mit | Ronit |
|---|---|---|---|
| **0. Contracts** (½ day, together) | Agree on the endpoint shapes above | Agree on alert levels and message fields | Agree on screens; mock the new endpoints in `api/mock.ts` |
| **1. Foundations** (parallel) | `/wards/lite`, caching, roads precompute; database; OpenWA running on a test SIM | `alert_rules.py` + tests; message texts; CAP mapping | PWA + offline cache; on-device ward lookup; resident screen; i18n |
| **2. Delivery** | Subscriptions API, webhook, Web Push, dispatcher, scheduler | Dec 2023 false-alarm review; tune thresholds | Subscribe flow, alert page, official approval view |
| **3. End to end** | Deploy everything (Render + Vercel + OpenWA) | Final message review (Tamil) | Two-phone demo rehearsal; Lighthouse; tests |

**Definition of done:** an official approves an alert for Ward X, and **within 60 seconds** a phone in Ward X gets a push notification and a WhatsApp message, while a phone in Ward Y gets nothing. All of it is labelled *Exercise*, and no raw location is stored anywhere.

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| WhatsApp number banned (OpenWA is unofficial) | Dedicated SIM; opt-in by inbound message; pacing on; push + SMS fallback; official Cloud API for production |
| False alarms make people ignore alerts | Mit's thresholds + hysteresis; human approval; Watch vs Warning levels |
| Privacy (DPDP Act 2023) | Only the ward ID is stored, never coordinates; explicit consent; one-tap delete; numbers encrypted |
| iPhone users without the installed app get no push | WhatsApp opt-in; clear "Add to Home Screen" guide |
| Render free tier sleeps | Keep-alive ping, or a paid instance for the demo |
| Demo network fails | Exercise mode works with pre-cached data; backup screen recording |
