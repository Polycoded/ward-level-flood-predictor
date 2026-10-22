# Chennai Ward-Level Flood Predictor

A prototype system predicting ward-level flood susceptibility and dynamic risk for Chennai's 200 wards based on incoming/forecasted rainfall scenarios (6-24 hour horizon), integrating topological, environmental, and infrastructure attributes.

## Features

- **Ward-level Risk Assessment**: Flood risk scoring for all 200 Chennai wards
- **Dynamic Rainfall Integration**: Manual input, scenario simulation, and live API support
- **Explainable AI**: Per-ward reasoning with factual threshold statements
- **Multi-channel Alerting**: SMS, WhatsApp, Voice (Twilio), and LiveKit voice agent
- **Road & Underpass Risk**: Road-level flood risk with underpass identification
- **Shelter Navigation**: Nearest shelter finder with walking routes (OSRM)
- **Future Scenario Modeling**: Toggle for +15%/+30% built-up area impact
- **Historical Validation**: Validated against Dec 2023 Chennai floods

## Architecture

```
flood-predictor/
├── api/                 # FastAPI backend
│   ├── routes/          # API endpoints
│   ├── schemas.py       # Pydantic models
│   └── main.py          # App entry point
├── model/               # Risk engine & ML models
│   ├── risk_engine.py   # Core scoring logic
│   ├── alerts.py        # Alert generation
│   ├── shelters.py      # Shelter finder
│   ├── road_risk.py     # Road-level risk
│   └── validation.py    # Historical validation
├── pipeline/            # Data processing pipeline
│   ├── download_wards.py
│   ├── download_dem.py
│   ├── download_lulc.py
│   ├── extract_osm.py
│   ├── zonal_stats.py
│   └── build_features.py
├── integrations/        # External services
│   ├── weather.py       # Weather APIs
│   └── notifications.py # Twilio SMS/WhatsApp/Voice
├── voice/               # LiveKit voice agent
│   ├── token_server.py
│   ├── family_agent.py
│   └── scripts.py
├── web/                 # React frontend (Vite + TS + Tailwind)
└── data/                # Processed data (GeoJSON, Parquet, TIFF)
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- uv (Python package manager)

### Backend Setup

```bash
# Install Python dependencies
uv sync --all-extras

# Run data pipeline (downloads data, computes features)
cd pipeline
python download_wards.py
python download_dem.py
python download_lulc.py
python extract_osm.py
python zonal_stats.py
python build_features.py

# Start API server
cd ../api
uv run uvicorn main:app --reload --port 8000
```

### Frontend Setup

```bash
cd web
npm install
npm run dev
```

Visit `http://localhost:5173` for the dashboard. It talks to the API on port 8000. If the API is not running, it switches to a clearly labelled offline mock so the UI can still be demoed.

```bash
npm test -- --run   # 85 tests: user flows, security cases, parity with model/risk_engine.py
npm run lint && npm run typecheck && npm run build
npm run preview     # production build with the same security headers as Vercel
```

See [docs/frontend.md](docs/frontend.md) for architecture, environment variables, security notes and the test map.

### Critical assets and shelters

```bash
python pipeline/extract_assets.py   # writes data/processed/assets.parquet and shelters.parquet
```

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
# Edit .env with your API keys
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/healthz` | GET | Health check |
| `/api/v1/readyz` | GET | Readiness check |
| `/api/v1/wards` | GET | List all wards |
| `/api/v1/wards/{id}` | GET | Ward details with features |
| `/api/v1/risk` | POST | Risk analysis for rainfall scenario |
| `/api/v1/scenario` | POST | Risk analysis with future land-use scenario |
| `/api/v1/validation` | GET | Historical validation metrics |
| `/api/v1/alerts` | POST | Generate multi-channel alerts |
| `/api/v1/shelters` | POST | Find nearest shelters |
| `/api/v1/roads/risk` | GET | Road-level flood risk |

## Data Sources

- **Ward Boundaries**: OpenStreetMap (Overpass API)
- **DEM**: SRTM 30m / Synthetic fallback
- **LULC**: ESA WorldCover 10m / Synthetic fallback
- **Roads/Water/Underpasses**: OpenStreetMap
- **Shelters**: Chennai Corporation data / Defaults
- **Validation Labels**: Sentinel-1 SAR + News reports (Dec 2023)

## Model

The risk engine uses a weighted hydrological index:

| Factor | Weight | Description |
|--------|--------|-------------|
| Elevation | 25% | Low elevation increases risk |
| Slope | 15% | Flat terrain limits drainage |
| Impervious Surface | 25% | Reduces infiltration |
| Water Proximity | 15% | Backflow risk |
| Road Density | 10% | Urbanization proxy |
| Underpasses | 10% | Critical flood points |

Risk score is scaled by rainfall intensity (mm/200, capped at 1.5x).

## Validation

Validated against December 2023 Chennai floods:
- **Precision@20**: ~0.65
- **Recall**: ~0.70
- **False Positive Rate**: ~0.15

See `data/processed/validation_metrics.json` for details.

## Deployment

### Docker

```bash
docker build -t flood-predictor-api -f api/Dockerfile .
docker run -p 8000:8000 flood-predictor-api
```

### Render (Backend) + Vercel (Frontend)

1. Connect GitHub repo to Render
2. Set environment variables
3. Deploy as Web Service
4. Connect to Vercel for frontend

## Team

- **John** — Pipeline + FastAPI + Deploy + CI
- **Mit** — Geo Modules + Risk Model + Validation + Explainability
- **Ronit** — React UI + Alerts UX + Assets + Demo + Observability

## License

MIT