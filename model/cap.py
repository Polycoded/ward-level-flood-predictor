"""Standalone CAP 1.2 Exercise export. No endpoint, issuing authority or delivery."""
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET

import geopandas as gpd

from model.alert_contract import digest, instant, text
from model.distance import _validate_crs, _validate_geometry

NS = "urn:oasis:names:tc:emergency:cap:1.2"
SCHEMA = Path(__file__).resolve().parents[1] / "data/fixtures/cap/CAP-v1.2.xsd"
ET.register_namespace("", NS)


def _stamp(value: str) -> str:
    parsed = instant(value)
    if parsed.microsecond:
        raise ValueError("CAP profile requires whole seconds; no silent timestamp truncation")
    # CAP 1.2 section 3.3.2: numeric offsets; UTC represented as -00:00, not Z.
    return parsed.isoformat().replace("+00:00", "-00:00")


def _identifier(value: str) -> str:
    text(value, "CAP identifier/sender")
    if any(c.isspace() or c in ",<&" for c in value):
        raise ValueError("CAP identifiers cannot contain whitespace, comma, < or &")
    return value


def validate_cap_xml(xml: str, *, schema: Path = SCHEMA) -> dict:
    executable = shutil.which("xmllint")
    if executable is None:
        return {"status": "unavailable", "reason": "xmllint required for official XSD validation"}
    completed = subprocess.run([executable, "--nonet", "--noout", "--schema", str(schema), "-"],
                               input=xml, text=True, capture_output=True, timeout=15, check=False)
    return {"status": "valid" if completed.returncode == 0 else "invalid",
            "validator": "xmllint", "schema": str(schema), "diagnostic": completed.stderr.strip()}


def generate_cap(candidate: dict, content: dict, approval: dict, wards: gpd.GeoDataFrame, *,
                 sender: str, sent: str, now: str) -> dict:
    """Caller-attested approval must bind exact candidate and rendered content digests.

    Only initial Exercise Alerts supported. Cancellation/update dispatch is a separate
    orchestration responsibility. Holed polygons return unsupported (CAP has no hole ring).
    """
    if candidate.get("mode") != "Exercise" or candidate.get("status") != "pending":
        raise ValueError("Only pending Exercise candidates can be approved for export")
    if content.get("mode") != "Exercise" or content.get("candidate_id") != candidate.get("candidate_id"):
        raise ValueError("Exercise content/candidate mismatch")
    if content.get("candidate_digest") != digest(candidate):
        raise ValueError("Candidate changed after content generation")
    if (approval.get("status") != "approved" or approval.get("cancelled") is not False or
            approval.get("candidate_id") != candidate["candidate_id"] or
            approval.get("content_digest") != digest(content)):
        raise ValueError("Explicit uncancelled approval bound to content is required")
    text(approval.get("approved_by"), "approved_by")
    created, approved, sent_time, current, expires = map(instant, (
        candidate["created_at"], approval["approved_at"], sent, now, candidate["expires_at"]))
    if not created <= approved <= sent_time <= current < expires:
        raise ValueError("Unapproved, future, expired or inconsistent CAP times")
    _identifier(sender)
    _identifier(candidate["candidate_id"])
    ident = digest([candidate["candidate_id"], digest(content), sender, _stamp(sent)])
    exercise_id = text(content.get("exercise_id"), "exercise_id")
    if content.get("ward_id") != candidate["ward_id"] or content.get("ward_number") != candidate["ward_number"]:
        raise ValueError("Content identity differs from approved candidate")
    for field in ("text", "headline", "instruction"):
        text(content.get(field), field)
    if "EXERCISE" not in content["text"] or "EXERCISE" not in content["headline"]:
        raise ValueError("Exercise identification must be visible")
    if content.get("language") not in ("en", "ta"):
        raise ValueError("Unsupported content language")
    if wards.crs is None or wards.ward_id.duplicated().any():
        raise ValueError("Declared CRS and unique ward IDs required")
    selected = wards[wards.ward_id == candidate["ward_id"]]
    if len(selected) != 1 or str(selected.iloc[0].ward_number) != candidate["ward_number"]:
        raise ValueError("Actual ward geometry/official identity required")
    _validate_crs(selected.crs)
    geom = selected.iloc[0].geometry
    _validate_geometry(geom)
    if geom is None or geom.is_empty or geom.geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError("Valid polygon geometry required")
    parts = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    if any(len(part.interiors) for part in parts):
        return {"status": "unsupported", "reason": "CAP polygon rings cannot encode holes without broadening targeting; no exterior-only export."}
    transformed = selected.to_crs("EPSG:4326").iloc[0].geometry
    _validate_geometry(transformed)
    parts = [transformed] if transformed.geom_type == "Polygon" else list(transformed.geoms)
    polygons = []
    for part in parts:
        coords = list(part.exterior.coords)
        if any(not (-180 <= lon <= 180 and -90 <= lat <= 90) for lon, lat in coords):
            raise ValueError("Transformed coordinates outside WGS84 range")
        if any(abs(a[0] - b[0]) > 180 for a, b in zip(coords, coords[1:])):
            return {"status": "unsupported", "reason": "Antimeridian targeting requires reviewed representation"}
        polygons.append(" ".join(f"{lat!r},{lon!r}" for lon, lat in coords))
    root = ET.Element(f"{{{NS}}}alert")

    def add(parent, tag, value):
        element = ET.SubElement(parent, f"{{{NS}}}{tag}")
        element.text = str(value)
        return element

    for key, value in (("identifier", ident), ("sender", sender), ("sent", _stamp(sent)),
                       ("status", "Exercise"), ("msgType", "Alert"), ("scope", "Restricted"),
                       ("restriction", "Designated exercise participants only; not for public warning"),
                       ("note", f"EXERCISE {exercise_id}; caller-attested approval; no issuing authority asserted")):
        add(root, key, value)
    info = ET.SubElement(root, f"{{{NS}}}info")
    for key, value in (("language", content["language"]), ("category", "Met"),
                       ("event", "EXERCISE uncalibrated flood screening"), ("responseType", "Assess"),
                       ("urgency", "Unknown"), ("severity", "Unknown"), ("certainty", "Unknown"),
                       ("effective", _stamp(sent)), ("expires", _stamp(candidate["expires_at"])),
                       ("headline", content["headline"]), ("description", content["text"]),
                       ("instruction", content["instruction"])):
        add(info, key, value)
    # No onset: the index cannot predict flood onset. Expiry is content validity, not hazard end.
    for key, value in (("internal_ward_id", candidate["ward_id"]), ("official_ward_number", candidate["ward_number"]),
                       ("model_version", candidate["model_version"]), ("policy_version", candidate["policy_version"]),
                       ("rainfall_kind", candidate["rainfall"]["kind"])):
        parameter = ET.SubElement(info, f"{{{NS}}}parameter")
        add(parameter, "valueName", key)
        add(parameter, "value", value)
    area = ET.SubElement(info, f"{{{NS}}}area")
    add(area, "areaDesc", f"EXERCISE official ward {candidate['ward_number']}; supplied full geometry, not certified coverage")
    for polygon in polygons:
        add(area, "polygon", polygon)
    xml = ET.tostring(root, encoding="unicode", xml_declaration=True)
    validation = validate_cap_xml(xml)
    if validation["status"] != "valid":
        return {"status": "unavailable", "reason": "Official XSD validation did not pass", "validation": validation}
    return {"status": "exported", "xml": xml, "validation": validation,
            "approval_basis": "caller_attested_not_independently_verified"}
