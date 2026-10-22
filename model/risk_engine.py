from typing import Tuple, List
import pandas as pd
import numpy as np
from enum import Enum


class RiskLevel(str, Enum):
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class DepthBand(str, Enum):
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
    if max_val == min_val:
        return 0.5
    norm = (value - min_val) / (max_val - min_val)
    norm = np.clip(norm, 0, 1)
    return 1 - norm if invert else norm


def score_ward(row: pd.Series, rainfall_mm: float, builtup_increase: float = 0.0) -> Tuple[float, RiskLevel, DepthBand, int, List[str]]:
    elevation_mean = row.get("elevation_mean", 10.0)
    slope_mean = row.get("slope_mean", 2.0)
    impervious_frac = min(row.get("impervious_frac", 0.5) * (1 + builtup_increase / 100), 1.0)
    water_frac = row.get("water_frac", 0.1)
    dist_to_water = row.get("dist_to_water_m", 1000.0)
    road_density = row.get("road_density_km_per_sqkm", 5.0)
    underpass_count = row.get("underpass_count", 0)
    
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
    
    rainfall_factor = min(rainfall_mm / 200.0, 1.5)
    risk_score = min(base_score * rainfall_factor, 1.0)
    
    risk_level = RiskLevel.VERY_LOW
    for level, (low, high) in RISK_THRESHOLDS.items():
        if low <= risk_score < high:
            risk_level = level
            break
    
    estimated_depth_cm = risk_score * 150 * rainfall_factor
    depth_band = DepthBand.NONE
    for band, (low, high) in DEPTH_THRESHOLDS.items():
        if low <= estimated_depth_cm / 100 < high:
            depth_band = band
            break
    
    peak_window = max(1, int(3 * (1 + risk_score)))
    
    reasons = generate_reasons(row, rainfall_mm, risk_score, risk_level, depth_band)
    
    return risk_score, risk_level, depth_band, peak_window, reasons


def generate_reasons(row: pd.Series, rainfall_mm: float, risk_score: float, 
                     risk_level: RiskLevel, depth_band: DepthBand) -> List[str]:
    reasons = []
    
    elevation_mean = row.get("elevation_mean", 10.0)
    if elevation_mean < 5.0:
        reasons.append(f"Low mean elevation ({elevation_mean:.1f}m) increases flood susceptibility")
    
    slope_mean = row.get("slope_mean", 2.0)
    if slope_mean < 1.5:
        reasons.append(f"Very flat terrain (mean slope {slope_mean:.1f}°) limits drainage")
    
    impervious_frac = row.get("impervious_frac", 0.5)
    if impervious_frac > 0.6:
        reasons.append(f"High impervious surface fraction ({impervious_frac:.0%}) reduces infiltration")
    
    dist_to_water = row.get("dist_to_water_m", 1000.0)
    if dist_to_water < 500:
        reasons.append(f"Close to water body ({dist_to_water:.0f}m) - backflow risk")
    
    underpass_count = row.get("underpass_count", 0)
    if underpass_count > 0:
        reasons.append(f"Contains {underpass_count} underpass(es) - high flood risk")
    
    road_density = row.get("road_density_km_per_sqkm", 5.0)
    if road_density > 15:
        reasons.append(f"High road density ({road_density:.1f} km/km²) indicates dense urbanization")
    
    if rainfall_mm > 150:
        reasons.append(f"High rainfall forecast ({rainfall_mm:.0f}mm) exceeds drainage capacity")
    elif rainfall_mm > 75:
        reasons.append(f"Moderate rainfall forecast ({rainfall_mm:.0f}mm) may overwhelm low-lying areas")
    
    if not reasons:
        reasons.append("No single dominant risk factor; composite score drives assessment")
    
    return reasons


def score_wards(features: pd.DataFrame, rainfall_mm: float, builtup_increase: float = 0.0) -> pd.DataFrame:
    results = []
    for _, row in features.iterrows():
        risk_score, risk_level, depth_band, peak_window, reasons = score_ward(row, rainfall_mm, builtup_increase)
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
    
    df = pd.DataFrame(results)
    df = df.sort_values("risk_score", ascending=False).reset_index(drop=True)
    return df