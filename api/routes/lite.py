"""Lightweight ward shapes for the phone: simplified, rounded, cached, ETagged."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter, Request, Response

router = APIRouter(prefix="/api/v1", tags=["wards"])

_cache: dict[str, Any] = {}


def _round_coords(value, precision: int = 5):
    if isinstance(value, (int, float)):
        return round(float(value), precision)
    if isinstance(value, (list, tuple)):
        return [_round_coords(item, precision) for item in value]
    return value


def _build() -> dict[str, Any]:
    from api.routes.main import load_wards

    wards = load_wards().to_crs("EPSG:4326")
    features = []
    for _, row in wards.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        simplified = geom.simplify(0.0001, preserve_topology=True)
        features.append({
            "type": "Feature",
            "properties": {
                "ward_id": int(row.ward_id),
                "ward_number": str(row.ward_number),
            },
            "geometry": _round_coords(simplified.__geo_interface__),
        })
    return {"type": "FeatureCollection", "features": features}


def reset_cache() -> None:
    _cache.clear()


def warm() -> None:
    """Build the simplified payload once so the first request is instant."""
    if "payload" in _cache:
        return
    payload = _build()
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    _cache["payload"] = body
    _cache["etag"] = '"' + hashlib.sha256(body).hexdigest()[:32] + '"'


@router.get("/wards/lite")
def wards_lite(request: Request) -> Response:
    warm()

    body: bytes = _cache["payload"]
    etag: str = _cache["etag"]

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "public, max-age=86400"})

    return Response(
        content=body,
        media_type="application/geo+json",
        headers={
            "ETag": etag,
            "Cache-Control": "public, max-age=86400",
        },
    )
