"""Web Push (VAPID) delivery via pywebpush."""

from __future__ import annotations

import json
from typing import Any

import structlog

from api.settings import settings

logger = structlog.get_logger()


def is_configured() -> bool:
    return bool(settings.vapid_private_key and settings.vapid_public_key)


def public_key() -> str:
    return settings.vapid_public_key


def send_push(subscription: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Send one push message.

    ``subscription`` matches the Web Push subscription shape stored on the
    server: ``{"endpoint": ..., "keys": {"p256dh": ..., "auth": ...}}``.
    Returns ``expired=True`` for 404/410 so callers can prune the row.
    """
    if not is_configured():
        return {"success": True, "simulated": True, "status": "simulated"}
    endpoint = subscription.get("endpoint")
    keys = subscription.get("keys") or {}
    if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
        return {"success": False, "expired": True, "status": "failed",
                "error": "incomplete subscription"}

    try:
        from pywebpush import webpush

        webpush(
            subscription_info={
                "endpoint": endpoint,
                "keys": {"p256dh": keys["p256dh"], "auth": keys["auth"]},
            },
            data=json.dumps(payload),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
        )
        return {"success": True, "simulated": False, "status": "sent"}
    except Exception as exc:  # WebPushException carries the HTTP status
        status = getattr(getattr(exc, "response", None), "status_code", None)
        expired = status in (404, 410)
        logger.warning("Web push failed", expired=expired, error=str(exc))
        return {"success": False, "simulated": False, "expired": expired,
                "status": "failed", "error": str(exc)}
