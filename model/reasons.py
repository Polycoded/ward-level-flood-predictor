from typing import List
import pandas as pd


def generate_reasons(row: pd.Series, rainfall_mm: float, risk_score: float) -> List[str]:
    reasons = []
    
    elevation_mean = row.get("elevation_mean", 10.0)
    if elevation_mean < 5.0:
        reasons.append(f"Low mean elevation ({elevation_mean:.1f}m) increases flood susceptibility")
    
    slope_mean = row.get("slope_mean", 2.0)
    if slope_mean < 1.5:
        reasons.append(f"Very flat terrain (mean slope {slope_mean:.1f}°) limits natural drainage")
    
    impervious_frac = row.get("impervious_frac", 0.5)
    if impervious_frac > 0.6:
        reasons.append(f"High impervious surface fraction ({impervious_frac:.0%}) reduces infiltration capacity")
    
    dist_to_water = row.get("dist_to_water_m", 1000.0)
    if dist_to_water < 500:
        reasons.append(f"Proximity to water body ({dist_to_water:.0f}m) creates backflow risk")
    
    underpass_count = row.get("underpass_count", 0)
    if underpass_count > 0:
        reasons.append(f"Contains {underpass_count} underpass(es) - critical flood risk points")
    
    road_density = row.get("road_density_km_per_sqkm", 5.0)
    if road_density > 15:
        reasons.append(f"High road density ({road_density:.1f} km/km²) indicates dense urbanization")
    
    vegetation_frac = row.get("vegetation_frac", 0.2)
    if vegetation_frac < 0.1:
        reasons.append(f"Low vegetation cover ({vegetation_frac:.0%}) reduces natural absorption")
    
    if rainfall_mm > 150:
        reasons.append(f"High rainfall forecast ({rainfall_mm:.0f}mm) likely exceeds drainage design capacity")
    elif rainfall_mm > 75:
        reasons.append(f"Moderate rainfall forecast ({rainfall_mm:.0f}mm) may overwhelm low-lying areas")
    
    if not reasons:
        reasons.append("No single dominant risk factor; composite score drives assessment")
    
    return reasons[:5]