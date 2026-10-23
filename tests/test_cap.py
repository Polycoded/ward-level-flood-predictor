from xml.etree import ElementTree as ET

import geopandas as gpd
import pytest
from pyproj import Transformer
from shapely.geometry import MultiPolygon, Polygon, box

from model.alert_contract import digest
from model.alerts import exercise_message
from model.cap import NS, generate_cap, validate_cap_xml


@pytest.fixture
def cap_args(exercise_candidate):
    content = exercise_message(exercise_candidate, exercise_id="artificial-exercise")
    return dict(candidate=exercise_candidate, content=content,
        approval={"status": "approved", "cancelled": False, "candidate_id": exercise_candidate["candidate_id"],
                  "content_digest": digest(content), "approved_by": "artificial-reviewer",
                  "approved_at": "2000-01-01T00:00:00Z"},
        wards=gpd.GeoDataFrame({"ward_id": [1], "ward_number": ["168"]},
                              geometry=[box(400000, 1450000, 400100, 1450100)], crs=32644),
        sender="exercise.invalid", sent="2000-01-01T00:00:00Z", now="2000-01-01T00:00:00Z")


def test_official_xsd_exercise_fields_and_coordinate_order(cap_args):
    result = generate_cap(**cap_args)
    assert result["status"] == "exported", result
    assert result["validation"]["status"] == "valid"
    root = ET.fromstring(result["xml"])
    def get(tag):
        return root.find(f".//{{{NS}}}{tag}")
    assert get("status").text == "Exercise"
    assert get("msgType").text == "Alert" and get("scope").text == "Restricted"
    assert get("urgency").text == get("severity").text == get("certainty").text == "Unknown"
    assert get("onset") is None
    assert get("sent").text.endswith("-00:00")
    lat, lon = map(float, get("polygon").text.split()[0].split(","))
    x, y = cap_args["wards"].geometry.iloc[0].exterior.coords[0]
    expected_lon, expected_lat = Transformer.from_crs(32644, 4326, always_xy=True).transform(x, y)
    assert lat == pytest.approx(expected_lat) and lon == pytest.approx(expected_lon)


def test_holes_explicitly_unsupported_and_multipart_preserved(cap_args):
    outer = box(400000, 1450000, 400100, 1450100)
    cap_args["wards"].geometry = [Polygon(outer.exterior.coords, [box(400020, 1450020, 400040, 1450040).exterior.coords])]
    result = generate_cap(**cap_args)
    assert result["status"] == "unsupported" and "xml" not in result
    cap_args["wards"].geometry = [MultiPolygon([outer, box(400200, 1450000, 400300, 1450100)])]
    result = generate_cap(**cap_args)
    root = ET.fromstring(result["xml"])
    assert len(root.findall(f".//{{{NS}}}polygon")) == 2


@pytest.mark.parametrize("mutation", ["pending", "cancelled", "tampered_content", "tampered_candidate", "expired", "actual", "identity", "sender", "future"])
def test_reject_unapproved_invalid_or_expired(cap_args, mutation):
    if mutation == "pending":
        cap_args["approval"]["status"] = "pending"
    if mutation == "cancelled":
        cap_args["approval"]["cancelled"] = True
    if mutation == "tampered_content":
        cap_args["content"]["text"] += "changed"
    if mutation == "tampered_candidate":
        cap_args["candidate"]["score"] = 0.99
    if mutation == "expired":
        cap_args["now"] = "2000-01-01T02:00:00Z"
    if mutation == "actual":
        cap_args["candidate"]["mode"] = "Actual"
    if mutation == "identity":
        cap_args["wards"]["ward_number"] = ["1"]
    if mutation == "sender":
        cap_args["sender"] = "not an identifier"
    if mutation == "future":
        cap_args["sent"] = "2000-01-01T00:01:00Z"
    with pytest.raises(ValueError):
        generate_cap(**cap_args)


def test_xml_escaping_and_tamil(cap_args):
    cap_args["content"] = exercise_message(cap_args["candidate"], exercise_id="A&B <exercise>", language="ta")
    cap_args["approval"]["content_digest"] = digest(cap_args["content"])
    result = generate_cap(**cap_args)
    assert result["status"] == "exported"
    assert "&amp;" in result["xml"] and "&lt;exercise&gt;" in result["xml"]
    assert ET.fromstring(result["xml"]).find(f".//{{{NS}}}language").text == "ta"


@pytest.mark.parametrize("tag,value", [("status", "Banana"), ("severity", "certain"), ("sent", "2000-01-01"), ("category", "Flood")])
def test_official_schema_rejects_invalid_enums_and_time(cap_args, tag, value):
    xml = generate_cap(**cap_args)["xml"]
    root = ET.fromstring(xml)
    root.find(f".//{{{NS}}}{tag}").text = value
    assert validate_cap_xml(ET.tostring(root, encoding="unicode"))["status"] == "invalid"


def test_official_schema_requires_sender(cap_args):
    root = ET.fromstring(generate_cap(**cap_args)["xml"])
    root.remove(root.find(f"{{{NS}}}sender"))
    assert validate_cap_xml(ET.tostring(root, encoding="unicode"))["status"] == "invalid"
