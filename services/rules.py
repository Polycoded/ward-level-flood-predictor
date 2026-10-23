"""Alert-rule bridge.

Mit owns ``model/alert_rules.py`` (thresholds, hysteresis, message content).
This module calls it when present and falls back to a conservative, clearly
documented default so John's scheduler and dispatcher can run end to end
before that module lands.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import structlog

from api.settings import settings
from services.messages import alert_text

logger = structlog.get_logger()

LEVEL_RANK = {"very_low": 0, "low": 1, "moderate": 2, "high": 3, "very_high": 4}


@dataclass(frozen=True)
class WardRisk:
    ward_id: int
    ward_name: str
    risk_level: str
    risk_score: float


def _rank(level: str) -> int:
    return LEVEL_RANK.get(level, 0)


def default_select(
    ward_risks: Iterable[WardRisk],
    rainfall_mm: float,
    duration_hours: float,
    recent: dict[int, Any],
    now: datetime,
) -> list[dict[str, Any]]:
    """Conservative Watch/Warning selection with per-ward hysteresis.

    ``recent`` maps ward_id -> most recent Alert-like object with ``created_at``
    and ``risk_level``. A ward is not re-alerted inside the hysteresis window
    unless its risk level worsens.
    """
    selected: list[dict[str, Any]] = []
    window = timedelta(hours=max(0, settings.hysteresis_hours))

    for risk in ward_risks:
        rank = _rank(risk.risk_level)
        if rainfall_mm >= settings.min_warning_rainfall_mm and rank >= LEVEL_RANK["high"]:
            alert_type = "warning"
        elif rainfall_mm >= settings.min_watch_rainfall_mm and rank >= LEVEL_RANK["moderate"]:
            alert_type = "watch"
        else:
            continue

        previous = recent.get(int(risk.ward_id))
        if previous is not None:
            created = getattr(previous, "created_at", None)
            if created is not None:
                if created.tzinfo is None:
                    created = created.replace(tzinfo=now.tzinfo)
                within = (now - created) < window
                if within and rank <= _rank(getattr(previous, "risk_level", "very_low")):
                    continue

        selected.append({
            "ward_id": int(risk.ward_id),
            "ward_name": risk.ward_name,
            "risk_level": risk.risk_level,
            "risk_score": float(risk.risk_score),
            "alert_type": alert_type,
            "rainfall_mm": float(rainfall_mm),
            "duration_hours": float(duration_hours),
            "message_en": alert_text(alert_type, risk.ward_name, rainfall_mm, duration_hours, "en"),
            "message_ta": alert_text(alert_type, risk.ward_name, rainfall_mm, duration_hours, "ta"),
        })

    selected.sort(key=lambda item: item["risk_score"], reverse=True)
    return selected[: max(1, settings.max_alerts_per_cycle)]


def select_alerts(
    ward_risks: Iterable[WardRisk],
    rainfall_mm: float,
    duration_hours: float,
    recent: dict[int, Any],
    now: datetime,
) -> list[dict[str, Any]]:
    ward_risks = list(ward_risks)
    try:
        from model import alert_rules as mit_rules  # type: ignore

        if hasattr(mit_rules, "select_alerts"):
            result = mit_rules.select_alerts(
                ward_risks,
                rainfall_mm=rainfall_mm,
                duration_hours=duration_hours,
                recent=recent,
                now=now,
                settings=settings,
            )
            if isinstance(result, list):
                return result
    except Exception as exc:  # missing module or incompatible signature
        logger.info("Using built-in alert rules", reason=str(exc))
    return default_select(ward_risks, rainfall_mm, duration_hours, recent, now)
