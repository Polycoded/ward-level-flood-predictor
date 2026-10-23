"""Human-in-the-loop alert approval and the resident-facing active feed."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from api.db import Alert, get_session, utcnow
from api.schemas import AlertOut, DispatchResult
from api.settings import settings
from services.dispatcher import dispatch_alert

router = APIRouter(prefix="/api/v1", tags=["alerts"])


def _out(alert: Alert) -> AlertOut:
    return AlertOut(
        id=alert.id,
        ward_id=alert.ward_id,
        ward_name=alert.ward_name,
        risk_level=alert.risk_level,
        risk_score=alert.risk_score,
        alert_type=alert.alert_type,
        status=alert.status,
        rainfall_mm=alert.rainfall_mm,
        duration_hours=alert.duration_hours,
        message_en=alert.message_en,
        message_ta=alert.message_ta,
        created_at=alert.created_at,
        approved_at=alert.approved_at,
        sent_at=alert.sent_at,
        exercise=settings.exercise_mode,
    )


@router.get("/alerts/pending", response_model=list[AlertOut])
def list_pending(session: Session = Depends(get_session)) -> list[AlertOut]:
    rows = session.exec(
        select(Alert).where(Alert.status == "pending").order_by(Alert.created_at.desc())
    ).all()
    return [_out(row) for row in rows]


@router.get("/alerts/active", response_model=list[AlertOut])
def list_active(ward_id: int | None = Query(default=None, ge=1),
                session: Session = Depends(get_session)) -> list[AlertOut]:
    statement = select(Alert).where(Alert.status.in_(["approved", "sent", "sending"]))
    if ward_id is not None:
        statement = statement.where(Alert.ward_id == ward_id)
    statement = statement.order_by(Alert.created_at.desc()).limit(20)
    rows = session.exec(statement).all()
    return [_out(row) for row in rows]


@router.get("/alerts/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: str, session: Session = Depends(get_session)) -> AlertOut:
    alert = session.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _out(alert)


@router.post("/alerts/{alert_id}/approve", response_model=DispatchResult)
async def approve_alert(alert_id: str, session: Session = Depends(get_session)) -> DispatchResult:
    alert = session.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status != "pending":
        raise HTTPException(status_code=409, detail=f"Alert is {alert.status}, not pending")

    alert.status = "approved"
    alert.approved_at = utcnow()
    session.add(alert)
    session.commit()

    summary = await dispatch_alert(alert_id)
    return DispatchResult(**{k: v for k, v in summary.items() if k != "status"},
                          status="sent")


@router.post("/alerts/{alert_id}/cancel", response_model=AlertOut)
def cancel_alert(alert_id: str, session: Session = Depends(get_session)) -> AlertOut:
    alert = session.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status in ("sent", "sending"):
        raise HTTPException(status_code=409, detail="Alert already dispatched")
    alert.status = "cancelled"
    alert.cancelled_at = utcnow()
    session.add(alert)
    session.commit()
    session.refresh(alert)
    return _out(alert)
