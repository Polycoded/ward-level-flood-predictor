"""Small strict JSON/time boundary shared by Exercise policy adapters."""
import hashlib
import json
import math
from datetime import UTC, datetime
from numbers import Real


def text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{name} must be nonempty trimmed text")
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ValueError(f"{name} contains control characters")
    return value


def number(value: object, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be numeric, not boolean/string")
    result = float(value)
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f"{name} must be finite in [{low}, {high}]")
    return result


def integer(value: object, name: str, low: int = 0) -> int:
    if type(value) is not int or value < low:
        raise ValueError(f"{name} must be an integer >= {low}")
    return value


def instant(value: str) -> datetime:
    text(value, "timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Expected ISO8601 timestamp with explicit UTC offset") from exc
    if "T" not in value or parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Ambiguous timestamp: explicit offset required")
    return parsed.astimezone(UTC)


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                     separators=(",", ":")).encode()).hexdigest()


def scenario_input(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("Rainfall input must be an object")
    if value.get("kind") not in {"manual_scenario", "forecast", "historical_observation"}:
        raise ValueError("Explicit rainfall kind required")
    result = dict(value)
    result["rainfall_mm"] = number(value.get("rainfall_mm"), "rainfall_mm", 0, 500)
    result["duration_hours"] = number(value.get("duration_hours"), "duration_hours", 1, 24)
    text(value.get("source"), "source")
    start, end = instant(value.get("interval_start")), instant(value.get("interval_end"))
    if (end - start).total_seconds() != result["duration_hours"] * 3600:
        raise ValueError("Exact interval does not match duration")
    result.update(interval_start=iso(start), interval_end=iso(end))
    digest(result)  # Reject non-JSON or nonfinite extra metadata.
    return result
