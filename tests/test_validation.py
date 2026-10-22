"""Artificial evaluation fixtures only; no historical observations or accuracy evidence."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from model.validation import (
    LABEL_COLUMNS,
    VALIDATION_PATH,
    evaluate_predictions,
    load_validation_metrics,
    main,
    save_validation_metrics,
    validate_against_historical,
)


@pytest.fixture
def metadata():
    return {
        "event_id": "artificial-event", "event_name": "ARTIFICIAL TEST ONLY",
        "event_date": "2000-01-01", "boundary_version": "artificial-boundaries-v1",
        "boundary_source_ref": "test-fixture:invented-grid-not-real-wards",
        "observation_protocol": "Artificial unit test labels, not observations",
        "sampling_notes": "Not representative; invented test fixture only",
        "model_id": "artificial-model", "model_version": "test-only",
        "rainfall_mm": 100, "duration_hours": 3,
    }


def predictions(metadata, ids=(3, 1, 4, 2), scores=(0.5, 0.9, 0.1, 0.5)):
    return pd.DataFrame({"ward_id": ids, "risk_score": scores,
                         "event_id": metadata["event_id"],
                         "boundary_version": metadata["boundary_version"]})


def labels(metadata, entries=()):
    return pd.DataFrame([
        {"ward_id": ward, "label": label,
         "source_ref": "test-fixture:artificial-label" if label != "unknown" else "",
         "event_id": metadata["event_id"], "boundary_version": metadata["boundary_version"]}
        for ward, label in entries
    ], columns=LABEL_COLUMNS)


def test_sort_ties_and_observed_only_counts(metadata):
    result = evaluate_predictions(predictions(metadata), labels(metadata, [
        (1, "flooded"), (2, "non_flooded"), (3, "flooded"), (4, "non_flooded"),
    ]), metadata, 2)
    assert result["selected_ward_ids"] == [1, 2]
    assert result["status"] == "evaluated"
    assert result["requested_top_k"] == result["actual_selected_size"] == 2
    for name in ("true_positives", "false_positives", "false_negatives", "true_negatives"):
        assert result["counts"][name] == 1
    for metric in result["metrics"].values():
        assert metric == {"value": 0.5, "numerator": 1, "denominator": 2, "unavailable_reason": None}
    assert result["coverage"]["prediction_universe"]["value"] == 1
    assert "precision_at_20" not in result and "recall" not in result


def test_top_k_larger_than_universe(metadata):
    result = evaluate_predictions(predictions(metadata), labels(metadata, [
        (1, "flooded"), (2, "non_flooded"), (3, "non_flooded"), (4, "non_flooded"),
    ]), metadata, 20)
    assert result["requested_top_k"] == 20 and result["actual_selected_size"] == 4
    assert result["metrics"]["precision_at_k"]["denominator"] == 4
    assert result["metrics"]["precision_at_k"]["value"] == 0.25


def test_selection_precedes_coverage_and_unknowns_are_not_negatives(metadata):
    result = evaluate_predictions(predictions(metadata), labels(metadata, [
        (2, "flooded"), (3, "non_flooded"), (4, "unknown"),
    ]), metadata, 2)
    assert result["selected_ward_ids"] == [1, 2]  # Do not replace unknown ward 1 by known ward 3.
    assert result["status"] == "partial"
    counts = result["counts"]
    assert counts["selected_unknown"] == 1
    assert counts["selected_flooded"] == 1 and counts["selected_non_flooded"] == 0
    assert counts["true_negatives"] == 1 and counts["false_positives"] == 0
    assert counts["missing_label_count"] == counts["explicit_unknown_count"] == 1
    assert result["metrics"]["precision_at_k"] == {
        "value": None, "numerator": 1, "denominator": 2,
        "unavailable_reason": "Selected wards include unknown status",
    }
    observed = result["metrics"]["precision_among_observed_selected"]
    assert observed["value"] == 1 and observed["denominator"] == 1
    assert result["coverage"]["prediction_universe"]["denominator"] == 4
    assert result["coverage"]["prediction_universe"]["value"] == 0.5


def test_absent_coverage_and_empty_predictions(metadata):
    result = evaluate_predictions(predictions(metadata), labels(metadata), metadata)
    assert result["status"] == "unavailable"
    assert result["counts"]["selected_unknown"] == 4
    assert all(metric["value"] is None and metric["unavailable_reason"]
               for metric in result["metrics"].values())
    empty = evaluate_predictions(predictions(metadata).iloc[:0], labels(metadata), metadata)
    assert empty["actual_selected_size"] == 0
    assert empty["coverage"]["prediction_universe"]["value"] is None
    assert empty["metrics"]["precision_at_k"]["denominator"] == 0


def test_no_positive_or_no_negative_denominators(metadata):
    negative = evaluate_predictions(predictions(metadata), labels(metadata, [(1, "non_flooded")]), metadata, 1)
    assert negative["metrics"]["recall_among_observed_flooded"]["value"] is None
    assert negative["metrics"]["precision_at_k"]["value"] == 0  # Defined observed zero.
    positive = evaluate_predictions(predictions(metadata), labels(metadata, [(1, "flooded")]), metadata, 1)
    assert positive["metrics"]["false_positive_rate_among_observed_non_flooded"]["value"] is None
    assert positive["metrics"]["recall_among_observed_flooded"]["value"] == 1
    assert positive["status"] == "partial"  # Full selected coverage is not full-universe coverage.


def test_unselected_positive_and_no_observed_selected(metadata):
    result = evaluate_predictions(predictions(metadata), labels(metadata, [(4, "flooded")]), metadata, 1)
    assert result["metrics"]["recall_among_observed_flooded"]["value"] == 0
    assert result["counts"]["false_negatives"] == 1
    assert result["metrics"]["precision_among_observed_selected"]["value"] is None


def test_outside_labels_are_explicit_exclusions(metadata):
    result = evaluate_predictions(predictions(metadata), labels(metadata, [(99, "flooded"), (2, "non_flooded")]), metadata)
    assert result["exclusions"] == [{"ward_id": 99, "label": "flooded",
                                       "reason": "label_outside_prediction_universe"}]
    assert result["counts"]["total_observed_flooded"] == 0
    assert result["metrics"]["false_positive_rate_among_observed_non_flooded"]["denominator"] == 1
    assert any("Out-of-universe" in warning for warning in result["warnings"])


@pytest.mark.parametrize("bad", [0, -1, 1.5, True, "2", None])
def test_bad_k(metadata, bad):
    with pytest.raises(ValueError, match="top_k"):
        evaluate_predictions(predictions(metadata), labels(metadata), metadata, bad)


@pytest.mark.parametrize("bad", [0, -1, "01", " 1", "1.0", 1.0, True, None, "Neighbourhood only"])
@pytest.mark.parametrize("which", ["predictions", "labels"])
def test_invalid_ids(metadata, bad, which):
    pred = predictions(metadata).astype({"ward_id": object})
    obs = labels(metadata, [(1, "flooded")]).astype({"ward_id": object})
    frame = pred if which == "predictions" else obs
    frame.loc[0, "ward_id"] = bad
    with pytest.raises(ValueError, match="ward_id"):
        evaluate_predictions(pred, obs, metadata)


@pytest.mark.parametrize("bad", [-0.1, 1.1, float("nan"), float("inf"), -float("inf"), None, True, "0.5"])
def test_invalid_scores(metadata, bad):
    pred = predictions(metadata).astype({"risk_score": object})
    pred.loc[0, "risk_score"] = bad
    with pytest.raises(ValueError, match="risk_score"):
        evaluate_predictions(pred, labels(metadata), metadata)


def test_duplicate_predictions_and_labels(metadata):
    pred = predictions(metadata)
    with pytest.raises(ValueError, match="Duplicate"):
        evaluate_predictions(pd.concat([pred, pred.iloc[:1]]), labels(metadata), metadata)
    for states in ([(1, "flooded"), (1, "flooded")], [(1, "flooded"), (1, "non_flooded")]):
        with pytest.raises(ValueError, match="Duplicate/conflicting"):
            evaluate_predictions(pred, labels(metadata, states), metadata)


@pytest.mark.parametrize("bad", ["wet", "", None, pd.NA])
def test_invalid_label_values(metadata, bad):
    obs = labels(metadata, [(1, "unknown")])
    obs.loc[0, "label"] = bad
    with pytest.raises(ValueError, match="label"):
        evaluate_predictions(predictions(metadata), obs, metadata)


@pytest.mark.parametrize("known", ["flooded", "non_flooded"])
@pytest.mark.parametrize("source", ["", None, "   "])
def test_known_labels_require_sources(metadata, known, source):
    obs = labels(metadata, [(1, known)])
    obs.loc[0, "source_ref"] = source
    with pytest.raises(ValueError, match="source_ref"):
        evaluate_predictions(predictions(metadata), obs, metadata)


@pytest.mark.parametrize("which", ["predictions", "labels"])
@pytest.mark.parametrize("field", ["event_id", "boundary_version"])
def test_alignment_mismatch(metadata, which, field):
    pred, obs = predictions(metadata), labels(metadata, [(1, "flooded")])
    (pred if which == "predictions" else obs).loc[0, field] = "different"
    with pytest.raises(ValueError, match=field):
        evaluate_predictions(pred, obs, metadata)


@pytest.mark.parametrize("field,bad", [
    ("event_id", ""), ("event_date", "not-a-date"), ("event_date", "2000-02-30"),
    ("boundary_source_ref", None), ("model_version", None), ("rainfall_mm", float("nan")),
    ("duration_hours", 0), ("is_template", True), ("sampling_notes", ""),
])
def test_metadata_validation(metadata, field, bad):
    metadata[field] = bad
    with pytest.raises(ValueError):
        evaluate_predictions(predictions(metadata), labels(metadata), metadata)


def test_optional_prediction_metadata_must_match(metadata):
    pred = predictions(metadata)
    pred["rainfall_mm"] = 250
    with pytest.raises(ValueError, match="rainfall_mm"):
        evaluate_predictions(pred, labels(metadata), metadata)


def test_positive_only_adapter_requires_metadata_and_sources(metadata):
    pred = predictions(metadata).drop(columns=["event_id", "boundary_version"])
    with pytest.raises(ValueError, match="metadata"):
        validate_against_historical(pred, [1])
    with pytest.raises(ValueError, match="source_refs"):
        validate_against_historical(pred, [1], event_metadata=metadata)
    with pytest.raises(ValueError, match="source_ref"):
        validate_against_historical(pred, [1], event_metadata=metadata, source_refs={})
    result = validate_against_historical(pred, [1], 2, event_metadata=metadata,
                                         source_refs={1: "test-fixture:artificial-positive"})
    assert result["counts"]["selected_unknown"] == 1
    assert result["counts"]["false_positives"] == result["counts"]["true_negatives"] == 0
    assert result["metrics"]["precision_at_k"]["value"] is None
    assert result["metrics"]["false_positive_rate_among_observed_non_flooded"]["value"] is None
    assert any("positive-only" in warning for warning in result["warnings"])


def test_reproducibility_and_input_immutability(metadata):
    pred, obs = predictions(metadata), labels(metadata, [(1, "flooded"), (2, "unknown")])
    original_pred, original_obs = pred.copy(deep=True), obs.copy(deep=True)
    first = evaluate_predictions(pred, obs, metadata)
    second = evaluate_predictions(pred.iloc[::-1], obs.iloc[::-1], metadata)
    assert first == second
    assert first["metadata_verification"] == "caller_supplied_not_independently_verified"
    assert first["event_metadata"]["model_version"] == "test-only"
    assert all(len(value) == 64 for key, value in first["reproducibility"].items() if key.endswith("sha256"))
    pd.testing.assert_frame_equal(pred, original_pred)
    pd.testing.assert_frame_equal(obs, original_obs)


def test_loading_missing_empty_and_round_trip(tmp_path, metadata, monkeypatch):
    path = tmp_path / "metrics.json"
    assert load_validation_metrics(path) == {
        "status": "unavailable", "status_reason": f"Metrics file missing: {path}"}
    path.write_text(" \n")
    assert load_validation_metrics(path) == {
        "status": "unavailable", "status_reason": f"Metrics file empty: {path}"}
    path.write_text("{}")
    assert load_validation_metrics(path) == {
        "status": "unavailable", "status_reason": f"Metrics object empty: {path}"}
    result = evaluate_predictions(predictions(metadata), labels(metadata), metadata)
    save_validation_metrics(result, path)
    assert load_validation_metrics(path) == result
    other_cwd = tmp_path / "other"
    other_cwd.mkdir()
    (other_cwd / "metrics.json").write_text('{"notes":"MOCK NUMBERS: artificial decoy"}')
    monkeypatch.chdir(other_cwd)
    assert VALIDATION_PATH.is_absolute()
    assert load_validation_metrics(path) == result  # Explicit absolute path ignores cwd decoy.


def test_loader_preserves_explicit_mock_without_certifying_it(tmp_path):
    path = tmp_path / "mock.json"
    payload = {"precision_at_20": 0.5, "notes": "MOCK NUMBERS: artificial test only"}
    path.write_text(json.dumps(payload))
    before = path.read_bytes()
    assert load_validation_metrics(path) == payload
    assert path.read_bytes() == before
    # Loader parses, but does not certify evidence or synthesize schema-2.0 status.
    assert "status" not in load_validation_metrics(path)


@pytest.mark.parametrize("payload", ["{bad", "[]", '{"a": NaN}', '{"a": Infinity}', '{"a": 1e999}', '{"a": 1, "a": 2}'])
def test_malformed_json_has_diagnostic(tmp_path, payload):
    path = tmp_path / "bad.json"
    path.write_text(payload)
    with pytest.raises(ValueError, match="Invalid JSON.*bad.json"):
        load_validation_metrics(path)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_strict_save_does_not_damage_existing_file(tmp_path, bad):
    path = tmp_path / "metrics.json"
    path.write_text('{"original": true}')
    with pytest.raises(ValueError):
        save_validation_metrics({"bad": bad}, path)
    assert path.read_text() == '{"original": true}'
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_failure_preserves_existing_file(tmp_path, monkeypatch):
    path = tmp_path / "metrics.json"
    path.write_text('{"original": true}')

    def fail_replace(*args):
        raise OSError("artificial replacement failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError):
        save_validation_metrics({"replacement": True}, path)
    assert path.read_text() == '{"original": true}'
    assert len(list(tmp_path.iterdir())) == 1


def test_cli_from_other_directory_and_raw_hashes(tmp_path, metadata):
    paths = {name: tmp_path / f"{name}.{suffix}" for name, suffix in (
        ("predictions", "csv"), ("labels", "csv"), ("metadata", "json"), ("output", "json"))}
    predictions(metadata).to_csv(paths["predictions"], index=False)
    labels(metadata, [(1, "flooded")]).to_csv(paths["labels"], index=False)
    paths["metadata"].write_text(json.dumps(metadata))
    canonical_before = VALIDATION_PATH.read_bytes()
    args = [value for name, path in paths.items() for value in (f"--{name}", str(path))]
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(root)}
    proc = subprocess.run([sys.executable, "-m", "model.validation", *args, "--top-k", "2"],
                          cwd=tmp_path, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    result = load_validation_metrics(paths["output"])
    assert result["selected_ward_ids"] == [1, 2]
    for name in ("predictions", "labels", "metadata"):
        assert result["reproducibility"]["input_files"][name]["sha256"] == hashlib.sha256(paths[name].read_bytes()).hexdigest()
    assert VALIDATION_PATH.read_bytes() == canonical_before
    args[args.index("--output") + 1] = str(VALIDATION_PATH)
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
    assert VALIDATION_PATH.read_bytes() == canonical_before


def test_templates_have_no_observations_and_are_not_evidence(metadata):
    root = Path(__file__).resolve().parents[1]
    template = root / "data/fixtures/validation_labels_TEMPLATE.csv"
    assert pd.read_csv(template).empty
    event = json.loads((root / "data/fixtures/validation_event_TEMPLATE.json").read_text())
    assert event["is_template"] is True
    with pytest.raises(ValueError, match="template"):
        evaluate_predictions(predictions(metadata), pd.read_csv(template), event)


def test_missing_and_duplicate_columns_rejected(metadata):
    pred = predictions(metadata)
    for field in ("ward_id", "risk_score", "event_id", "boundary_version"):
        with pytest.raises(ValueError, match="columns"):
            evaluate_predictions(pred.drop(columns=field), labels(metadata), metadata)
    with pytest.raises(ValueError, match="columns"):
        evaluate_predictions(pd.concat([pred, pred[["ward_id"]]], axis=1), labels(metadata), metadata)
    with pytest.raises(ValueError, match="columns"):
        evaluate_predictions(pred, labels(metadata).drop(columns="source_ref"), metadata)


def test_cli_duplicate_csv_headers_are_not_silently_mangled(tmp_path, capsys):
    pred, obs, event, output = [tmp_path / name for name in ("pred.csv", "labels.csv", "event.json", "out.json")]
    pred.write_text("ward_id,ward_id,risk_score,event_id,boundary_version\n")
    obs.write_text(",".join(LABEL_COLUMNS) + "\n")
    event.write_text("{}")
    with pytest.raises(SystemExit) as exc:
        main(["--predictions", str(pred), "--labels", str(obs), "--metadata", str(event),
              "--output", str(output)])
    assert exc.value.code == 2
    assert "Duplicate CSV" in capsys.readouterr().err
    assert not output.exists()


def test_boundary_and_event_required_even_for_outside_labels(metadata):
    obs = labels(metadata, [(99, "flooded")])
    obs.loc[0, "boundary_version"] = "unmatched-boundary"
    with pytest.raises(ValueError, match="boundary_version"):
        evaluate_predictions(predictions(metadata), obs, metadata)


def test_score_endpoints_and_numeric_id_tie_break(metadata):
    pred = predictions(metadata, ids=(10, 2, 100), scores=(1, 1, 0))
    result = evaluate_predictions(pred, labels(metadata), metadata, 1)
    assert result["selected_ward_ids"] == [2]  # Numeric, not lexical order.


def test_extreme_numeric_scores_and_non_object_save(metadata, tmp_path):
    pred = predictions(metadata).astype({"risk_score": object})
    pred.loc[0, "risk_score"] = 10 ** 400
    with pytest.raises(ValueError, match="risk_score"):
        evaluate_predictions(pred, labels(metadata), metadata)
    with pytest.raises(ValueError, match="object"):
        save_validation_metrics([], tmp_path / "invalid.json")
    assert not (tmp_path / "invalid.json").exists()


@pytest.mark.parametrize("which", ["predictions", "labels"])
@pytest.mark.parametrize("field,value", [
    ("rainfall_mm", "100"), ("duration_hours", "3.0"),
    ("rainfall_mm", "101"), ("duration_hours", "4"),
    ("rainfall_mm", ""), ("duration_hours", "bad"),
    ("rainfall_mm", "NaN"), ("duration_hours", "Infinity"),
    ("rainfall_mm", "501"), ("duration_hours", "0"),
])
def test_cli_optional_numeric_metadata(tmp_path, metadata, which, field, value, capsys):
    metadata.update(event_id="001", boundary_version="002", model_version="003")
    pred = predictions(metadata)
    obs = labels(metadata, [(1, "flooded")])
    obs["source_ref"] = "000123"
    for frame in (pred, obs):
        frame["rainfall_mm"] = "100"
        frame["duration_hours"] = "3"
        frame["model_version"] = "003"
        frame["external_identifier"] = "000456"
    (pred if which == "predictions" else obs)[field] = value
    paths = {name: tmp_path / name for name in ("predictions", "labels", "metadata", "output")}
    pred.to_csv(paths["predictions"], index=False)
    obs.to_csv(paths["labels"], index=False)
    paths["metadata"].write_text(json.dumps(metadata))
    args = [item for name, path in paths.items() for item in (f"--{name}", str(path))]
    if (field, value) in (("rainfall_mm", "100"), ("duration_hours", "3.0")):
        assert main(args) == 0
        # Canonical hashes also prove text identifiers/source refs survive CSV parsing.
        for frame in (pred, obs):
            frame["ward_id"] = frame["ward_id"].astype(str)
            for numeric in ("rainfall_mm", "duration_hours"):
                frame[numeric] = frame[numeric].astype(float)
        expected = evaluate_predictions(pred, obs, metadata)
        actual = load_validation_metrics(paths["output"])
        for key in ("canonical_predictions_sha256", "canonical_labels_sha256"):
            assert actual["reproducibility"][key] == expected["reproducibility"][key]
    else:
        with pytest.raises(SystemExit) as exc:
            main(args)
        assert exc.value.code == 2
        assert field in capsys.readouterr().err
        assert not paths["output"].exists()


def test_direct_optional_numeric_strings_still_rejected(metadata):
    obs = labels(metadata, [(1, "flooded")])
    obs["duration_hours"] = "3"
    with pytest.raises(ValueError, match="duration_hours"):
        evaluate_predictions(predictions(metadata), obs, metadata)
