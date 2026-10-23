"""Operator authentication and SSRF protection.

Two public-safety actions must never be anonymous: approving an alert (which
fans a broadcast out to every subscriber in a ward) and cancelling one (which
suppresses a warning). ``require_admin`` gates them behind a shared secret and
fails closed when no secret is configured.

``is_safe_push_endpoint`` stops the Web Push subscription endpoint from being
used for server-side request forgery: without it, a subscriber can point the
server at an internal address (cloud metadata, localhost, a private range) and
the dispatcher will dutifully connect to it.
"""

from __future__ import annotations

import hmac
import ipaddress
import socket
from urllib.parse import urlsplit

from fastapi import Header, HTTPException, status

from api.settings import settings

# Hostnames that never belong to a real push service and often front internal data.
_BLOCKED_HOSTS = {"localhost", "ip6-localhost", "metadata", "metadata.google.internal"}


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Allow the request only when it carries the configured operator token.

    Fails closed: with no ``ADMIN_API_TOKEN`` set, the action is refused rather
    than left open, because dispatching or suppressing a public alert anonymously
    is the exact abuse we are preventing.
    """
    expected = settings.admin_api_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Operator authentication is not configured on the server (set ADMIN_API_TOKEN).",
        )
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid operator token is required for this action.",
        )


def _ip_is_public(value: str) -> bool:
    try:
        addr = ipaddress.ip_address(value)
    except ValueError:
        return False
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def is_safe_push_endpoint(url: str, *, resolve: bool = False) -> bool:
    """True only for an https URL that cannot reach an internal address.

    When ``resolve`` is false the check is cheap (no DNS): it rejects non-https
    URLs, blocked hostnames and private/reserved IP literals. When true it also
    resolves a hostname and rejects it if any address is internal — the real
    SSRF guard, used at send time. A name that does not resolve is allowed: it
    cannot reach an internal host, and offline test endpoints rely on this.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme != "https" or not parts.hostname:
        return False
    host = parts.hostname.lower().rstrip(".")
    if host in _BLOCKED_HOSTS:
        return False

    try:
        ipaddress.ip_address(host)
        return _ip_is_public(host)  # IP literal: judge it directly
    except ValueError:
        pass  # a hostname, not an IP

    # Real push services always end in an alphabetic TLD. A numeric or hex last label
    # (2130706433, 127.1, 0x7f000001) is an obfuscated IP that resolvers expand to
    # loopback or a private address, so refuse it without needing DNS.
    tld = host.rsplit(".", 1)[-1]
    if tld.startswith("0x") or not any(ch.isalpha() for ch in tld):
        return False

    if not resolve:
        return True
    try:
        infos = socket.getaddrinfo(host, parts.port or 443, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, OSError):
        return True  # unresolvable: cannot be used to reach an internal host
    return bool(infos) and all(_ip_is_public(info[4][0]) for info in infos)
