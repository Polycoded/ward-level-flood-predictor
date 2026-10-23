"""Symmetric encryption for phone/chat identifiers at rest (DPDP-friendly)."""

from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken

from api.settings import settings

_DEV_KEY = b"flood-predictor-dev-insecure-key-change-me"


def _fernet_key() -> bytes:
    raw = (settings.phone_encryption_key or "").strip()
    if raw:
        # Accept a real Fernet key (44 chars) or hash any passphrase to 32 bytes.
        if len(raw) == 44:
            return raw.encode()
        return base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    return base64.urlsafe_b64encode(hashlib.sha256(_DEV_KEY).digest())


def _cipher() -> Fernet:
    return Fernet(_fernet_key())


def encrypt(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("value to encrypt must be a non-empty string")
    return _cipher().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    try:
        return _cipher().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise ValueError("cannot decrypt stored identifier") from exc


def is_encrypted(value: str) -> bool:
    try:
        decrypt(value)
        return True
    except ValueError:
        return False


def identifier_hash(value: str) -> str:
    """Deterministic, non-reversible lookup key for an encrypted identifier."""
    if not value:
        raise ValueError("identifier_hash requires a non-empty value")
    return hmac.new(_fernet_key(), value.encode("utf-8"), hashlib.sha256).hexdigest()


def mask(value: str) -> str:
    """Last 4 characters only, for logs and admin display."""
    if not value:
        return ""
    return "*" * max(0, len(value) - 4) + value[-4:]
