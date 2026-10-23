"""Artificial readiness fixtures; not Chennai boundary evidence."""

import json

import pandas as pd
import pytest
from shapely.geometry import box, mapping

from model.evaluation_runner import FEATURES
from model.input_readiness import ROOT, inspect_inputs, main


@pytest.fixture
def artifacts(tmp_path):
    boundary, features = tmp_path / "wards.geojson", tmp_path / "features.csv"
    boundary.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"ward_id": 1, "ward_number": "099", "ward_name": "Test ward"},
         "geometry": mapping(box(80, 13, 80.01, 13.01))}]}))
    pd.DataFrame([{**dict.fromkeys(FEATURES, 0), "ward_id": 1, "official_number": "099"}]).to_csv(features, index=False)
    return boundary, features


def check(artifacts):
    return inspect_inputs(*artifacts, boundary_version="artificial-v1", identity_reference="artificial-review")


def test_valid_and_read_only(artifacts, tmp_path):
    before = [p.read_bytes() for p in artifacts]
    result = check(artifacts)
    assert result["identity_ready"] and result["structural_scoring_ready"]
    assert not result["historical_evaluation_ready"]
    assert "zeros" in " ".join(result["limitations"])
    assert [p.read_bytes() for p in artifacts] == before
    assert not inspect_inputs(*artifacts)["identity_ready"]
    output = tmp_path / "report.json"
    main(["--boundary", str(artifacts[0]), "--features", str(artifacts[1]), "--output", str(output)])
    assert json.loads(output.read_text())["identity_ready"] is False
    with pytest.raises(SystemExit):
        main(["--boundary", str(artifacts[0]), "--output", str(output)])
    with pytest.raises(SystemExit):
        main(["--boundary", str(artifacts[0]), "--output", str(ROOT / "data/processed/new.json")])


def test_zone_boundary_signal(artifacts):
    raw = json.loads(artifacts[0].read_text())
    raw["features"][0]["properties"].update(ward_name="Zone 1", ward_number="")
    artifacts[0].write_text(json.dumps(raw))
    result = check(artifacts)
    assert result["boundary"]["zone_name_signals"] == ["Zone 1"]
    assert result["boundary"]["blank_official_number_rows"] == [0]
    assert not result["identity_ready"]


def test_missing_artifacts(tmp_path):
    result = inspect_inputs(tmp_path / "missing.json", tmp_path / "missing.parquet")
    assert not result["structural_scoring_ready"]
    assert any("Features unavailable" in message for message in result["blockers"])


@pytest.mark.parametrize("value", ["", "NaN", "inf", "-1", "bad"])
def test_invalid_measurements(artifacts, value):
    frame = pd.read_csv(artifacts[1], dtype=str)
    frame["dist_to_water_m"] = value
    frame.to_csv(artifacts[1], index=False)
    report = check(artifacts)
    assert not report["structural_scoring_ready"]
    assert report["features"]["invalid_measurements"][0]["feature"] == "dist_to_water_m"


def test_missing_column_and_id_alignment(artifacts):
    frame = pd.read_csv(artifacts[1], dtype=str).drop(columns="slope_mean")
    frame["ward_id"] = "2"
    frame.to_csv(artifacts[1], index=False)
    report = check(artifacts)
    assert report["features"]["missing_columns"] == ["slope_mean"]
    assert report["features"]["boundary_only_ids"] == [1]
    assert report["features"]["feature_only_ids"] == [2]


def test_duplicates_and_invalid_geometry(artifacts):
    raw = json.loads(artifacts[0].read_text())
    raw["features"] *= 2
    raw["features"][0]["geometry"] = None
    artifacts[0].write_text(json.dumps(raw))
    report = check(artifacts)
    assert report["boundary"]["duplicate_ids"] == [1]
    assert report["boundary"]["duplicate_official_numbers"] == ["099"]
    assert report["boundary"]["missing_geometry_rows"]
    assert not report["identity_ready"]


def test_mock_metrics(artifacts, tmp_path):
    path = tmp_path / "metrics.json"
    path.write_text('{"notes":"MOCK NUMBERS: placeholder"}')
    report = inspect_inputs(*artifacts, metrics=path)
    assert report["metrics"]["explicit_mock"]
    assert report["metrics"]["status"] == "unsuitable_for_accuracy_claims"
    assert report["historical_evaluation_ready"] is False
    assert any("MOCK metrics" in reason for reason in report["historical_blockers"])
    assert json.loads(path.read_text()) == {"notes": "MOCK NUMBERS: placeholder"}


def test_invalid_empty_and_missing_ids(artifacts):
    raw = json.loads(artifacts[0].read_text())
    raw["features"][0]["properties"]["ward_id"] = None
    raw["features"][0]["geometry"] = {"type": "Polygon", "coordinates": [[[0, 0], [2, 2], [0, 2], [2, 0], [0, 0]]]}
    artifacts[0].write_text(json.dumps(raw))
    report = check(artifacts)
    assert report["boundary"]["invalid_geometry_rows"] == [0]
    assert report["boundary"]["missing_id_rows"] == [0]
    raw["features"][0]["geometry"] = {"type": "Polygon", "coordinates": []}
    artifacts[0].write_text(json.dumps(raw))
    assert check(artifacts)["boundary"]["empty_geometry_rows"] == [0]


def test_official_number_alignment(artifacts):
    frame = pd.read_csv(artifacts[1], dtype=str)
    frame["official_number"] = "100"
    frame.to_csv(artifacts[1], index=False)
    assert check(artifacts)["features"]["official_number_mismatches"] == [1]


@pytest.mark.parametrize("second_box, expected", [
    ((80.005, 13, 80.015, 13.01), 1),
    ((80.01, 13, 80.02, 13.01), 0),
    ((80.02, 13, 80.03, 13.01), 0),
])
def test_overlap_diagnostic(artifacts, second_box, expected):
    raw = json.loads(artifacts[0].read_text())
    raw["features"].append({"type": "Feature", "properties": {
        "ward_id": 2, "ward_number": "100", "ward_name": "Artificial ward"},
        "geometry": mapping(box(*second_box))})
    artifacts[0].write_text(json.dumps(raw))
    before = artifacts[0].read_bytes()
    report = check(artifacts)
    overlap = report["boundary"]["overlap_review"]
    assert overlap["pair_count"] == expected
    assert overlap["pairs"] == ([{"rows": [0, 1], "ward_ids": ["1", "2"]}] if expected else [])
    assert report["identity_ready"]  # Diagnostic does not silently redefine identity gates.
    assert artifacts[0].read_bytes() == before


def test_overlap_skips_invalid_geometry(artifacts):
    raw = json.loads(artifacts[0].read_text())
    raw["features"][0]["geometry"] = None
    artifacts[0].write_text(json.dumps(raw))
    assert check(artifacts)["boundary"]["overlap_review"]["status"] == "not_assessed"
