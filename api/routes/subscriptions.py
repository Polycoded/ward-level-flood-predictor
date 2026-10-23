"""Ward-only subscription management. No coordinates are ever accepted."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlmodel import Session, select

from api.db import Subscription, get_session, utcnow
from api.rate_limit import client_key, subscription_limiter
from api.schemas import SubscriptionCreate, SubscriptionOut, SubscriptionUpdate

router = APIRouter(prefix="/api/v1", tags=["subscriptions"])


@router.get("/push/vapid-public-key")
def vapid_public_key() -> dict:
    from integrations import webpush

    return {"key": webpush.public_key(), "configured": webpush.is_configured()}


def _ward_ids() -> set[int]:
    from api.routes.main import load_wards

    wards = load_wards()
    return {int(value) for value in wards["ward_id"].tolist()}


def _require_ward(ward_id: int) -> None:
    try:
        ids = _ward_ids()
    except Exception:
        raise HTTPException(status_code=503, detail="Ward boundaries not available")
    if ward_id not in ids:
        raise HTTPException(status_code=404, detail=f"Unknown ward_id {ward_id}")


@router.post("/subscriptions", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
def create_subscription(payload: SubscriptionCreate, request: Request,
                        session: Session = Depends(get_session)) -> SubscriptionOut:
    if not subscription_limiter.allow(client_key(request)):
        raise HTTPException(status_code=429, detail="Too many subscription requests; try again shortly")
    _require_ward(payload.ward_id)

    existing = session.exec(
        select(Subscription).where(Subscription.endpoint == payload.push.endpoint)
    ).first()
    if existing is not None:
        existing.ward_id = payload.ward_id
        existing.language = payload.language
        existing.p256dh = payload.push.keys.p256dh
        existing.auth = payload.push.keys.auth
        existing.active = True
        existing.updated_at = utcnow()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return SubscriptionOut(id=existing.id, ward_id=existing.ward_id,
                               language=existing.language, active=existing.active)

    subscription = Subscription(
        ward_id=payload.ward_id,
        language=payload.language,
        endpoint=payload.push.endpoint,
        p256dh=payload.push.keys.p256dh,
        auth=payload.push.keys.auth,
    )
    session.add(subscription)
    session.commit()
    session.refresh(subscription)
    return SubscriptionOut(id=subscription.id, ward_id=subscription.ward_id,
                           language=subscription.language, active=subscription.active)


@router.patch("/subscriptions/{subscription_id}", response_model=SubscriptionOut)
def update_subscription(subscription_id: str, payload: SubscriptionUpdate, request: Request,
                        session: Session = Depends(get_session)) -> SubscriptionOut:
    if not subscription_limiter.allow(client_key(request)):
        raise HTTPException(status_code=429, detail="Too many subscription requests; try again shortly")
    _require_ward(payload.ward_id)

    subscription = session.get(Subscription, subscription_id)
    if subscription is None or not subscription.active:
        raise HTTPException(status_code=404, detail="Subscription not found")
    subscription.ward_id = payload.ward_id
    if payload.language is not None:
        subscription.language = payload.language
    subscription.updated_at = utcnow()
    session.add(subscription)
    session.commit()
    session.refresh(subscription)
    return SubscriptionOut(id=subscription.id, ward_id=subscription.ward_id,
                           language=subscription.language, active=subscription.active)


@router.delete("/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subscription(subscription_id: str, session: Session = Depends(get_session)) -> Response:
    subscription = session.get(Subscription, subscription_id)
    if subscription is not None:
        session.delete(subscription)
        session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
