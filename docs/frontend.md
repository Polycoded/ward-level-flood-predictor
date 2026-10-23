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
| Ward detail: risk level and score; depth band and peak window labelled *indicative* (display proxies per `docs/model_logic.md`) | `WardDetailPanel` | 4 |
| "Why this ward?": weighted factor bars beside the model's `reasons[]` | `ExplainabilityPanel` | 5 |
| English/Tamil SMS and WhatsApp drafts, copy, share link, channel readiness | `AlertPanel`, `ChannelStatus` | 4 |
| Today vs +15% / +30% built-up, with "N wards get worse" | `FutureScenarioToggle` | 6, stretch goal |
| Roads and underpasses coloured by risk, "close/divert" hint | `MapView` road layer | 1, 4, stretch goal |
| Nearest shelters, walking time, OSM directions link | `ShelterPanel` | 1, 4, stretch goal |
| Live API vs mock, rainfall provider | `ProviderBadge` | honesty in the demo |
| Dec 2023 validation metrics | `ValidationPanel` | 3 |

## Data flow

```
RainfallControl ──reading──▶ App.runAnalysis ──▶ api.getScenarioRisk (0% = today)
                                                  │ (0% baseline fetched too for +15/+30%)
                                                  ▼
                                     zustand store (lib/store.ts)
                       ┌───────────────┬───────────┴──────────┬──────────────┐
                    MapView        RankedList         WardDetailPanel    FutureScenarioToggle
```

All analyses go through `/scenario`, with `builtup_increase_pct: 0` meaning today's land use. `/risk` currently drops `duration_hours` while `/scenario` applies it, so mixing the two made "+15% built-up" look safer than today for long storms. Using one endpoint keeps the comparison honest whichever way `/risk` is fixed.

The rainfall factor follows `model/risk_engine.py`: `(mm / 200) × clamp(sqrt(3 / hours), 0.5, 1.5)`, capped at 1.5. The explainability panel shows it, and `lib/explain.test.ts` checks 27 cases (1–24 h, 0–30% built-up) against outputs recorded from the Python engine.

The **Validation** panel labels metrics as placeholders, with a warning, when the app is in mock mode or the file's `notes` say mock/placeholder/template. The `validation_metrics.json` currently on `main` holds the frontend's mock numbers, so it is flagged.

`api/client.ts` calls `/readyz` once per page load. If the backend answers with `features` and `wards` ready it uses the live API for the whole session; otherwise it uses `api/mock.ts`. The two sources are never mixed, so you never see live wards with mock scores.

`api/mock.ts` produces 200 synthetic grid "wards" over Chennai. Its scoring calls the same functions as the explainability panel (`lib/explain.ts`), which mirror `model/risk_engine.py`. `lib/explain.test.ts` checks that against outputs recorded from the Python engine. **The mock is for offline demos and tests only; the polygons are not real ward boundaries.**

## Security

The frontend treats everything from the API and the user as untrusted:

- **Ward names** come from OpenStreetMap. React escapes text automatically. Leaflet tooltips take raw HTML, so they go through `escapeHtml` (`lib/tooltip.ts`).
- **WhatsApp links** from the API are only used if they are `https://wa.me/?text=…` or `https://api.whatsapp.com/send?text=…` with **no recipient number**. Anything else (a `javascript:` URL, a look-alike host, or a pre-filled phone number) is replaced by a share link built from the message text. The official chooses who receives an alert. All outbound links use `rel="noopener noreferrer"`.
- **CSV upload** is limited to 64 KB and 24 rows. Each value must be a finite, non-negative number of plausible size, and the total must be ≤ 500 mm (the API limit). Errors name the bad row.
- **Manual input** is clamped to the API limits: 0–500 mm and 1–24 h.
- **Crowd reports** are stripped of control characters, limited to 280 characters and 20 per session, and kept in the tab only.
- **Location** is requested only when the user presses "Use my location", and it is never sent anywhere except the backend's `/shelters` call.
- **Headers** (`vercel.json`): a strict CSP (`script-src 'self'`, with explicit hosts for tiles, Open-Meteo, Render and Sentry), `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, and COOP. `npm run preview` serves the same headers, so CSP breakage shows up locally.

If the backend moves somewhere other than `*.onrender.com`, add its origin to `connect-src` in `vercel.json`.

## Tests

`npm test -- --run` runs 85 tests:

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

## Known gaps (backend side, tracked in the PR)

- `data/processed/validation_metrics.json` on `main` contains mock numbers; the UI flags them as placeholders until the real evaluation replaces the file.
- `/risk` ignores `duration_hours` (the dashboard uses `/scenario` instead; see above).
- `model/alerts.py` "Tamil" templates are Chinese text. The mock's Tamil is correct but still needs a native-speaker review.
- `/wards` is ~650 KB uncompressed; adding `GZipMiddleware` to `api/main.py` cuts it to ~77 KB. Lighthouse on the production build (offline mode): mobile 91–94 performance / 100 accessibility, desktop 99–100. The uncompressed payload is the main thing slowing the live version on mobile.
- `risk_engine.py` labels a score of exactly 1.0 (any extreme storm) as `very_low`.
