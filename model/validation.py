"""Evidence-aware top-k evaluation. See docs/validation.md; no historical facts are inferred."""

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import tempfile
from datetime import date
from io import BytesIO, StringIO
from numbers import Integral, Real
from pathlib import Path

import pandas as pd

VALIDATION_PATH = Path(__file__).resolve().parents[1] / "data/processed/validation_metrics.json"
LABEL_COLUMNS = ["ward_id", "label", "source_ref", "event_id", "boundary_version"]
METADATA_TEXT = [
    "event_id", "event_name", "event_date", "boundary_version", "boundary_source_ref",
    "observation_protocol", "sampling_notes", "model_id", "model_version",
]


def _text(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty traceable reference or identifier/text")
    if value != value.strip():
        raise ValueError(f"{name} must not contain surrounding whitespace")
    return value


def _ward_id(value) -> int:
    if isinstance(value, bool):
        raise ValueError("ward_id must be a canonical positive integer, not a name/boolean")
    if isinstance(value, Integral) and value > 0:
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value):
        return int(value)
    raise ValueError("ward_id must be a canonical positive integer; names/leading zeros are ambiguous")


def _number(value, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be finite numeric data")
    try:
        value = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name} must be finite numeric data") from exc
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite numeric data")
    if not low <= value <= high:
        raise ValueError(f"{name} must be in [{low}, {high}]")
    return float(value)


def _strict_json(value) -> str:
    return json.dumps(value, allow_nan=False, sort_keys=True, ensure_ascii=False, indent=2)


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _metadata(metadata: dict) -> dict:
    if not isinstance(metadata, dict) or metadata.get("is_template"):
        raise ValueError("Supply completed event metadata, not a template")
    result = dict(metadata)
    for name in METADATA_TEXT:
        _text(result.get(name), name)
    try:
        if date.fromisoformat(result["event_date"]).isoformat() != result["event_date"]:
            raise ValueError
    except ValueError as exc:
        raise ValueError("event_date must be an ISO YYYY-MM-DD date supplied by the caller") from exc
    result["rainfall_mm"] = _number(result.get("rainfall_mm"), "rainfall_mm", 0, 500)
    result["duration_hours"] = _number(result.get("duration_hours"), "duration_hours", 1, 24)
    _strict_json(result)
    return result


def _records(frame: pd.DataFrame, columns: list[str], metadata: dict, name: str) -> list[dict]:
    if not frame.columns.is_unique or not set(columns).issubset(frame.columns):
        raise ValueError(f"{name} requires unique columns including {columns}")
    optional = [field for field in METADATA_TEXT + ["rainfall_mm", "duration_hours"]
                if field in frame.columns and field not in columns]
    records = frame[columns + optional].to_dict("records")
    seen = set()
    for record in records:
        ward_id = _ward_id(record["ward_id"])
        if ward_id in seen:
            raise ValueError(f"Duplicate/conflicting {name} ward_id {ward_id}; resolve alignment first")
        seen.add(ward_id)
        record["ward_id"] = ward_id
        for field in ("event_id", "boundary_version"):
            if _text(record[field], f"{name}.{field}") != metadata[field]:
                raise ValueError(f"{name}.{field} does not match event metadata for ward {ward_id}")
        for field in optional:
            if field in ("rainfall_mm", "duration_hours"):
                low, high = (0, 500) if field == "rainfall_mm" else (1, 24)
                value = _number(record[field], field, low, high)
            else:
                value = _text(record[field], f"{name}.{field}")
            if value != metadata[field]:
                raise ValueError(f"{name}.{field} does not match event metadata for ward {ward_id}")
    return records


def _metric(numerator: int, denominator: int, reason: str | None = None) -> dict:
    if denominator == 0 and reason is None:
        reason = "No eligible observations in denominator"
    return {"value": None if reason else numerator / denominator,
            "numerator": numerator, "denominator": denominator, "unavailable_reason": reason}


def evaluate_predictions(predictions: pd.DataFrame, labels: pd.DataFrame,
                         event_metadata: dict, top_k: int = 20) -> dict:
    """Select on all predictions first, evaluate only explicitly observed labels.

    Evidence truth, sampling representativeness and boundary membership are not verified.
    Input event/boundary fields are mandatory caller attestations of alignment.
    """
    if isinstance(top_k, bool) or not isinstance(top_k, Integral) or top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    metadata = _metadata(event_metadata)
    ranked = _records(predictions, ["ward_id", "risk_score", "event_id", "boundary_version"],
                      metadata, "predictions")
    for record in ranked:
        record["risk_score"] = _number(record["risk_score"], "risk_score", 0, 1)
    ranked.sort(key=lambda row: (-row["risk_score"], row["ward_id"]))
    observations = _records(labels, LABEL_COLUMNS, metadata, "labels")
    for record in observations:
        if not isinstance(record["label"], str) or record["label"] not in ("flooded", "non_flooded", "unknown"):
            raise ValueError(f"Invalid label for ward {record['ward_id']}; use flooded/non_flooded/unknown")
        if record["label"] != "unknown":
            _text(record["source_ref"], f"source_ref for ward {record['ward_id']}")
        elif pd.isna(record["source_ref"]) or record["source_ref"] == "":
            record["source_ref"] = None
        else:
            _text(record["source_ref"], "source_ref")
    observations.sort(key=lambda row: row["ward_id"])
    universe = {row["ward_id"] for row in ranked}
    selected = [row["ward_id"] for row in ranked[:int(top_k)]]
    by_id = {row["ward_id"]: row["label"] for row in observations if row["ward_id"] in universe}
    positives = {ward for ward, label in by_id.items() if label == "flooded"}
    negatives = {ward for ward, label in by_id.items() if label == "non_flooded"}
    chosen = set(selected)
    tp, fp = len(chosen & positives), len(chosen & negatives)
    fn, tn = len(positives - chosen), len(negatives - chosen)
    n, k, known = len(ranked), len(selected), len(positives) + len(negatives)
    unknown_selected = k - tp - fp
    exclusions = [{"ward_id": row["ward_id"], "label": row["label"],
                   "reason": "label_outside_prediction_universe"}
                  for row in observations if row["ward_id"] not in universe]
    warnings = [
        "Caller-supplied evidence and boundary alignment are not independently verified.",
        "Observed-sample metrics do not establish representative city-wide accuracy; "
        "small or biased convenience samples may mislead.",
        "Top-k ranking selection is not the model's high-risk category.",
    ]
    if known < n:
        warnings.append("Observation coverage is incomplete; missing labels remain unknown.")
    if exclusions:
        warnings.append("Out-of-universe labels excluded from all metric denominators; review alignment.")
    status = "unavailable" if n == 0 or known == 0 else "partial" if known < n or exclusions else "evaluated"
    metrics = {
        "precision_at_k": _metric(tp, k, "Selected wards include unknown status" if unknown_selected else None),
        "precision_among_observed_selected": _metric(tp, tp + fp),
        "recall_among_observed_flooded": _metric(tp, len(positives)),
        "false_positive_rate_among_observed_non_flooded": _metric(fp, len(negatives)),
    }
    return {
        "schema_version": "2.0", "status": status,
        "status_reason": "No predictions or no known observations" if status == "unavailable" else None,
        "evaluation_type": "top_k_ranking", "event_metadata": metadata,
        "metadata_verification": "caller_supplied_not_independently_verified",
        "requested_top_k": int(top_k), "actual_selected_size": k, "prediction_count": n,
        "selected_ward_ids": selected,
        "counts": {"selected_flooded": tp, "selected_non_flooded": fp,
                   "selected_unknown": unknown_selected, "total_observed_flooded": len(positives),
                   "total_observed_non_flooded": len(negatives), "total_unknown": n - known,
                   "missing_label_count": n - len(by_id),
                   "explicit_unknown_count": sum(label == "unknown" for label in by_id.values()),
                   "true_positives": tp, "false_positives": fp,
                   "false_negatives": fn, "true_negatives": tn},
        "coverage": {"prediction_universe": _metric(known, n), "selected": _metric(tp + fp, k)},
        "metrics": metrics, "exclusions": exclusions, "warnings": warnings,
        "reproducibility": {
            "hash_algorithm": "sha256", "canonical_predictions_sha256": _hash(_strict_json(ranked).encode()),
            "canonical_labels_sha256": _hash(_strict_json(observations).encode()),
            "canonical_metadata_sha256": _hash(_strict_json(metadata).encode()),
            "evaluator_source_sha256": _hash(Path(__file__).read_bytes()),
            "python_version": platform.python_version(), "pandas_version": pd.__version__,
            "selection_rule": "risk_score descending, numeric ward_id ascending; select before labels",
        },
    }


def validate_against_historical(predictions: pd.DataFrame, actual_flooded_wards: list,
                                top_k: int = 20, *, event_metadata: dict | None = None,
                                source_refs: dict | None = None) -> dict:
    """Legacy positive-only adapter; unlisted wards are unknown, never negative."""
    metadata = _metadata(event_metadata)
    if source_refs is None:
        raise ValueError("Positive-only evaluation requires per-ward source_refs")
    predictions = predictions.copy()
    for field in ("event_id", "boundary_version"):
        if field not in predictions:
            predictions[field] = metadata[field]
    labels = pd.DataFrame([
        {"ward_id": ward, "label": "flooded", "source_ref": source_refs.get(ward),
         "event_id": metadata["event_id"], "boundary_version": metadata["boundary_version"]}
        for ward in actual_flooded_wards
    ], columns=LABEL_COLUMNS)
    result = evaluate_predictions(predictions, labels, metadata, top_k)
    result["warnings"].append("Legacy positive-only labels establish no observed negatives; "
                              "event/boundary alignment is caller-attested.")
    return result


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(text: str, path: Path) -> dict:
    def reject_constant(value):
        raise ValueError(f"Non-finite JSON constant: {value}")

    try:
        result = json.loads(text, parse_constant=reject_constant, object_pairs_hook=_json_object)
        if not isinstance(result, dict):
            raise ValueError("Expected a JSON object")
        _strict_json(result)  # Also rejects overflowed numeric literals such as 1e999.
        return result
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def load_validation_metrics(path: Path | str = VALIDATION_PATH) -> dict:
    path = Path(path)
    if not path.exists():
        return {"status": "unavailable", "status_reason": f"Metrics file missing: {path}"}
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {"status": "unavailable", "status_reason": f"Metrics file empty: {path}"}
    result = _read_json(text, path)
    return result or {"status": "unavailable", "status_reason": f"Metrics object empty: {path}"}


def save_validation_metrics(metrics: dict, path: Path | str = VALIDATION_PATH) -> None:
    """Atomically write strict JSON; callers must not publish artificial fixture results."""
    if not isinstance(metrics, dict):
        raise ValueError("Metrics must be a JSON object")
    payload = _strict_json(metrics) + "\n"  # Validate before touching the existing artifact.
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as out:
            temporary = Path(out.name)
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _read_csv(data: bytes, *, predictions: bool = False) -> pd.DataFrame:
    """Parse numeric CSV fields explicitly while preserving all identifier text."""
    frame = pd.read_csv(BytesIO(data), dtype=str, keep_default_na=False)
    bounds = {"rainfall_mm": (0, 500), "duration_hours": (1, 24)}
    if predictions:
        bounds["risk_score"] = (0, 1)
    for field, (low, high) in bounds.items():
        if field not in frame:
            continue
        values = []
        for cell in frame[field]:
            try:
                number = float(cell)
            except ValueError as exc:
                raise ValueError(f"{field} CSV value must be numeric, not {cell!r}") from exc
            values.append(_number(number, field, low, high))
        frame[field] = pd.Series(values, index=frame.index, dtype="float64")
    return frame


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("predictions", "labels", "metadata", "output"):
        parser.add_argument(f"--{option}", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        if args.output.resolve() == VALIDATION_PATH.resolve():
            raise ValueError("CLI cannot publish directly to data/processed/validation_metrics.json; "
                             "use a separate review artifact")
        inputs = {name: getattr(args, name).resolve() for name in ("predictions", "labels", "metadata")}
        if args.output.resolve() in inputs.values():
            raise ValueError("Output must not overwrite an input file")
        # Read once: raw hashes describe exactly the bytes parsed, not a later file revision.
        raw = {name: path.read_bytes() for name, path in inputs.items()}
        for name in ("predictions", "labels"):
            header = next(csv.reader(StringIO(raw[name].decode("utf-8"))), [])
            if len(header) != len(set(header)):
                raise ValueError(f"Duplicate CSV column names in {inputs[name]}")
        predictions = _read_csv(raw["predictions"], predictions=True)
        labels = _read_csv(raw["labels"])
        metadata = _read_json(raw["metadata"].decode("utf-8"), inputs["metadata"])
        result = evaluate_predictions(predictions, labels, metadata, args.top_k)
        result["reproducibility"]["input_files"] = {
            name: {"path": str(path), "sha256": _hash(raw[name])} for name, path in inputs.items()
        }
        save_validation_metrics(result, args.output)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Evaluation failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
