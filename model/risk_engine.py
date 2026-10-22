"""Uncalibrated ward risk index; see docs/model_logic.md for the contract."""

from enum import Enum
from math import isfinite, sqrt
from numbers import Real

import numpy as np
import pandas as pd


class RiskLevel(str, Enum):  # noqa: UP042 - preserve existing enum string behaviour
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class DepthBand(str, Enum):  # noqa: UP042 - preserve existing enum string behaviour
    NONE = "none"
    LOW = "0-0.15m"
    MEDIUM = "0.15-0.5m"
    HIGH = "0.5-1.0m"
    VERY_HIGH = "1.0m+"


RISK_THRESHOLDS = {
    RiskLevel.VERY_LOW: (0.0, 0.2),
    RiskLevel.LOW: (0.2, 0.35),
    RiskLevel.MODERATE: (0.35, 0.55),
    RiskLevel.HIGH: (0.55, 0.75),
    RiskLevel.VERY_HIGH: (0.75, 1.0),
}

DEPTH_THRESHOLDS = {
    DepthBand.NONE: (0, 0.01),
    DepthBand.LOW: (0.01, 0.15),
    DepthBand.MEDIUM: (0.15, 0.5),
    DepthBand.HIGH: (0.5, 1.0),
    DepthBand.VERY_HIGH: (1.0, float('inf')),
}

WEIGHTS = {
    "elevation": 0.25,
    "slope": 0.15,
    "impervious": 0.25,
    "water_proximity": 0.15,
    "road_density": 0.10,
    "underpass": 0.10,
}


def normalize(value: float, min_val: float, max_val: float, invert: bool = False) -> float:
    value = _number("value", value)
    min_val = _number("min_val", min_val)
    max_val = _number("max_val", max_val)
    if max_val <= min_val:
        raise ValueError("max_val must exceed min_val")
    norm = (value - min_val) / (max_val - min_val)
    norm = np.clip(norm, 0, 1)
    return 1 - norm if invert else norm


def _number(name: str, value: object, low: float | None = None,
            high: float | None = None) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite numeric measurement")
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    if (low is not None and value < low) or (high is not None and value > high):
        raise ValueError(f"{name} must be in [{low}, {high}]")
    return value


def effective_inputs(row: pd.Series, rainfall_mm: float, builtup_increase: float = 0.0,
                     *, duration_hours: float = 3.0) -> tuple[dict[str, float], float, float]:
    """Validate original measurements and apply the scenario exactly once."""
    bounds = {
        "elevation_mean": (None, None),
        "slope_mean": (0, 90),
        "impervious_frac": (0, 1),
        "dist_to_water_m": (0, None),
        "road_density_km_per_sqkm": (0, None),
        "underpass_count": (0, None),
    }
    features = {name: _number(name, row.get(name), low, high)
                for name, (low, high) in bounds.items()}
    if not features["underpass_count"].is_integer():
        raise ValueError("underpass_count must be an integer count")
    rain = _number("rainfall_mm", rainfall_mm, 0, 500)
    duration = _number("duration_hours", duration_hours, 1, 24)
    increase = _number("builtup_increase", builtup_increase, 0, 100)
    features["impervious_frac"] = min(features["impervious_frac"] * (1 + increase / 100), 1)
    return features, rain, duration


def classify_risk(risk_score: float) -> RiskLevel:
    risk_score = _number("risk_score", risk_score, 0, 1)
    for level, (_, high) in RISK_THRESHOLDS.items():
        if risk_score < high:
            return level
    return RiskLevel.VERY_HIGH


def score_ward(row: pd.Series, rainfall_mm: float, builtup_increase: float = 0.0,
               *, duration_hours: float = 3.0) -> tuple[float, RiskLevel, DepthBand, int, list[str]]:
    features, rain, duration = effective_inputs(
        row, rainfall_mm, builtup_increase, duration_hours=duration_hours
    )
    elevation_mean = features["elevation_mean"]
    slope_mean = features["slope_mean"]
    impervious_frac = features["impervious_frac"]
    dist_to_water = features["dist_to_water_m"]
    road_density = features["road_density_km_per_sqkm"]
    underpass_count = features["underpass_count"]

    elevation_score = normalize(elevation_mean, 0, 50, invert=True)
    slope_score = normalize(slope_mean, 0, 15, invert=True)
    impervious_score = normalize(impervious_frac, 0, 1)
    water_proximity_score = normalize(dist_to_water, 0, 5000, invert=True)
    road_density_score = normalize(road_density, 0, 20)
    underpass_score = 1.0 if underpass_count > 0 else 0.0

    base_score = (
        WEIGHTS["elevation"] * elevation_score +
        WEIGHTS["slope"] * slope_score +
        WEIGHTS["impervious"] * impervious_score +
        WEIGHTS["water_proximity"] * water_proximity_score +
        WEIGHTS["road_density"] * road_density_score +
        WEIGHTS["underpass"] * underpass_score
    )

    # Bounded intensity sensitivity, anchored to the legacy three-hour scenario.
    duration_factor = min(1.5, max(0.5, sqrt(3.0 / duration)))
    rainfall_factor = min((rain / 200.0) * duration_factor, 1.5)
    risk_score = float(min(base_score * rainfall_factor, 1.0))
    risk_level = classify_risk(risk_score)

    # Unsupported legacy display proxies, retained for tuple/API compatibility only.
    estimated_depth_cm = risk_score * 150 * rainfall_factor
    depth_band = DepthBand.NONE
    for band, (low, high) in DEPTH_THRESHOLDS.items():
        if low <= estimated_depth_cm / 100 < high:
            depth_band = band
            break

    peak_window = max(1, int(3 * (1 + risk_score)))

    from model.reasons import _reasons_for_features

    reasons = _reasons_for_features(features, rain, duration, risk_score)

    return risk_score, risk_level, depth_band, peak_window, reasons


def generate_reasons(row: pd.Series, rainfall_mm: float, risk_score: float,
                     risk_level: RiskLevel, depth_band: DepthBand, *,
                     builtup_increase: float = 0.0, duration_hours: float = 3.0) -> list[str]:
    """Compatibility entry point; level/depth are retained but do not drive reasons."""
    from model.reasons import generate_reasons as explain

    return explain(row, rainfall_mm, risk_score, builtup_increase=builtup_increase,
                   duration_hours=duration_hours)


def score_wards(features: pd.DataFrame, rainfall_mm: float, builtup_increase: float = 0.0,
                *, duration_hours: float = 3.0) -> pd.DataFrame:
    _number("rainfall_mm", rainfall_mm, 0, 500)
    _number("builtup_increase", builtup_increase, 0, 100)
    _number("duration_hours", duration_hours, 1, 24)
    results = []
    for _, row in features.iterrows():
        risk_score, risk_level, depth_band, peak_window, reasons = score_ward(
            row, rainfall_mm, builtup_increase, duration_hours=duration_hours
        )
        results.append({
            "ward_id": int(row.ward_id),
            "ward_number": str(row.ward_number),
            "ward_name": str(row.ward_name),
            "risk_score": risk_score,
            "risk_level": risk_level.value,
            "depth_band": depth_band.value,
            "peak_window_hours": peak_window,
            "reasons": reasons,
        })

    df = pd.DataFrame(results, columns=[
        "ward_id", "ward_number", "ward_name", "risk_score", "risk_level",
        "depth_band", "peak_window_hours", "reasons",
    ])
    df = df.sort_values("risk_score", ascending=False).reset_index(drop=True)
    return df
