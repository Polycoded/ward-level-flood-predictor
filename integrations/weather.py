import httpx
import structlog
from typing import Dict, Any, Optional
from datetime import datetime

logger = structlog.get_logger()

OPENWEATHER_API_KEY = None
OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"

IMD_API_KEY = None
IMD_BASE_URL = "https://api.imd.gov.in"


async def fetch_openweather_forecast(lat: float, lon: float) -> Dict[str, Any]:
    if not OPENWEATHER_API_KEY:
        logger.warning("OpenWeather API key not configured, returning mock data")
        return get_mock_forecast()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{OPENWEATHER_BASE_URL}/forecast",
                params={
                    "lat": lat,
                    "lon": lon,
                    "appid": OPENWEATHER_API_KEY,
                    "units": "metric",
                }
            )
            response.raise_for_status()
            data = response.json()
            
            forecast_3h = sum(item.get("rain", {}).get("3h", 0) for item in data.get("list", [])[:1])
            forecast_24h = sum(item.get("rain", {}).get("3h", 0) for item in data.get("list", [])[:8])
            
            return {
                "current_mm": data.get("list", [{}])[0].get("rain", {}).get("3h", 0),
                "forecast_3h_mm": forecast_3h,
                "forecast_24h_mm": forecast_24h,
                "source": "openweather",
                "timestamp": datetime.now().isoformat(),
                "raw": data
            }
        except Exception as e:
            logger.error("OpenWeather API error", error=str(e))
            return get_mock_forecast()


async def fetch_imd_forecast(lat: float, lon: float) -> Dict[str, Any]:
    if not IMD_API_KEY:
        logger.warning("IMD API key not configured, returning mock data")
        return get_mock_forecast()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{IMD_BASE_URL}/forecast",
                params={"lat": lat, "lon": lon, "apikey": IMD_API_KEY}
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "current_mm": data.get("current_rainfall", 0),
                "forecast_3h_mm": data.get("forecast_3h", 0),
                "forecast_24h_mm": data.get("forecast_24h", 0),
                "source": "imd",
                "timestamp": datetime.now().isoformat(),
                "raw": data
            }
        except Exception as e:
            logger.error("IMD API error", error=str(e))
            return get_mock_forecast()


async def fetch_rainfall_forecast(lat: float, lon: float, provider: str = "auto") -> Dict[str, Any]:
    if provider == "openweather" or (provider == "auto" and OPENWEATHER_API_KEY):
        return await fetch_openweather_forecast(lat, lon)
    elif provider == "imd" or (provider == "auto" and IMD_API_KEY):
        return await fetch_imd_forecast(lat, lon)
    else:
        return get_mock_forecast()


def get_mock_forecast() -> Dict[str, Any]:
    return {
        "current_mm": 0.0,
        "forecast_3h_mm": 0.0,
        "forecast_24h_mm": 0.0,
        "source": "mock",
        "timestamp": datetime.now().isoformat(),
        "note": "No weather API configured. Set OPENWEATHER_API_KEY or IMD_API_KEY environment variables."
    }


async def fetch_historical_rainfall(lat: float, lon: float, date: str) -> Dict[str, Any]:
    logger.warning("Historical rainfall API not implemented, returning mock data")
    return {
        "date": date,
        "total_mm": 0.0,
        "source": "mock",
        "note": "Historical data not available"
    }