from enum import Enum


class DepthBand(str, Enum):
    NONE = "none"
    LOW = "0-0.15m"
    MEDIUM = "0.15-0.5m"
    HIGH = "0.5-1.0m"
    VERY_HIGH = "1.0m+"


DEPTH_THRESHOLDS_M = {
    DepthBand.NONE: (0, 0.01),
    DepthBand.LOW: (0.01, 0.15),
    DepthBand.MEDIUM: (0.15, 0.5),
    DepthBand.HIGH: (0.5, 1.0),
    DepthBand.VERY_HIGH: (1.0, float('inf')),
}


def get_depth_band(depth_m: float) -> DepthBand:
    for band, (low, high) in DEPTH_THRESHOLDS_M.items():
        if low <= depth_m < high:
            return band
    return DepthBand.VERY_HIGH


def estimate_depth(risk_score: float, rainfall_mm: float) -> float:
    base_depth_cm = risk_score * 150
    rainfall_factor = min(rainfall_mm / 100.0, 2.0)
    return (base_depth_cm * rainfall_factor) / 100