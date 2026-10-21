from typing import List, Dict, Any
import pandas as pd
import structlog

logger = structlog.get_logger()


def get_rainfall_scenarios() -> List[Dict[str, Any]]:
    return [
        {"name": "Light Rain", "rainfall_mm": 25, "duration_hours": 3, "description": "Light shower, minimal risk"},
        {"name": "Moderate Rain", "rainfall_mm": 75, "duration_hours": 3, "description": "Moderate rain, localized waterlogging"},
        {"name": "Heavy Rain", "rainfall_mm": 150, "duration_hours": 3, "description": "Heavy rain, significant flooding likely"},
        {"name": "Extreme Rain", "rainfall_mm": 250, "duration_hours": 3, "description": "Extreme event, widespread flooding"},
        {"name": "Dec 2023 Event", "rainfall_mm": 300, "duration_hours": 24, "description": "Historical Dec 2023 Chennai floods"},
    ]


async def fetch_live_rainfall(lat: float, lon: float) -> Dict[str, Any]:
    logger.warning("Live rainfall API not configured, returning mock data")
    return {
        "current_mm": 0.0,
        "forecast_3h_mm": 0.0,
        "forecast_24h_mm": 0.0,
        "source": "mock",
        "timestamp": pd.Timestamp.now().isoformat()
    }