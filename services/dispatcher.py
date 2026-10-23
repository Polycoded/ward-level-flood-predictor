"""Fan out an approved alert to push, WhatsApp and the SMS fallback."""

from __future__ import annotations

from typing import Any

import structlog
from sqlmodel import Session, select

from api.db import Alert, DispatchLog, Subscription, WhatsAppSubscriber, get_engine, utcnow
from api.settings import settings
from integrations import openwa, webpush
from integrations.crypto import decrypt
from integrations.notifications import send_sms

logger = structlog.get_logger()


def _looks_like_phone(value: str) -> bool:
    digits = value.lstrip("+").replace(" ", "").replace("-", "")
    return digits.isdigit() and 7 <= len(digits) <= 15


def _is_exercise() -> bool:
    return bool(settings.exercise_mode)


def _log(session: Session, alert_id: str, channel: str, recipient_ref: str,
         status: str, detail: str | None = None) -> None:
    session.add(DispatchLog(
        alert_id=alert_id, channel=channel, recipient_ref=recipient_ref,
        status=status, detail=detail,
    ))


async def dispatch_alert(alert_id: str) -> dict[str, Any]:
    """Deliver one approved alert. Returns per-channel counts for the admin UI."""
    with Session(get_engine()) as session:
        alert = session.get(Alert, alert_id)
        if alert is None:
            raise ValueError(f"alert {alert_id} not found")
        if alert.status in ("cancelled",):
            return {"alert_id": alert_id, "status": "cancelled", "delivered": 0}

        alert.status = "sending"
        session.add(alert)
        session.commit()

        summary = {"alert_id": alert_id, "ward_id": alert.ward_id,
                   "webpush": 0, "whatsapp": 0, "sms": 0, "failed": 0}

        payload = {
            "type": "flood_alert",
            "alert_id": alert.id,
            "ward_id": alert.ward_id,
            "ward_name": alert.ward_name,
            "alert_type": alert.alert_type,
            "risk_level": alert.risk_level,
            "rainfall_mm": alert.rainfall_mm,
            "duration_hours": alert.duration_hours,
            "exercise": _is_exercise(),
        }

        subscriptions = session.exec(
            select(Subscription).where(
                Subscription.ward_id == alert.ward_id,
                Subscription.active == True,  # noqa: E712
            )
        ).all()
        for sub in subscriptions:
            result = webpush.send_push(
                {"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
                payload,
            )
            if result.get("expired"):
                sub.active = False
                session.add(sub)
            status = "simulated" if result.get("simulated") else ("sent" if result.get("success") else "failed")
            _log(session, alert.id, "webpush", sub.id, status, result.get("error"))
            if result.get("success"):
                summary["webpush"] += 1
            else:
                summary["failed"] += 1

        subscribers = session.exec(
            select(WhatsAppSubscriber).where(
                WhatsAppSubscriber.ward_id == alert.ward_id,
                WhatsAppSubscriber.active == True,  # noqa: E712
            )
        ).all()
        for subscriber in subscribers:
            try:
                chat_id = decrypt(subscriber.chat_id_enc)
            except ValueError:
                _log(session, alert.id, "whatsapp", subscriber.id, "failed", "decrypt error")
                summary["failed"] += 1
                continue

            text = alert.message_ta if subscriber.language == "ta" else alert.message_en
            result = await openwa.send_text(
                chat_id, text, idempotency_key=f"{alert.id}:{subscriber.id}"
            )
            status = "simulated" if result.get("simulated") else ("sent" if result.get("success") else "failed")
            _log(session, alert.id, "whatsapp", subscriber.id, status, result.get("error"))
            if result.get("success"):
                summary["whatsapp"] += 1

            if not result.get("success") and settings.twilio_sms_fallback and _looks_like_phone(chat_id):
                sms = await send_sms(chat_id, text)
                sms_status = "simulated" if sms.get("simulated") else ("sent" if sms.get("success") else "failed")
                _log(session, alert.id, "sms", subscriber.id, sms_status, sms.get("error"))
                if sms.get("success"):
                    summary["sms"] += 1
                else:
                    summary["failed"] += 1

        alert.status = "sent"
        alert.sent_at = utcnow()
        session.add(alert)
        session.commit()

        logger.info("Alert dispatched", alert_id=alert.id, **{k: v for k, v in summary.items() if k not in ("alert_id", "ward_id")})
        return summary
