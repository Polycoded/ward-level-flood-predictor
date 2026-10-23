"""Presentation boundary for evaluator output; never certifies evidence truth."""

import json
import math
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from api.schemas import ValidationMetrics
from model.validation import METADATA_TEXT, load_validation_metrics

METRICS = {
    "precision_at_k", "precision_among_observed_selected",
    "recall_among_observed_flooded", "false_positive_rate_among_observed_non_flooded",
}
# Absolute tolerance only: allow JSON floating-point roundoff, not rounded percentages.
METRIC_ABS_TOLERANCE = 1e-12


def unavailable(reason: str) -> ValidationMetrics:
    return ValidationMetrics(status="unavailable", status_reason=reason)


def validation_status(path: Path) -> ValidationMetrics:
    try:
        payload = load_validation_metrics(path)
        if "mock" in json.dumps(payload).lower():
            return unavailable("Mock metrics are demonstration placeholders, not accuracy evidence.")
        if payload.get("schema_version") != "2.0":
            return unavailable(payload.get("status_reason") or
                               "Unsupported legacy metrics: reviewed schema-2 evaluator output is required.")
        result = ValidationMetrics.model_validate(payload)
        if not result.metrics or not METRICS.issubset(result.metrics):
            raise ValueError("Missing schema-2 metrics")
        if not result.coverage or not {"prediction_universe", "selected"}.issubset(result.coverage):
            raise ValueError("Missing observation coverage")
        for metric in (*result.metrics.values(), *result.coverage.values()):
            if metric.numerator > metric.denominator:
                raise ValueError("Metric numerator exceeds denominator")
            if metric.value is not None and not math.isclose(
                metric.value, metric.numerator / metric.denominator,
                rel_tol=0, abs_tol=METRIC_ABS_TOLERANCE,
            ):
                raise ValueError("Metric value disagrees with numerator/denominator")
        for key in ("counts", "event_metadata", "reproducibility"):
            if not isinstance(payload.get(key), dict):
                raise ValueError(f"Missing schema-2 {key}")
        metadata = payload["event_metadata"]
        if not all(isinstance(metadata.get(key), str) and metadata[key].strip() for key in METADATA_TEXT):
            raise ValueError("Incomplete event metadata")
        date.fromisoformat(metadata["event_date"])
        for key, low, high in (("rainfall_mm", 0, 500), ("duration_hours", 1, 24)):
            value = metadata.get(key)
            if type(value) not in (int, float) or not low <= value <= high or not math.isfinite(value):
                raise ValueError(f"Invalid event {key}")
        if payload.get("evaluation_type") != "top_k_ranking" or payload.get("metadata_verification") != "caller_supplied_not_independently_verified":
            raise ValueError("Unsupported evaluation contract")
        if not isinstance(payload.get("warnings"), list) or not isinstance(payload.get("exclusions"), list):
            raise ValueError("Missing evaluator warnings or exclusions")
        counts = payload["counts"]
        required_counts = {"selected_flooded", "selected_non_flooded", "selected_unknown",
                           "total_observed_flooded", "total_observed_non_flooded", "total_unknown",
                           "missing_label_count", "explicit_unknown_count", "true_positives",
                           "false_positives", "false_negatives", "true_negatives"}
        if not required_counts.issubset(counts) or any(type(value) is not int or value < 0 for value in counts.values()):
            raise ValueError("Invalid evaluator counts")
        selected = payload.get("selected_ward_ids")
        if not isinstance(selected, list) or any(type(ward) is not int or ward <= 0 for ward in selected):
            raise ValueError("Invalid selected ward identities")
        for key in ("prediction_count", "actual_selected_size", "requested_top_k"):
            if type(payload.get(key)) is not int or payload[key] < 0:
                raise ValueError(f"Invalid schema-2 {key}")
        if payload["requested_top_k"] == 0:
            raise ValueError("requested_top_k must be positive")
        if len(set(selected)) != len(selected) or len(selected) != payload["actual_selected_size"]:
            raise ValueError("Selected IDs must be unique and match actual_selected_size")
        if payload["actual_selected_size"] != min(payload["requested_top_k"], payload["prediction_count"]):
            raise ValueError("Selected size disagrees with top-k/prediction count")
        if result.status == "unavailable" and not result.status_reason:
            raise ValueError("Unavailable output requires a reason")
        return result
    except (OSError, UnicodeError, ValueError, ValidationError) as exc:
        return unavailable(f"Metrics unavailable: invalid or unreadable evaluator output ({exc}).")
