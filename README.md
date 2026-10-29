# Chennai Ward-Level Flood Predictor

A ward-level flood early-warning prototype for Chennai's 200 wards. It combines
terrain, land use, drainage/infrastructure and rainfall to score flood risk,
shows residents a simple phone-first view, and lets officials approve alerts that
go out by push notification, WhatsApp, SMS and a CAP feed.

> Everything the alerting stack sends is labelled **Exercise**. The risk score is
> an uncalibrated index, not a calibrated flood probability or forecast.

## Features

- **200 real wards** from the official GCC 2022 ward and zone maps.
- **Uncalibrated risk index** over six measurements: elevation, slope,
  impervious fraction, distance to water, road density and underpass count.
- **Rainfall scenarios** (amount, duration, built-up increase) with explainable
  per-ward reasoning.
- **Resident experience**: phone-first view, Tamil/English, ward picked on the
  device (only the ward ID leaves the phone), nearest relief camp.
- **Officials-in-the-loop alerts**: scheduler creates pending alerts; an official
  approves or cancels; delivery is logged per channel.
- **Delivery channels**: Web Push (VAPID), WhatsApp via OpenWA, Twilio SMS
  fallback, and a CAP 1.2 feed (`status=Exercise`).
- **Voice agent**: speaks the alert and answers questions ("give me directions")
  using DeepSeek for the LLM, local faster-whisper for speech-to-text and Edge TTS
  for speech.
- **Fast endpoints**: simplified ward shapes (`/wards/lite`, ~117 KB gzip) and a
  precomputed road risk index (cached requests ~25 ms).
- **Road/underpass risk**, shelter lookup, and a separate reproducible
  [logistic-regression research package](research/logistic_regression/README.md).

## Alerts and voice

The alert pipeline is documented in [docs/alerts.md](docs/alerts.md). In short:

```
Open-Meteo -> scheduler (every 15 min) -> pending alerts -> official approval
            -> Web Push + WhatsApp + SMS fallback + CAP feed
```

Key endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/wards/lite` | Cached simplified ward shapes for the phone |
| `POST/PATCH/DELETE /api/v1/subscriptions` | Ward-only push subscriptions (no coordinates) |
| `POST /api/v1/whatsapp/webhook` | HMAC-verified `JOIN <ward>` / `STOP` / `HELP` |
| `GET /api/v1/alerts/pending` | Alerts awaiting official approval |
| `POST /api/v1/alerts/{id}/approve` | Approve and dispatch |
| `POST /api/v1/alerts/{id}/cancel` | Cancel before dispatch |
| `GET /api/v1/alerts/active` | Resident-facing active alerts |
| `GET /api/v1/alerts/cap.xml` | CAP 1.2 feed (Exercise until changed) |

Voice demo (no browser required):

```powershell
run_voice_agent.bat          # loads everything, then press Y to start
# or
.venv\Scripts\python.exe -m voice.family_agent console
```

Setup, providers and troubleshooting are in [docs/voice.md](docs/voice.md).
The optional browser variant is `run_voice_browser.bat`.

## Architecture

```
flood-predictor/
├── api/
│   ├── routes/               # wards, risk, subscriptions, whatsapp, alerts, cap, lite
│   ├── db.py                 # SQLModel: subscriptions, subscribers, alerts, dispatch log
│   ├── schemas.py            # Pydantic request/response models
│   ├── settings.py           # env-backed configuration
│   └── main.py               # app, CORS, lifespan, routers
├── model/
│   ├── risk_engine.py        # weighted risk index
│   ├── road_risk_index.py    # precomputed road risk
│   ├── validation.py         # evidence-aware evaluator
│   ├── cap.py                # CAP 1.2 export/validation
│   ├── alerts.py, shelters.py, ...
├── services/
│   ├── scheduler.py          # 15-min forecast -> pending alerts
│   ├── dispatcher.py         # approved alert -> push/WhatsApp/SMS
│   ├── rules.py              # alert-rule bridge (Mit's rules when present)
│   └── messages.py           # EN/TA alert copy
├── integrations/
│   ├── openwa.py             # paced WhatsApp client
│   ├── webpush.py            # VAPID sender
│   ├── openmeteo.py          # forecast
│   ├── crypto.py             # encrypt WhatsApp IDs at rest
│   └── notifications.py      # Twilio SMS/voice
├── voice/
│   ├── family_agent.py       # LiveKit agent (DeepSeek + Whisper + Edge TTS)
│   ├── plugins/              # Edge TTS and faster-whisper LiveKit plugins
│   ├── test_case.py          # Ward 14 relief-camp/directions test case
│   ├── token_server.py, demo.py, scripts.py
├── pipeline/                 # data acquisition and feature building
├── research/logistic_regression/  # separate reproducible experiment
├── web/                      # React + Vite + TypeScript + Tailwind
└── data/                     # processed GeoJSON, Parquet, rasters
```

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 20+
- [uv](https://docs.astral.sh/uv/)

### Backend

```bash
uv sync --all-extras

# Optional: rebuild data (all sources are real; no synthetic fallbacks)
python pipeline/download_dem.py
python pipeline/download_lulc.py
python pipeline/extract_osm_local.py
python pipeline/extract_assets.py
python pipeline/zonal_stats.py
python pipeline/build_features.py

# Start the API
uv run uvicorn api.main:app --reload --port 8000
```

Ward boundaries are converted from the tracked KML files with
`python pipeline/extract_wards_from_kml.py`.

### Frontend

```bash
cd web
npm install
npm run dev          # http://localhost:5173
npm test -- --run
npm run lint && npm run typecheck && npm run build
```

If the API is not running, the UI switches to a clearly labelled offline mock.

### Alerts

Copy `.env.example` to `.env` and set the values you need. To let the scheduler
create pending alerts, set `ENABLE_SCHEDULER=true`. Nothing is delivered until an
official approves it. WhatsApp uses OpenWA (unofficial); see
[docker-compose.openwa.yml](docker-compose.openwa.yml) and
[docs/alerts.md](docs/alerts.md). Without OpenWA/VAPID credentials the dispatcher
runs in simulated mode and logs `simulated`.

### Tests

```bash
.venv\Scripts\python.exe -m pytest     # backend: 674 passing
```

## API endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/healthz` | GET | Health check |
| `/api/v1/readyz` | GET | Readiness (data, database, OpenWA, exercise mode) |
| `/api/v1/wards` | GET | List all wards |
| `/api/v1/wards/lite` | GET | Simplified cached shapes for the phone |
| `/api/v1/wards/geojson` | GET | Full ward GeoJSON |
| `/api/v1/wards/{id}` | GET | Ward details with features |
| `/api/v1/risk` | POST | Risk for a rainfall/duration scenario |
| `/api/v1/scenario` | POST | Risk with a built-up increase |
| `/api/v1/validation` | GET | Evidence-aware validation status |
| `/api/v1/alerts` | POST | Generate alert text for selected wards |
| `/api/v1/shelters` | POST | Nearest shelters |
| `/api/v1/roads/risk` | GET | Road-level flood risk |
| `/api/v1/subscriptions` | POST | Subscribe this device to a ward |
| `/api/v1/subscriptions/{id}` | PATCH/DELETE | Move ward / unsubscribe and delete |
| `/api/v1/push/vapid-public-key` | GET | Web Push public key |
| `/api/v1/whatsapp/webhook` | POST | OpenWA inbound webhook |
| `/api/v1/alerts/pending` | GET | Pending approvals |
| `/api/v1/alerts/active` | GET | Active alerts (`?ward_id=`) |
| `/api/v1/alerts/{id}` | GET | Alert detail |
| `/api/v1/alerts/{id}/approve` | POST | Approve and dispatch |
| `/api/v1/alerts/{id}/cancel` | POST | Cancel |
| `/api/v1/alerts/cap.xml` | GET | CAP 1.2 Exercise feed |

## Data sources

| Layer | Source |
|---|---|
| Ward / zone boundaries | Official Greater Chennai Corporation 2022 KML (tracked in `data/raw/`) |
| Elevation, slope | Copernicus DEM 30 m COGs (AWS Open Data); slope via `numpy.gradient` |
| Land use | ESA WorldCover 10 m v200 (2021) via Planetary Computer STAC |
| Water, roads, underpasses | Geofabrik Southern Zone OSM PBF (local extract, no Overpass) |
| Shelters / assets | OSM features extracted from the same PBF |
| Rainfall forecast | Open-Meteo |
| Validation labels | Pending reviewed event labels; see `docs/validation.md` |

No synthetic DEM/LULC fallback exists in the downloaders. Known boundary
topology (291 ward-pair overlaps, 0.025% interior gap) is documented in
[docs/chennai_boundary_review.md](docs/chennai_boundary_review.md).

## Model

The risk engine is an **uncalibrated risk index**, not a flood probability:

| Factor | Weight | Description |
|---|---:|---|
| Elevation | 25% | Low elevation increases risk |
| Slope | 15% | Flatter terrain increases the component |
| Impervious surface | 25% | Reduces infiltration |
| Water proximity | 15% | Proximity proxy; backflow not modelled |
| Road density | 10% | Urbanisation proxy |
| Underpasses | 10% | Critical flood points |

The index is scaled by rainfall accumulation and a bounded duration heuristic.
Built-up increase is applied exactly once. See
[docs/model_logic.md](docs/model_logic.md) for the formula, units and handoffs.
Legacy depth/timing outputs are display proxies, not physical predictions.

### Research experiment

[`research/logistic_regression/`](research/logistic_regression/README.md) is a
separate, reproducible CPU experiment (frozen proxy dataset, portable model,
geographic held-out results): recall 71.43%, precision 12.50%, balanced accuracy
80.55% against seven satellite-proxy positives. It does not validate future flood
forecasting, and the application still uses the weighted-score engine.

## Validation

Historical validation is **pending**. `data/processed/validation_metrics.json`
returns a schema-2 `unavailable` status until reviewed, ward-aligned labels are
supplied; the API and UI refuse mock/legacy metrics. See
[docs/validation.md](docs/validation.md).

## Deployment

### Docker

```bash
docker build -t flood-predictor-api -f api/Dockerfile .
docker run -p 8000:8000 --env-file .env flood-predictor-api
```

### Render + Vercel

1. Deploy the API as a Render Web Service (set `DATABASE_URL` to Postgres).
2. Set the environment variables from `.env.example`.
3. Deploy `web/` to Vercel and set `VITE_API_URL` to the Render API URL.
4. Optional: run OpenWA with `docker-compose.openwa.yml` and point
   `OPENWA_BASE_URL` at it.

GitHub Actions builds/tests, pushes the Docker image, and triggers Render/Vercel
when the required secrets are configured.

## Team and contributions

See [CONTRIBUTORS.md](CONTRIBUTORS.md) for the detailed breakdown.

- **John** — data pipeline (Copernicus DEM, ESA WorldCover, local Geofabrik PBF,
  official GCC KML conversion), FastAPI endpoints, SQLModel alert storage,
  scheduler/dispatcher, OpenWA and Web Push integrations, CAP feed, speed work
  (`/wards/lite`, road index, caching), Docker/CI, DeepSeek voice agent with local
  Whisper STT and Edge TTS, and the handoff/provenance documentation.
- **Mit** — geo modules, risk engine and alert rules, evidence-aware validation
  framework, CAP 1.2 export, boundary review, and the reproducible
  logistic-regression research package.
- **Ronit** — React frontend, resident and official views, PWA/offline behaviour,
  on-device ward lookup, Tamil/English i18n, alerts UX, hostile-input hardening,
  accessibility and demo assets.

## License

MIT
