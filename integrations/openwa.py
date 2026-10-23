"""OpenWA (unofficial WhatsApp Web bridge) client.

Safety notes baked in:
- messages are paced (3-5 s + jitter) to reduce ban risk;
- every send carries an idempotency key and retries with backoff;
- when OpenWA is not configured the result is explicit and simulated so the
  dispatcher can still be exercised in tests and demos.

OpenWA is unofficial; production should use Meta's Cloud API.
"""

from __future__ import annotations

import asyncio
import hashlib
import random
import time
from collections import OrderedDict
from typing import Any

import httpx
import structlog

from api.settings import settings

logger = structlog.get_logger()

_lock = asyncio.Lock()
_last_sent = 0.0
_seen: OrderedDict[str, dict[str, Any]] = OrderedDict()
_MAX_SEEN = 2048


def _remember(key: str, result: dict[str, Any]) -> None:
    _seen[key] = result
    _seen.move_to_end(key)
    while len(_seen) > _MAX_SEEN:
        _seen.popitem(last=False)


def _idempotency_key(chat_id: str, text: str) -> str:
    digest = hashlib.sha256(f"{chat_id}:{text}".encode()).hexdigest()
    return digest[:40]


async def _pace() -> None:
    global _last_sent
    async with _lock:
        now = time.monotonic()
        low = max(0.0, settings.openwa_min_interval_seconds)
        high = max(low, settings.openwa_max_interval_seconds)
        wait = low + random.uniform(0, high - low)
        remaining = wait - (now - _last_sent)
        if remaining > 0:
            await asyncio.sleep(remaining)
        _last_sent = time.monotonic()


def is_configured() -> bool:
    return bool(settings.openwa_base_url)


async def probe() -> dict[str, Any]:
    """Cheap health probe used by /readyz."""
    if not is_configured():
        return {"configured": False, "ok": True, "detail": "OpenWA not configured"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.openwa_base_url.rstrip('/')}/health",
                headers={"X-API-Key": settings.openwa_api_key},
            )
        return {"configured": True, "ok": response.status_code < 500,
                "detail": f"HTTP {response.status_code}"}
    except Exception as exc:  # network failures must not crash readiness
        logger.warning("OpenWA probe failed", error=str(exc))
        return {"configured": True, "ok": False, "detail": str(exc)}


async def send_text(chat_id: str, text: str, idempotency_key: str | None = None) -> dict[str, Any]:
    """Send one text message. Never raises; callers log the returned status."""
    if not chat_id or not text:
        return {"success": False, "status": "skipped", "error": "empty chat_id or text"}
    if not is_configured():
        logger.warning("OpenWA not configured; message simulated", chat_id_tail=chat_id[-4:])
        return {"success": True, "simulated": True, "status": "simulated"}

    key = idempotency_key or _idempotency_key(chat_id, text)
    if key in _seen:
        return {**_seen[key], "deduplicated": True}

    payload = {
        "session": settings.openwa_session,
        "chatId": chat_id,
        "text": text,
    }
    headers = {
        "X-API-Key": settings.openwa_api_key,
        "Idempotency-Key": key,
        "Content-Type": "application/json",
    }
    url = f"{settings.openwa_base_url.rstrip('/')}/messages/send"

    last_error: str | None = None
    for attempt in range(1, max(1, settings.openwa_max_retries) + 1):
        await _pace()
        try:
            async with httpx.AsyncClient(timeout=settings.openwa_timeout_seconds) as client:
                response = await client.post(url, json=payload, headers=headers)
            if response.status_code < 300:
                result = {"success": True, "simulated": False, "status": "sent",
                          "http_status": response.status_code}
                _remember(key, result)
                logger.info("OpenWA message sent", attempt=attempt)
                return result
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            if response.status_code in (401, 403):
                break  # auth problems do not improve with retries
        except Exception as exc:
            last_error = str(exc)
        await asyncio.sleep(min(2 ** attempt, 8) + random.uniform(0, 0.5))

    logger.error("OpenWA send failed", error=last_error)
    return {"success": False, "simulated": False, "status": "failed", "error": last_error}


def reset_state() -> None:
    """Test helper: clear pacing state and the idempotency cache."""
    global _last_sent
    _last_sent = 0.0
    _seen.clear()
