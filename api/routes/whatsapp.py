"""OpenWA inbound webhook: JOIN / STOP / HELP in English and Tamil.

Security: when ``OPENWA_WEBHOOK_SECRET`` is set, the raw body must carry a
valid HMAC-SHA256 signature (``X-Webhook-Signature`` or
``X-Hub-Signature-256``, hex, optional ``sha256=`` prefix).
"""

from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from api.db import WhatsAppSubscriber, get_session, utcnow
from api.rate_limit import client_key, webhook_limiter
from api.settings import settings
from integrations import openwa
from integrations.crypto import encrypt, identifier_hash
from services.messages import (
    help_text,
    join_confirmation,
    stop_confirmation,
    unknown_command,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1", tags=["whatsapp"])

_JOIN = re.compile(r"^(?:join|சேர்)\s+(\d{1,6})$", re.IGNORECASE)
_STOP = re.compile(r"^(?:stop|நிறுத்து)$", re.IGNORECASE)
_HELP = re.compile(r"^(?:help|உதவி)$", re.IGNORECASE)


def _verify(raw: bytes, request: Request) -> None:
    secret = settings.openwa_webhook_secret
    if not secret:
        return  # dev mode
    signature = (request.headers.get("x-webhook-signature")
                 or request.headers.get("x-hub-signature-256") or "")
    if signature.startswith("sha256="):
        signature = signature[len("sha256="):]
    expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


def _normalise(payload: Any) -> list[dict[str, str]]:
    """Accept the common OpenWA / whatsapp-web.js payload shapes."""
    candidates: list[Any] = []
    if isinstance(payload, dict):
        if isinstance(payload.get("messages"), list):
            candidates = payload["messages"]
        elif isinstance(payload.get("data"), list):
            candidates = payload["data"]
        elif isinstance(payload.get("data"), dict):
            candidates = [payload["data"]]
        else:
            candidates = [payload]

    messages: list[dict[str, str]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        sender = item.get("from") or item.get("chatId") or item.get("sender")
        body = item.get("body") if item.get("body") is not None else item.get("text")
        if isinstance(sender, str) and isinstance(body, str):
            messages.append({"from": sender, "body": body})
    return messages


def _ward_exists(ward_id: int) -> bool:
    try:
        from api.routes.main import load_wards

        return ward_id in {int(v) for v in load_wards()["ward_id"].tolist()}
    except Exception:
        return False


def _find(session: Session, chat_id: str) -> WhatsAppSubscriber | None:
    digest = identifier_hash(chat_id)
    return session.exec(
        select(WhatsAppSubscriber).where(WhatsAppSubscriber.chat_id_hash == digest)
    ).first()


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request, session: Session = Depends(get_session)):
    if not webhook_limiter.allow(client_key(request)):
        raise HTTPException(status_code=429, detail="Too many webhook requests")

    raw = await request.body()
    _verify(raw, request)
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    messages = _normalise(payload)
    handled = 0

    for message in messages:
        chat_id = message["from"].strip()
        body = " ".join(message["body"].strip().split())

        join_match = _JOIN.match(body)
        if join_match:
            ward_id = int(join_match.group(1))
            if not _ward_exists(ward_id):
                await openwa.send_text(chat_id, unknown_command("en"))
                continue
            existing = _find(session, chat_id)
            if existing is None:
                session.add(WhatsAppSubscriber(
                    chat_id_hash=identifier_hash(chat_id),
                    chat_id_enc=encrypt(chat_id),
                    ward_id=ward_id,
                    language="en",
                    active=True,
                    consent_at=utcnow(),
                ))
            else:
                existing.ward_id = ward_id
                existing.active = True
                existing.updated_at = utcnow()
                session.add(existing)
            session.commit()
            await openwa.send_text(chat_id, join_confirmation(ward_id, "en"))
            handled += 1

        elif _STOP.match(body):
            existing = _find(session, chat_id)
            if existing is not None:
                session.delete(existing)
                session.commit()
            await openwa.send_text(chat_id, stop_confirmation("en"))
            handled += 1

        elif _HELP.match(body):
            await openwa.send_text(chat_id, help_text("en"))
            handled += 1

        else:
            await openwa.send_text(chat_id, unknown_command("en"))

    return {"status": "ok", "handled": handled, "messages": len(messages)}
