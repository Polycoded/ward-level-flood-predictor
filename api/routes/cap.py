"""CAP 1.2 feed: the honest bridge to SACHET / cell-broadcast systems.

Everything is ``status=Exercise`` until an official turns exercise mode off.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, timedelta

from fastapi import APIRouter, Depends, Response
from sqlmodel import Session, select

from api.db import Alert, get_session, utcnow
from api.settings import settings

router = APIRouter(prefix="/api/v1", tags=["alerts"])

CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"
ET.register_namespace("", CAP_NS)


def _tag(name: str) -> str:
    return f"{{{CAP_NS}}}{name}"


def _iso(value) -> str:
    if value is None:
        value = utcnow()
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ward_polygon(ward_id: int) -> str | None:
    try:
        from api.routes.main import load_wards

        wards = load_wards().to_crs("EPSG:4326")
        match = wards[wards["ward_id"] == ward_id]
        if len(match) == 0:
            return None
        geom = match.iloc[0].geometry
        if geom is None or geom.is_empty:
            return None
        geom = geom.simplify(0.0005, preserve_topology=True)
        if geom.geom_type == "MultiPolygon":
            geom = max(geom.geoms, key=lambda polygon: polygon.area)
        if geom.geom_type != "Polygon":
            return None
        coords = list(geom.exterior.coords)
        if len(coords) > 40:
            step = max(1, len(coords) // 40)
            coords = coords[::step] + [coords[-1]]
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        return " ".join(f"{lat:.4f},{lon:.4f}" for lon, lat in coords)
    except Exception:
        return None


def _severity(alert: Alert) -> str:
    return "Severe" if alert.alert_type == "warning" else "Moderate"


def _build_alert(alert: Alert) -> ET.Element:
    node = ET.Element(_tag("alert"))
    ET.SubElement(node, _tag("identifier")).text = alert.id
    ET.SubElement(node, _tag("sender")).text = "flood-predictor@example.org"
    ET.SubElement(node, _tag("sent")).text = _iso(alert.created_at)
    ET.SubElement(node, _tag("status")).text = "Exercise" if settings.exercise_mode else "Actual"
    ET.SubElement(node, _tag("msgType")).text = "Alert"
    ET.SubElement(node, _tag("scope")).text = "Public"

    info = ET.SubElement(node, _tag("info"))
    ET.SubElement(info, _tag("language")).text = "en-IN"
    ET.SubElement(info, _tag("category")).text = "Met"
    event_name = "Flood Warning" if alert.alert_type == "warning" else "Flood Watch"
    ET.SubElement(info, _tag("event")).text = event_name
    ET.SubElement(info, _tag("responseType")).text = (
        "Evacuate" if alert.alert_type == "warning" else "Prepare"
    )
    ET.SubElement(info, _tag("urgency")).text = (
        "Immediate" if alert.alert_type == "warning" else "Expected"
    )
    ET.SubElement(info, _tag("severity")).text = _severity(alert)
    ET.SubElement(info, _tag("certainty")).text = "Possible"
    ET.SubElement(info, _tag("effective")).text = _iso(alert.approved_at or alert.created_at)
    ET.SubElement(info, _tag("expires")).text = _iso(
        (alert.approved_at or alert.created_at) + timedelta(hours=6)
    )
    ET.SubElement(info, _tag("senderName")).text = "Chennai Flood Predictor (Exercise)"
    ET.SubElement(info, _tag("headline")).text = f"{event_name}: {alert.ward_name}"
    ET.SubElement(info, _tag("description")).text = alert.message_en
    ET.SubElement(info, _tag("instruction")).text = (
        "Avoid underpasses and low-lying roads. Follow official instructions. "
        "This is an exercise."
    )

    area = ET.SubElement(info, _tag("area"))
    ET.SubElement(area, _tag("areaDesc")).text = alert.ward_name or f"Ward {alert.ward_id}"
    polygon = _ward_polygon(alert.ward_id)
    if polygon:
        ET.SubElement(area, _tag("polygon")).text = polygon
    geocode = ET.SubElement(area, _tag("geocode"))
    ET.SubElement(geocode, _tag("valueName")).text = "ward_id"
    ET.SubElement(geocode, _tag("value")).text = str(alert.ward_id)
    return node


@router.get("/alerts/cap.xml")
def cap_feed(session: Session = Depends(get_session)) -> Response:
    rows = session.exec(
        select(Alert)
        .where(Alert.status.in_(["approved", "sent", "sending"]))
        .order_by(Alert.created_at.desc())
        .limit(50)
    ).all()

    root = ET.Element(_tag("alerts"))
    for alert in rows:
        root.append(_build_alert(alert))

    body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return Response(
        content=body,
        media_type="application/xml",
        headers={"Cache-Control": "no-store"},
    )
