from typing import List, Dict, Any
from datetime import datetime
import structlog

logger = structlog.get_logger()

_reports: List[Dict[str, Any]] = []


def add_report(
    ward_id: int,
    latitude: float,
    longitude: float,
    severity: str,
    description: str,
    reporter_id: str = "anonymous"
) -> Dict[str, Any]:
    report = {
        "id": len(_reports) + 1,
        "ward_id": ward_id,
        "latitude": latitude,
        "longitude": longitude,
        "severity": severity,
        "description": description,
        "reporter_id": reporter_id,
        "timestamp": datetime.now().isoformat(),
        "verified": False,
    }
    _reports.append(report)
    logger.info("Crowd report added", report_id=report["id"])
    return report


def get_reports(ward_id: int = None, limit: int = 50) -> List[Dict[str, Any]]:
    filtered = _reports
    if ward_id is not None:
        filtered = [r for r in _reports if r["ward_id"] == ward_id]
    return filtered[-limit:]


def get_reports_geojson() -> Dict[str, Any]:
    features = []
    for r in _reports:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
            "properties": {
                "id": r["id"],
                "ward_id": r["ward_id"],
                "severity": r["severity"],
                "description": r["description"],
                "timestamp": r["timestamp"],
                "verified": r["verified"]
            }
        })
    return {"type": "FeatureCollection", "features": features}