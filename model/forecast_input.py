"""Exact Open-Meteo hourly aggregation; no networking or missing-to-zero conversion.

https://open-meteo.com/en/docs, Hourly Parameter Definition, inspected 2026-10-23:
precipitation is a preceding-hour SUM. Label t represents [t-1h,t), not [t,t+1h).
Only explicit UTC offset timestamps (or caller-adapted UTC labels) are accepted here.
generationtime_ms is processing latency, NOT model issue time.
"""
from datetime import timedelta

from model.alert_contract import instant, iso, number, scenario_input, text


def validate_forecast(value: dict, *, now: str) -> dict:
    """Recheck normalized forecast freshness at decision time, not just retrieval time."""
    result = scenario_input(value)
    if result["kind"] != "forecast" or result.get("timezone") != "UTC" or result.get("timestamp_semantics") != "preceding_hour_sum":
        raise ValueError("Normalized UTC preceding-hour forecast required")
    issued, retrieved, current = map(instant, (result.get("issued_at"), result.get("retrieved_at"), now))
    max_age = number(result.get("max_age_seconds"), "max_age_seconds", 0, 604800)
    retrieval_age = number(result.get("max_retrieval_age_seconds"), "max_retrieval_age_seconds", 0, 604800)
    if not issued <= retrieved <= current or (current - issued).total_seconds() > max_age or (current - retrieved).total_seconds() > retrieval_age:
        raise ValueError("Stale or inconsistent forecast timestamps")
    start, end = instant(result["interval_start"]), instant(result["interval_end"])
    if start.minute or start.second or start.microsecond or end.minute or end.second or end.microsecond:
        raise ValueError("Forecast window must align with complete UTC hours")
    if not instant(result.get("valid_from")) <= start < end <= instant(result.get("valid_until")) or start < current:
        raise ValueError("Forecast window outside validity or already started")
    series = result.get("series_mm")
    if not isinstance(series, list) or len(series) != result["duration_hours"]:
        raise ValueError("Complete hourly series required")
    values = [number(v, "precipitation_mm", 0, 500) for v in series]
    if sum(values) != result["rainfall_mm"]:
        raise ValueError("Forecast total differs from complete hourly series")
    return result


def aggregate_forecast(records: list[dict], *, interval_start: str, interval_end: str,
                       issued_at: str, retrieved_at: str, valid_from: str, valid_until: str,
                       now: str, source: str, max_age_seconds: float,
                       max_retrieval_age_seconds: float) -> dict:
    """records=[{interval_end: offset ISO8601, precipitation_mm: finite number}]."""
    text(source, "source")
    start, end = instant(interval_start), instant(interval_end)
    issued, retrieved, current = map(instant, (issued_at, retrieved_at, now))
    valid_start, valid_end = instant(valid_from), instant(valid_until)
    age = number(max_age_seconds, "max_age_seconds", 0, 604800)
    retrieval_age = number(max_retrieval_age_seconds, "max_retrieval_age_seconds", 0, 604800)
    if not issued <= retrieved <= current or not 0 <= (current - issued).total_seconds() <= age:
        raise ValueError("Forecast issue/retrieval ordering or freshness failed")
    if (current - retrieved).total_seconds() > retrieval_age:
        raise ValueError("Stale retrieval")
    duration = (end - start).total_seconds() / 3600
    number(duration, "duration_hours", 1, 24)
    if not duration.is_integer() or start.minute or start.second or start.microsecond:
        raise ValueError("Requested interval must align with complete UTC hours; no splitting")
    if not valid_start <= start < end <= valid_end or start < current:
        raise ValueError("Requested window outside validity or already started")
    if not isinstance(records, list) or not records:
        raise ValueError("Hourly coverage required")
    by_end = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Hourly record must be an object")
        stamp = instant(record.get("interval_end"))
        if stamp.minute or stamp.second or stamp.microsecond or stamp in by_end:
            raise ValueError("Duplicate or non-hourly interval")
        by_end[stamp] = number(record.get("precipitation_mm"), "precipitation_mm", 0, 500)
    requested = [start + timedelta(hours=i) for i in range(1, int(duration) + 1)]
    if any(stamp not in by_end for stamp in requested):
        raise ValueError("Incomplete matching hourly coverage")
    series = [by_end[stamp] for stamp in requested]
    return validate_forecast({"kind": "forecast", "source": source, "timezone": "UTC",
        "rainfall_mm": sum(series), "duration_hours": duration,
        "interval_start": iso(start), "interval_end": iso(end), "issued_at": iso(issued),
        "retrieved_at": iso(retrieved), "valid_from": iso(valid_start), "valid_until": iso(valid_end),
        "max_age_seconds": age, "max_retrieval_age_seconds": retrieval_age,
        "timestamp_semantics": "preceding_hour_sum", "series_mm": series}, now=now)
