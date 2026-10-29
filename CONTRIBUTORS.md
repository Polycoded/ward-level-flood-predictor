# Contributors

Chennai Ward-Level Flood Predictor — hackathon team contributions.

## John

Data, backend, delivery and voice.

- **Pipeline**: official GCC 2022 KML conversion; Copernicus DEM 30 m and ESA
  WorldCover acquisition; local Geofabrik Southern Zone PBF extraction for water,
  roads, underpasses and assets; zonal statistics; feature building.
- **API**: FastAPI endpoints, schemas, error handling, CORS/compression,
  readiness checks.
- **Alerting**: SQLModel storage for subscriptions, WhatsApp subscribers, alerts
  and dispatch logs; 15-minute scheduler; approval dispatcher; OpenWA client with
  pacing/retries/idempotency; HMAC WhatsApp webhook (JOIN/STOP/HELP); Web Push
  (VAPID); CAP 1.2 feed; rate limiting and encrypted identifiers.
- **Speed**: `/wards/lite` simplified shapes with ETag/cache, precomputed road risk
  index, scenario caching, startup warm-up.
- **Voice**: LiveKit agent wired to DeepSeek (OpenAI-compatible), local
  faster-whisper STT and Edge TTS; console and browser demos; cached fast-start.
- **Ops**: Dockerfile, CI workflow, `.dockerignore`, OpenWA compose file, environment
  documentation, data-provenance handoff docs.

## Mit

Geo science, model, validation and evidence.

- Geo modules and the weighted risk engine.
- Alert-rule design and CAP 1.2 content/mapping.
- Evidence-aware validation framework and schema-2 metrics envelope; refusal of
  mock/legacy accuracy claims.
- Boundary review and topology findings for the 200-ward dataset.
- Reproducible logistic-regression research package (`research/logistic_regression/`)
  with frozen proxy dataset and geographic held-out results.

## Ronit

Frontend, resident experience and demo.

- React/Vite/TypeScript dashboard, resident and official views.
- PWA, offline caching, on-device ward lookup, Tamil/English i18n.
- Alerts and approval UX, accessibility, responsive/touch design.
- Response validation and hostile-input hardening for the web client.
- Demo assets and presentation material.

## Shared

- Endpoint and data contracts.
- Boundary and validation review discussions.
- Integration and end-to-end testing.
