"""15-minute scheduler: forecast -> ward risk -> Mit's alert rules -> pending alerts."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

import structlog
from sqlmodel import Session, select

from api.db import Alert, get_engine, utcnow
from api.settings import settings
from integrations.openmeteo import fetch_forecast
from services.rules import WardRisk, select_alerts

logger = structlog.get_logger()

_stop = asyncio.Event()
_task: asyncio.Task | None = None


def _load_features():
    from api.routes.main import load_features

    return load_features()


def _recent_alerts(session: Session, now) -> dict[int, Alert]:
    cutoff = now - timedelta(hours=max(1, settings.hysteresis_hours))
    rows = session.exec(
        select(Alert).where(Alert.created_at >= cutoff, Alert.status != "cancelled")
    ).all()
    recent: dict[int, Alert] = {}
    for row in rows:
        current = recent.get(row.ward_id)
        if current is None or row.created_at > current.created_at:
            recent[row.ward_id] = row
    return recent


async def run_cycle() -> dict[str, Any]:
    """Run one alerting cycle. Safe to call directly from tests."""
    forecast = await fetch_forecast(settings.forecast_hours)
    if forecast is None:
        return {"status": "skipped", "reason": "no_forecast"}

    rainfall = float(forecast["rainfall_mm"])
    duration = float(forecast["duration_hours"])
    if rainfall < settings.min_watch_rainfall_mm:
        return {"status": "skipped", "reason": "below_threshold",
                "rainfall_mm": rainfall, "threshold": settings.min_watch_rainfall_mm}

    try:
        features = _load_features()
    except Exception as exc:
        logger.error("Scheduler could not load features", error=str(exc))
        return {"status": "skipped", "reason": "features_unavailable"}

    from model.risk_engine import score_wards

    scored = score_wards(features, rainfall, duration_hours=duration)
    wards = [
        WardRisk(
            ward_id=int(row.ward_id),
            ward_name=str(row.ward_name),
            risk_level=str(row.risk_level),
            risk_score=float(row.risk_score),
        )
        for _, row in scored.iterrows()
    ]

    now = utcnow()
    with Session(get_engine()) as session:
        recent = _recent_alerts(session, now)
        selected = select_alerts(wards, rainfall, duration, recent, now)

        created = 0
        for item in selected:
            session.add(Alert(**item, status="pending", created_at=now))
            created += 1
        session.commit()

    logger.info("Scheduler cycle complete", rainfall_mm=rainfall, pending_created=created)
    return {"status": "ok", "rainfall_mm": rainfall, "duration_hours": duration,
            "pending_created": created, "exercise": settings.exercise_mode}


async def scheduler_loop() -> None:
    interval = max(1, settings.scheduler_interval_minutes) * 60
    while not _stop.is_set():
        try:
            await run_cycle()
        except Exception as exc:
            logger.error("Scheduler cycle failed", error=str(exc))
        try:
            await asyncio.wait_for(_stop.wait(), timeout=interval)
        except TimeoutError:
            continue


def start_scheduler() -> None:
    global _task
    if _task is not None and not _task.done():
        return
    _stop.clear()
    _task = asyncio.create_task(scheduler_loop())
    logger.info("Scheduler started", interval_minutes=settings.scheduler_interval_minutes)


async def stop_scheduler() -> None:
    global _task
    _stop.set()
    if _task is not None:
        try:
            await asyncio.wait_for(_task, timeout=5)
        except (TimeoutError, asyncio.CancelledError):
            _task.cancel()
        _task = None
