"""Isolated evaluator-output transport tests, not historical accuracy evidence."""

import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes import main as routes
from model.validation import LABEL_COLUMNS, METADATA_TEXT, evaluate_predictions


@pytest.fixture
def metrics_path(tmp_path, monkeypatch):
    path = tmp_path / "metrics.json"
    monkeypatch.setattr(routes, "VALIDATION_PATH", path)
    return path


@pytest.mark.parametrize("text", [None, "", "{}", "{broken", "[]", '{"value":NaN}',
                                  '{"precision_at_20":0.65,"notes":"MOCK NUMBERS"}',
                                  '{"precision_at_20":0.65}', '{"schema_version":"3.0"}'])
def test_untrusted_metrics_are_unavailable(metrics_path, text):
    if text is not None:
        metrics_path.write_text(text)
    with TestClient(app) as client:
        response = client.get("/api/v1/validation")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unavailable"
    assert data["status_reason"]
    assert data["metrics"] is None
    assert "precision_at_20" not in data
    assert not metrics_path.exists() if text is None else metrics_path.read_text() == text


def evaluator_output(known=2, prediction_count=2, top_k=2, mixed=False):
    metadata = {key: "artificial-test-only" for key in METADATA_TEXT}
    metadata.update(event_date="2000-01-01", rainfall_mm=100, duration_hours=3)
    predictions = pd.DataFrame([
        {"ward_id": ward, "risk_score": score, "event_id": metadata["event_id"],
         "boundary_version": metadata["boundary_version"]}
        for ward in range(1, prediction_count + 1)
        for score in [1 / (ward + 1)]
    ], columns=["ward_id", "risk_score", "event_id", "boundary_version"])
    labels = pd.DataFrame([
        {"ward_id": ward, "label": "non_flooded" if mixed and ward % 2 == 0 else "flooded", "source_ref": "artificial-only",
         "event_id": metadata["event_id"], "boundary_version": metadata["boundary_version"]}
        for ward in range(1, known + 1)
    ], columns=LABEL_COLUMNS)
    return evaluate_predictions(predictions, labels, metadata, top_k=top_k)


@pytest.mark.parametrize("known,status", [(0, "unavailable"), (1, "partial"), (2, "evaluated")])
def test_schema_two_retains_evaluator_contract(metrics_path, known, status):
    expected = evaluator_output(known)
    metrics_path.write_text(json.dumps(expected))
    with TestClient(app) as client:
        response = client.get("/api/v1/validation")
    assert response.status_code == 200
    assert response.json() == expected
    assert response.json()["status"] == status
    assert response.json()["metrics"]["false_positive_rate_among_observed_non_flooded"]["value"] is None


@pytest.mark.parametrize("field", ["rainfall_mm", "duration_hours"])
@pytest.mark.parametrize("invalid", [True, False, None, "3", float("nan"), float("inf"), -float("inf")])
def test_invalid_event_measurements(metrics_path, field, invalid):
    payload = evaluator_output()
    payload["event_metadata"][field] = invalid
    assert_rejected(metrics_path, payload)


@pytest.mark.parametrize("field,invalid", [
    ("rainfall_mm", -0.5), ("rainfall_mm", 501),
    ("duration_hours", 0), ("duration_hours", 0.5),
    ("duration_hours", 25), ("duration_hours", 1000),
])
def test_event_measurement_ranges(metrics_path, field, invalid):
    payload = evaluator_output()
    payload["event_metadata"][field] = invalid
    assert_rejected(metrics_path, payload)


def assert_rejected(path, payload):
    text = json.dumps(payload)
    path.write_text(text)
    with TestClient(app) as client:
        response = client.get("/api/v1/validation")
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["status_reason"]
    assert response.json()["metrics"] is None
    assert path.read_text() == text


@pytest.mark.parametrize("section,key", [
    ("metrics", "precision_at_k"), ("metrics", "precision_among_observed_selected"),
    ("metrics", "recall_among_observed_flooded"),
    ("metrics", "false_positive_rate_among_observed_non_flooded"), ("coverage", "selected"),
    ("coverage", "prediction_universe"),
])
@pytest.mark.parametrize("field,invalid", [("numerator", 3), ("value", 0.25)])
def test_metric_arithmetic_rejected(metrics_path, section, key, field, invalid):
    payload = evaluator_output(mixed=True)
    payload[section][key][field] = invalid
    assert_rejected(metrics_path, payload)


@pytest.mark.parametrize("invalid", [
    {"value": None, "numerator": 1, "denominator": 0, "unavailable_reason": "No eligible observations"},
    {"value": None, "numerator": 0, "denominator": 0, "unavailable_reason": None},
    {"value": 0, "numerator": 0, "denominator": 0, "unavailable_reason": None},
])
def test_invalid_null_and_zero_denominator_metrics(metrics_path, invalid):
    payload = evaluator_output()
    payload["metrics"]["false_positive_rate_among_observed_non_flooded"] = invalid
    assert_rejected(metrics_path, payload)


def test_confirmed_one_over_one_fraction_bug(metrics_path):
    payload = evaluator_output(top_k=1)
    assert payload["metrics"]["precision_at_k"]["numerator"] == 1
    assert payload["metrics"]["precision_at_k"]["denominator"] == 1
    payload["metrics"]["precision_at_k"]["value"] = 0.25
    assert_rejected(metrics_path, payload)


def test_genuine_fractional_metrics(metrics_path):
    payload = evaluator_output(3, 3, 3, mixed=True)
    assert payload["metrics"]["precision_at_k"]["value"] == 2 / 3
    metrics_path.write_text(json.dumps(payload))
    with TestClient(app) as client:
        assert client.get("/api/v1/validation").json() == payload


@pytest.mark.parametrize("field,invalid", [
    ("selected_ward_ids", [1, 1]), ("selected_ward_ids", [1]),
    ("actual_selected_size", 1), ("requested_top_k", 0),
    ("requested_top_k", 1), ("prediction_count", 1),
])
def test_selection_contract_rejected(metrics_path, field, invalid):
    payload = evaluator_output()
    payload[field] = invalid
    assert_rejected(metrics_path, payload)


@pytest.mark.parametrize("rain,duration", [(0, 1), (500, 24), (0.5, 1.5)])
def test_valid_measurement_bounds_preserved(metrics_path, rain, duration):
    payload = evaluator_output()
    payload["event_metadata"].update(rainfall_mm=rain, duration_hours=duration)
    metrics_path.write_text(json.dumps(payload))
    with TestClient(app) as client:
        assert client.get("/api/v1/validation").json() == payload


@pytest.mark.parametrize("known,prediction_count,top_k", [(1, 3, 3), (0, 2, 2), (0, 0, 20), (2, 2, 20)])
def test_fractional_coverage_nulls_and_selection_limits(metrics_path, known, prediction_count, top_k):
    payload = evaluator_output(known, prediction_count, top_k)
    metrics_path.write_text(json.dumps(payload))
    with TestClient(app) as client:
        assert client.get("/api/v1/validation").json() == payload


@pytest.mark.parametrize("delta,accepted", [(5e-13, True), (2e-12, False)])
def test_fraction_tolerance_is_absolute(metrics_path, delta, accepted):
    payload = evaluator_output(1, 3, 3)
    payload["coverage"]["prediction_universe"]["value"] += delta
    if not accepted:
        assert_rejected(metrics_path, payload)
    else:
        metrics_path.write_text(json.dumps(payload))
        with TestClient(app) as client:
            assert client.get("/api/v1/validation").json() == payload
