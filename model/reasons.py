"""Shared explanations of the uncalibrated index, not physical flood predictions."""

import pandas as pd


def _reasons_for_features(features: dict[str, float], rainfall_mm: float,
                          duration_hours: float, risk_score: float) -> list[str]:
    reasons = []
    elevation = features["elevation_mean"]
    if elevation < 5:
        reasons.append(f"Low mean elevation ({elevation:.1f} m) raises the elevation component")
    slope = features["slope_mean"]
    if slope < 1.5:
        reasons.append(f"Flat terrain (mean slope {slope:.1f}°) raises the slope component")
    impervious = features["impervious_frac"]
    if impervious > 0.6:
        reasons.append(f"High effective impervious fraction ({impervious:.1%}) raises the impervious component")
    distance = features["dist_to_water_m"]
    if distance < 500:
        reasons.append(f"Water proximity ({distance:.0f} m) raises the proximity component; backflow is not modelled")
    count = features["underpass_count"]
    if count > 0:
        reasons.append(f"Mapped underpass count ({count:.0f}) activates the underpass component")
    roads = features["road_density_km_per_sqkm"]
    if roads > 15:
        reasons.append(f"High road density ({roads:.1f} km/km²) raises the road-density component")
    reasons.append(
        f"Rainfall input: {rainfall_mm:g} mm over {duration_hours:g} h "
        f"(mean intensity {rainfall_mm / duration_hours:.1f} mm/h); "
        "a bounded duration heuristic scales the index"
    )
    reasons.append(f"Uncalibrated risk index: {risk_score:.3f}; not a flood probability, depth or peak-time prediction")
    return reasons


def generate_reasons(row: pd.Series, rainfall_mm: float, risk_score: float, *,
                     builtup_increase: float = 0.0, duration_hours: float = 3.0) -> list[str]:
    """Explain original features with the same scenario arguments as score_ward.

    risk_score is the caller's computed index, retained for compatibility.
    """
    from model.risk_engine import _number, effective_inputs

    features, rain, duration = effective_inputs(
        row, rainfall_mm, builtup_increase, duration_hours=duration_hours
    )
    score = _number("risk_score", risk_score, 0, 1)
    return _reasons_for_features(features, rain, duration, score)
