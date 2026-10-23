"""Open-Meteo forecast fetch (no API key required)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from api.settings import settings

logger = structlog.get_logger()


async def fetch_forecast(hours: int | None = None) -> dict[str, Any] | None:
    """Return rainfall accumulation for the next ``hours`` hours.

    Returns ``None`` on any failure so the scheduler can skip a cycle instead of
    broadcasting on fabricated data.
    """
    horizon = int(hours or settings.forecast_hours)
    params = {
        "latitude": settings.chennai_lat,
        "longitude": settings.chennai_lon,
        "hourly": "precipitation",
        "forecast_days": 2,
        "timezone": "Asia/Kolkata",
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(settings.open_meteo_base_url, params=params)
        response.raise_for_status()
        data = response.json()
        precipitation = (data.get("hourly") or {}).get("precipitation") or []
        total = sum(float(value or 0) for value in precipitation[:horizon])
        return {
            "rainfall_mm": round(total, 2),
            "duration_hours": horizon,
            "source": "open-meteo",
            "fetched_at": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:
        logger.warning("Open-Meteo forecast failed", error=str(exc))
        return None
