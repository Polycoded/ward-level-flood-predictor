"""SQLModel storage for subscriptions, WhatsApp subscribers, alerts and dispatch logs.

Only a ward ID is ever stored for a resident; raw coordinates are never accepted
or persisted. WhatsApp chat identifiers are encrypted at rest by
``integrations.crypto``.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime

from sqlalchemy.pool import StaticPool
from sqlmodel import Field, Session, SQLModel, create_engine

from api.settings import settings


def utcnow() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid.uuid4())


class Subscription(SQLModel, table=True):
    """A browser/device that wants push alerts for one ward."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    ward_id: int = Field(index=True)
    language: str = "en"
    endpoint: str = Field(index=True)
    p256dh: str
    auth: str
    active: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class WhatsAppSubscriber(SQLModel, table=True):
    """A WhatsApp user who opted in by messaging us first."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    chat_id_hash: str = Field(index=True)
    chat_id_enc: str = Field(index=True)
    ward_id: int = Field(index=True)
    language: str = "en"
    active: bool = True
    consent_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Alert(SQLModel, table=True):
    """A pending/approved/cancelled/sent broadcast created by the scheduler."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    ward_id: int = Field(index=True)
    ward_name: str = ""
    risk_level: str = "moderate"
    risk_score: float = 0.0
    alert_type: str = "watch"  # watch | warning
    status: str = "pending"  # pending | approved | sent | cancelled
    rainfall_mm: float = 0.0
    duration_hours: float = 3.0
    message_en: str = ""
    message_ta: str = ""
    created_at: datetime = Field(default_factory=utcnow, index=True)
    approved_at: datetime | None = None
    sent_at: datetime | None = None
    cancelled_at: datetime | None = None


class DispatchLog(SQLModel, table=True):
    """One row per delivery attempt, for observability and de-duplication."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    alert_id: str = Field(index=True)
    channel: str  # webpush | whatsapp | sms
    recipient_ref: str  # subscription id / encrypted chat id (never raw phone)
    status: str  # sent | failed | skipped | simulated
    detail: str | None = None
    created_at: datetime = Field(default_factory=utcnow, index=True)


_engine = None
_engine_url: str | None = None


def get_engine():
    global _engine, _engine_url
    if _engine is None:
        url = settings.database_url
        kwargs = {}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in url:
                kwargs["poolclass"] = StaticPool
        _engine = create_engine(url, **kwargs)
        _engine_url = url
    return _engine


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())


def reset_engine(url: str | None = None) -> None:
    """Used by tests to point at a fresh database."""
    global _engine, _engine_url
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _engine_url = None
    if url is not None:
        settings.database_url = url


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
