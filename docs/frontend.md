# Frontend

React 18 + Vite + TypeScript + Tailwind + react-leaflet, in `web/`. Owner: Ronit.

## Run it

```bash
cd web
npm install
npm run dev          # http://localhost:5173, proxies /api to http://localhost:8000
```

With the FastAPI backend running (`uvicorn api.main:app --port 8000` from the repo root) the header shows **Live API**. Without it, the app switches to the bundled mock and shows **Mock data**.

| Command | What it does |
| --- | --- |
| `npm run dev` | Dev server with hot reload |
| `npm test` | Vitest (watch mode); `npm test -- --run` for CI |
| `npm run lint` | ESLint, zero warnings allowed |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run build` | Production build into `dist/` |
| `npm run preview` | Serves `dist/` on :4173 **with the production security headers** from `vercel.json` |

### Environment variables (build time)

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_API_URL` | `/api/v1` | Backend base URL. On Vercel set it to the Render URL, e.g. `https://flood-api.onrender.com/api/v1` |
| `VITE_USE_MOCK` | unset | `true` forces the offline mock (demo without a backend) |
| `VITE_SENTRY_DSN` | unset | Enables Sentry error reporting. Without it Sentry is not even downloaded |
| `VITE_ENABLE_CROWD_REPORTS` | unset | `true` shows the Tier 3 crowd-report preview |

## How the screen maps to the rubric

| Screen element | Component | Criterion |
| --- | --- | --- |
| Rainfall input: manual amount + duration, CSV upload, Open-Meteo forecast | `RainfallControl` | 4, problem statement §5 "Rainfall input" |
| Colour-graded ward map, tooltips | `MapView` | 4 |
| Ranked list with search and High+ filter | `RankedList` | 4 |
| Ward detail: uncalibrated index/category and reasons; physical proxies suppressed | `WardDetailPanel` | 4 |
| "Why this ward?": weighted factor bars beside the model's `reasons[]` | `ExplainabilityPanel` | 5 |
| English/Tamil SMS and WhatsApp drafts, copy, share link, channel readiness | `AlertPanel`, `ChannelStatus` | 4 |
| Today vs +15% / +30% built-up, with "N wards get worse" | `FutureScenarioToggle` | 6, stretch goal |
| Roads and underpasses: uncalibrated screening requiring review, no depth/closure instruction | `MapView` road layer | 1, 4, stretch goal |
| Shelter candidates and directions links, without verified availability/capacity/safe routes | `ShelterPanel` | 1, 4, stretch goal |
| Live API vs mock, rainfall provider | `ProviderBadge` | honesty in the demo |
| Evidence status, nullable observed-sample metrics and coverage; mock accuracy suppressed | `ValidationPanel` | 3 |

## Resident app and phone alerts (docs/ACTION_PLAN_ALERTS.md, Ronit's part)

Phones open the **Resident** screen by default; laptops open the **Official** dashboard. Both can switch, and the choice is remembered on the device.

| Piece | Where | Notes |
| --- | --- | --- |
| Resident screen | `components/resident/ResidentView.tsx` | My ward, plain-language estimate from the live Open-Meteo forecast, Where do I go? (shelters), Get alerts, call 1913 / 112 |
| On-device ward lookup | `lib/wardLookup.ts` | Point-in-polygon on cached ward shapes; only the ward ID ever leaves the phone. Points up to 150 m outside a ward (gaps, GPS error) snap to the nearest ward; further away = "outside Chennai" |
| Tamil / English | `lib/i18n.ts` | Every key has a Tamil string (enforced by TypeScript and `i18n.test.ts`); native-speaker review still needed |
| Subscribe flow | `components/resident/SubscribeSheet.tsx`, `lib/push.ts` | Web Push when `VITE_VAPID_PUBLIC_KEY` is set; otherwise the page shows notifications itself (preview). WhatsApp opt-in via a `JOIN <ward>` deep link to `VITE_WHATSAPP_NUMBER` |
| Follow location | `components/resident/hooks.ts` | While the app is open, two readings in a new ward move the subscription (max once a minute). Browsers can't do this in the background |
| Alert page | `components/AlertScreen.tsx` | Full screen; opened by a notification (`/?alert=<id>`), a new alert for my ward, or the banner. Drill banner on exercise alerts; general safety tips only |
| Official approval | `components/AlertQueuePanel.tsx` | "Check wards for alerts" → pending EN/TA texts → Approve & send / Cancel. Nothing reaches phones without approval |
| PWA | `public/manifest.webmanifest`, `public/sw.js`, `public/icons/` | Installable; offline app shell; ward shapes cached (stale-while-revalidate); last known alerts cached; push and notification-click handlers |

### Endpoints from the plan that the backend doesn't have yet

`api/client.ts` calls the planned endpoints (`/wards/lite`, `/subscriptions`, `/alerts/check`, `/alerts/pending`, `/alerts/{id}/approve|cancel`, `/alerts/active`, `/alerts/{id}`). If the live server answers 404/405/501, the call falls back to `api/mockAlerts.ts`, an in-browser stand-in stored in localStorage (so an official tab and a resident tab on one laptop see the same alerts in a demo), and the UI shows a **Preview** note. `/wards/lite` falls back to the full `/wards` (also on the 422 FastAPI currently returns for it). Once John's endpoints exist, the same UI uses them with no code change.

The preview's alert rule (high → Watch, very high → Warning, no repeat within 6 h unless it worsens, max 25 wards per run) is a placeholder for Mit's `model/alert_rules.py`.

### Offline and demo data
- Offline phones stay on real data and use the service worker's cached copies; they never switch to the synthetic demo.
- When the backend is unreachable while online, residents see an amber **"Demo data"** notice.

### New environment variables
| Variable | Purpose |
| --- | --- |
| `VITE_VAPID_PUBLIC_KEY` | Public key for Web Push subscriptions (matches the backend's private key) |
| `VITE_WHATSAPP_NUMBER` | The OpenWA alert number residents message with `JOIN <ward>` |
| `VITE_ENABLE_SW` | `true` to register the service worker in `npm run dev` (it always registers in production builds) |

### Measured
- Phone path: about 98 KB gzipped JS (the map library loads only for officials).
- Lighthouse mobile on the resident screen: performance 99, accessibility 100, best practices 96, SEO 100.
- Real headless Chrome: the service worker installs and takes control; with the network off, the app opens and shows the saved real ward.

## Data flow

```
RainfallControl ──reading──▶ App.runAnalysis ──▶ api.getScenarioRisk (0% = today)
                                                  │ (0% baseline fetched too for +15/+30%)
                                                  ▼
                                     zustand store (lib/store.ts)
                       ┌───────────────┬───────────┴──────────┬──────────────┐
                    MapView        RankedList         WardDetailPanel    FutureScenarioToggle
```

Ward analyses go through `/scenario`, with `builtup_increase_pct: 0` meaning baseline land use.
Both `/risk` and `/scenario` forward duration. AlertPanel passes the analyzed response's
rainfall/duration (not unsubmitted control edits) to `/alerts`; omitted alert duration
defaults to 3 hours. Live and mock alert scoring use that interval, and messages identify
the total accumulation/interval. Alerts remain baseline land use, so built-up scenario
map categories may differ. Road screening retains its separate endpoint/default interval;
it is not a duration-aware physical road forecast. Compatibility depth fields remain in
responses but are not displayed as predictions. Manual 300 mm is explicitly hypothetical.

The rainfall factor follows `model/risk_engine.py`: `(mm / 200) × clamp(sqrt(3 / hours), 0.5, 1.5)`, capped at 1.5. The explainability panel shows it, and `lib/explain.test.ts` checks 27 cases (1–24 h, 0–30% built-up) against outputs recorded from the Python engine.

The **Validation** panel renders unavailable/partial/evaluated evidence states. Mock,
unsupported legacy and malformed metrics never become accuracy cards. Schema-2 null
metrics retain reasons; denominators/coverage and supplied event metadata are shown
without a hardcoded validated event. Canonical metrics are still mock, so current live
evidence is unavailable. Evaluated status does not certify the underlying observations.

`api/client.ts` calls `/readyz` once per page load. If the backend answers with `features` and `wards` ready it uses the live API for the whole session; otherwise it uses `api/mock.ts`. The two sources are never mixed, so you never see live wards with mock scores.

`api/mock.ts` produces 200 synthetic grid "wards" over Chennai. Its scoring calls the same functions as the explainability panel (`lib/explain.ts`), which mirror `model/risk_engine.py`. `lib/explain.test.ts` checks that against outputs recorded from the Python engine. **The mock is for offline demos and tests only; the polygons are not real ward boundaries.**

## Security

The frontend treats everything from the API and the user as untrusted:

- **Every API response is validated** (`api/validate.ts`) before the UI uses it. A wrong shape (an HTML page from a misconfigured proxy, `wards: null`) becomes a clear error banner and the previous result stays on screen. Out-of-range values are clamped, unknown risk levels are re-derived from the score, undrawable geometry is dropped, and text is length-limited. Before this, any of these crashed the whole dashboard.

- **Ward names** come from OpenStreetMap. React escapes text automatically. Leaflet tooltips take raw HTML, so they go through `escapeHtml` (`lib/tooltip.ts`).
- **WhatsApp links** from the API are only used if they are `https://wa.me/?text=…` or `https://api.whatsapp.com/send?text=…` with **no recipient number**. Anything else (a `javascript:` URL, a look-alike host, or a pre-filled phone number) is replaced by a share link built from the message text. The official chooses who receives an alert. All outbound links use `rel="noopener noreferrer"`.
- **CSV upload** is limited to 64 KB and 24 rows. Each value must be a finite, non-negative number of plausible size, and the total must be ≤ 500 mm (the API limit). Errors name the bad row.
- **Manual input** is clamped to the API limits: 0–500 mm and 1–24 h.
- **Crowd reports** are stripped of control characters, limited to 280 characters and 20 per session, and kept in the tab only.
- **Location** is requested only when the user presses "Use my location", and it is never sent anywhere except the backend's `/shelters` call.
- **Headers** (`vercel.json`): a strict CSP (`script-src 'self'`, with explicit hosts for tiles, Open-Meteo, Render and Sentry), `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, and COOP. `npm run preview` serves the same headers, so CSP breakage shows up locally.

If the backend moves somewhere other than `*.onrender.com`, add its origin to `connect-src` in `vercel.json`.

## Tests

`npm test -- --run` runs the current suite; exact latest counts are recorded in
`docs/mit_implementation_plan.md` rather than promised as a permanent inventory:

| File | Covers |
| --- | --- |
| `lib/explain.test.ts` | Parity with `model/risk_engine.py` outputs (fixture generated from the Python engine); factor sums; scenario effect |
| `lib/safe.test.ts` | HTML escaping; WhatsApp URL allow-list including `javascript:`, `data:`, look-alike hosts, credentials, ports and pre-addressed numbers |
| `lib/rainfall.test.ts` | CSV formats (BOM, CRLF, quotes, `;` and tab) and rejection cases; Open-Meteo parsing and stale forecasts |
| `lib/tooltip.test.ts` | Hostile ward names stay text in map tooltips |
| `api/client.test.ts` | Live/mock decision (up, down, 500, not ready); single readiness probe; no silent fallback after going live; request bodies match the FastAPI schemas |
| `App.test.tsx` | User flows: analyse, rank, monotonic risk with more rain, search/filter with hostile input, scenario delta, ward explanation, Tamil alert with copy and share, API link injection, CSV and forecast input, failure states |
| `components/panels.test.tsx` | Crowd-report validation and spam cap, shelter links, location-permission denial, no location prompt until asked |

To regenerate the Python parity fixture after changing the model:

```bash
python web/scripts/python_parity_fixture.py   # from the repo root, with the backend's Python deps installed
```

## Current evidence and operational limits

- Reviewed historical labels and approved event alignment remain absent; station candidates
  are not adopted ward rainfall. Do not edit canonical mock metrics to simulate evaluation.
- Tamil live/mock templates require native-speaker review. Message generation, timestamps,
  copy/share links and channel status cards do not establish notification delivery.
- Shelter presence/opening/capacity and route safety are unverified; an empty live result
  is not evidence of no shelters. Mock shelter names are demonstration data.
- No latency, Lighthouse score, deployment headers or live-browser behavior is promised
  by a local build. Run and record the relevant measurement before making such claims.
- Index 1.0 is very_high. Categories are ordinal prototype bins, not validated warnings.
