"""Artificial location-neutral runner fixtures, not real geographic evidence."""

import json

import pandas as pd
import pytest

from model.evaluation_runner import BASELINE_ID, FEATURE_UNITS, main, run
from model.risk_engine import score_ward
from model.validation import evaluate_predictions


@pytest.fixture
def inputs(tmp_path):
    paths = {key: tmp_path / f"{key}.{suffix}" for key, suffix in (
        ("features", "csv"), ("labels", "csv"), ("metadata", "json"), ("config", "json"))}
    config = {"location": "ARTIFICIAL LOCATION", "administrative_unit_type": "test unit",
              "run_purpose": "synthetic_demonstration",
              "feature_provenance": {name: {"source_ref": "artificial-fixture", "dataset_version_or_date": "test-v1",
                  "units": unit, "evidence_type": "synthetic", "coverage_status": "complete",
                  "coverage_notes": "artificial only", "processing_ref": "test-fixture"} for name, unit in FEATURE_UNITS.items()},
              "boundary_version": "test-boundary", "model_id": BASELINE_ID, "model_version": "test-only",
              "projected_crs": "EPSG:32643", "projection_review_ref": "artificial-review",
              "identity_mode": "explicit_mapping", "identity_reference": "artificial-crosswalk",
              "id_mapping": {"2": "0010", "1": "0099"}, "builtup_increase": 0}
    metadata = {"event_id": "test-event", "event_name": "ARTIFICIAL EVENT", "event_date": "2000-01-01",
                "boundary_source_ref": "artificial-fixture", "observation_protocol": "artificial only",
                "sampling_notes": "not representative", "rainfall_mm": 100, "duration_hours": 6,
                **{key: config[key] for key in ("location", "administrative_unit_type", "boundary_version",
                                              "model_id", "model_version")}}
    features = pd.DataFrame([
        {"ward_id": ward, "official_number": official, "event_id": metadata["event_id"],
         "boundary_version": config["boundary_version"], "elevation_mean": 10, "slope_mean": 2,
         "impervious_frac": 0.5, "dist_to_water_m": 1000,
         "road_density_km_per_sqkm": 5, "underpass_count": 0, "new_metric": "not used"}
        for ward, official in config["id_mapping"].items()])
    labels = pd.DataFrame([{"ward_id": "1", "label": "flooded", "source_ref": "artificial-source",
                            "event_id": metadata["event_id"], "boundary_version": config["boundary_version"]}])
    features.to_csv(paths["features"], index=False)
    labels.to_csv(paths["labels"], index=False)
    for key, value in (("config", config), ("metadata", metadata)):
        paths[key].write_text(json.dumps(value))
    return paths


def execute(paths, output):
    return run(paths["features"], paths["labels"], paths["metadata"], paths["config"], output, top_k=1)


def change_json(paths, key, field, value):
    data = json.loads(paths[key].read_text())
    data[field] = value
    paths[key].write_text(json.dumps(data))


def test_score_export_evaluate_and_reproduce(inputs, tmp_path):
    before = {key: path.read_bytes() for key, path in inputs.items()}
    result = execute(inputs, tmp_path / "out")
    pred = pd.read_csv(tmp_path / "out/predictions.csv")
    assert list(pred) == ["ward_id", "risk_score", "event_id", "boundary_version"]
    assert pred.ward_id.tolist() == [1, 2]
    row = pd.read_csv(inputs["features"]).iloc[0]
    assert pred.iloc[0].risk_score == pytest.approx(score_ward(row, 100, 0, duration_hours=6)[0])
    assert pred.iloc[0].risk_score != score_ward(row, 100, 0, duration_hours=3)[0]
    assert result["runner_manifest"]["scenario"]["builtup_increase"] == 0
    assert result["runner_manifest"]["unused_feature_columns"] == ["new_metric"]
    expected = evaluate_predictions(pred, pd.read_csv(inputs["labels"]), json.loads(inputs["metadata"].read_text()), 1)
    assert result["metrics"] == expected["metrics"]
    assert result["selected_ward_ids"] == [1]
    second = execute(inputs, tmp_path / "again")
    assert result["reproducibility"] == second["reproducibility"]
    assert result["runner_manifest"]["source_sha256"] == second["runner_manifest"]["source_sha256"]
    assert (tmp_path / "out/predictions.csv").read_bytes() == (tmp_path / "again/predictions.csv").read_bytes()
    assert all(path.read_bytes() == before[key] for key, path in inputs.items())


@pytest.mark.parametrize("field,value", [
    ("projected_crs", "EPSG:4326"), ("projected_crs", "EPSG:2263"),
    ("projection_review_ref", ""), ("location", ""), ("identity_mode", "guess"),
    ("id_mapping", {}), ("builtup_increase", 15), ("is_template", True),
    ("weights", {"new_metric": 1}), ("model_id", "new-model"),
])
def test_bad_configuration(inputs, tmp_path, field, value):
    change_json(inputs, "config", field, value)
    with pytest.raises(ValueError):
        execute(inputs, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("field", ["location", "administrative_unit_type", "boundary_version", "model_version"])
def test_event_configuration_alignment(inputs, tmp_path, field):
    change_json(inputs, "metadata", field, "conflicting")
    with pytest.raises(ValueError, match=field):
        execute(inputs, tmp_path / "out")


@pytest.mark.parametrize("field,value", [
    ("elevation_mean", ""), ("slope_mean", "NaN"), ("impervious_frac", "1.1"),
    ("dist_to_water_m", "-1"), ("underpass_count", "1.5"),
    ("road_density_km_per_sqkm", "bad"), ("official_number", "2"),
    ("ward_id", "01"), ("event_id", "wrong-event"),
])
def test_invalid_records_fail_without_outputs(inputs, tmp_path, field, value):
    data = pd.read_csv(inputs["features"], dtype=str)
    data.loc[0, field] = value
    data.to_csv(inputs["features"], index=False)
    with pytest.raises(ValueError):
        execute(inputs, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_identity_assertion_requires_matching_numbers(inputs, tmp_path):
    change_json(inputs, "config", "identity_mode", "same_as_official")
    change_json(inputs, "config", "id_mapping", {})
    with pytest.raises(ValueError, match="official_number"):
        execute(inputs, tmp_path / "bad")
    data = pd.read_csv(inputs["features"], dtype=str)
    data["official_number"] = data.ward_id
    data.to_csv(inputs["features"], index=False)
    execute(inputs, tmp_path / "good")


def test_invalid_labels_before_scoring(inputs, tmp_path, monkeypatch):
    import model.evaluation_runner as runner

    def must_not_score(*args, **kwargs):
        pytest.fail("Scored before evidence validation")

    monkeypatch.setattr(runner, "score_ward", must_not_score)
    obs = pd.read_csv(inputs["labels"])
    obs["label"] = "invalid"
    obs.to_csv(inputs["labels"], index=False)
    with pytest.raises(ValueError, match="label"):
        execute(inputs, tmp_path / "out")


def test_protect_existing_inputs_and_canonical_output(inputs, tmp_path):
    for output in (inputs["features"], tmp_path, tmp_path / "existing"):
        if output.name == "existing":
            output.mkdir()
        with pytest.raises(ValueError, match="new directory"):
            execute(inputs, output)
    from model.evaluation_runner import ROOT

    with pytest.raises(ValueError, match="canonical"):
        execute(inputs, ROOT / "data/processed/validation_metrics.json")


def test_cli_and_invocation(inputs, tmp_path):
    output = tmp_path / "cli"
    argv = [item for key, path in {**inputs, "output": output}.items() for item in (f"--{key}", str(path))]
    assert main(argv) == 0
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["invocation"]["arguments"] == argv
    assert len(manifest["input_files"]["configuration"]["sha256"]) == 64


@pytest.mark.parametrize("kind", ["missing_feature", "duplicate_id", "empty", "nonfinite"])
def test_bad_feature_tables(inputs, tmp_path, kind):
    data = pd.read_csv(inputs["features"], dtype=str)
    if kind == "missing_feature":
        data = data.drop(columns="slope_mean")
    elif kind == "duplicate_id":
        data = pd.concat([data, data.iloc[:1]])
    elif kind == "empty":
        data = data.iloc[:0]
    else:
        data.loc[0, "elevation_mean"] = "inf"
    data.to_csv(inputs["features"], index=False)
    with pytest.raises(ValueError):
        execute(inputs, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_location_neutral_and_hash_change(inputs, tmp_path):
    first = execute(inputs, tmp_path / "first")
    for key in ("config", "metadata"):
        change_json(inputs, key, "location", "ANOTHER ARTIFICIAL LOCATION")
        change_json(inputs, key, "administrative_unit_type", "test district")
    second = execute(inputs, tmp_path / "second")
    assert first["metrics"] == second["metrics"]
    assert first["runner_manifest"]["input_files"]["configuration"]["sha256"] != second["runner_manifest"]["input_files"]["configuration"]["sha256"]


@pytest.mark.parametrize("field,value", [("units", "feet"), ("evidence_type", "guess"),
    ("coverage_status", "assumed"), ("source_ref", ""), ("dataset_version_or_date", ""),
    ("processing_ref", ""), ("coverage_notes", "")])
def test_provenance_validation(inputs, tmp_path, field, value):
    config = json.loads(inputs["config"].read_text())
    config["feature_provenance"]["elevation_mean"][field] = value
    inputs["config"].write_text(json.dumps(config))
    with pytest.raises(ValueError):
        execute(inputs, tmp_path / "out")


@pytest.mark.parametrize("origin", ["synthetic", "unknown"])
def test_historical_rejects_origin(inputs, tmp_path, origin):
    config = json.loads(inputs["config"].read_text())
    config["run_purpose"] = "historical_evaluation"
    for item in config["feature_provenance"].values():
        item["evidence_type"] = origin
    inputs["config"].write_text(json.dumps(config))
    with pytest.raises(ValueError, match="origin"):
        execute(inputs, tmp_path / "out")


def test_missing_provenance_and_synthetic_disclosure(inputs, tmp_path):
    config = json.loads(inputs["config"].read_text())
    change_json(inputs, "config", "feature_provenance", {})
    with pytest.raises(ValueError, match="six"):
        execute(inputs, tmp_path / "bad")
    config["feature_provenance"]["slope_mean"]["coverage_status"] = "partial"
    inputs["config"].write_text(json.dumps(config))
    execute(inputs, tmp_path / "good")
    for filename in ("manifest.json", "evaluation.json"):
        data = json.loads((tmp_path / "good" / filename).read_text())
        assert data["run_purpose"] == "synthetic_demonstration"
        assert "not evidence of historical accuracy" in data["evidence_notice"]
    manifest = json.loads((tmp_path / "good/manifest.json").read_text())
    assert manifest["features_without_complete_attested_coverage"] == ["slope_mean"]
