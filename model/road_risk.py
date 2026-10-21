import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point, LineString
from shapely.ops import nearest_points
from typing import List, Dict, Any
import structlog

logger = structlog.get_logger()

RISK_THRESHOLDS = {
    "very_low": (0.0, 0.2),
    "low": (0.2, 0.35),
    "moderate": (0.35, 0.55),
    "high": (0.55, 0.75),
    "very_high": (0.75, 1.0),
}


def get_risk_level(score: float) -> str:
    for level, (low, high) in RISK_THRESHOLDS.items():
        if low <= score < high:
            return level
    return "very_high"


def score_roads(
    roads_gdf: gpd.GeoDataFrame,
    underpasses_gdf: gpd.GeoDataFrame,
    wards_gdf: gpd.GeoDataFrame,
    rainfall_mm: float
) -> List[Dict[str, Any]]:
    if len(roads_gdf) == 0:
        return []
    
    roads_utm = roads_gdf.to_crs("EPSG:32644") if roads_gdf.crs != "EPSG:32644" else roads_gdf
    wards_utm = wards_gdf.to_crs("EPSG:32644") if wards_gdf.crs != "EPSG:32644" else wards_gdf
    
    underpass_geoms = []
    if len(underpasses_gdf) > 0:
        underpasses_utm = underpasses_gdf.to_crs("EPSG:32644") if underpasses_gdf.crs != "EPSG:32644" else underpasses_gdf
        underpass_geoms = underpasses_utm.geometry.tolist()
    
    results = []
    rainfall_factor = min(rainfall_mm / 150.0, 2.0)
    
    for idx, road in roads_utm.iterrows():
        road_geom = road.geometry
        if road_geom.is_empty:
            continue
        
        highway_type = road.get("highway_type", "road")
        is_tunnel = road.get("is_tunnel", False)
        layer = road.get("layer", 0)
        
        ward_matches = wards_utm[wards_utm.intersects(road_geom)]
        if len(ward_matches) == 0:
            continue
        
        ward = ward_matches.iloc[0]
        elevation_mean = ward.get("elevation_mean", 10.0)
        slope_mean = ward.get("slope_mean", 2.0)
        impervious_frac = ward.get("impervious_frac", 0.5)
        dist_to_water = ward.get("dist_to_water_m", 1000.0)
        
        highway_weights = {
            "motorway": 1.0, "trunk": 0.9, "primary": 0.8,
            "secondary": 0.6, "tertiary": 0.5, "residential": 0.4, "service": 0.3
        }
        highway_weight = highway_weights.get(highway_type, 0.5)
        
        is_underpass = is_tunnel or layer < 0
        
        if is_underpass:
            underpass_proximity = 0.0
        else:
            if underpass_geoms:
                min_dist = min(road_geom.distance(up) for up in underpass_geoms)
                underpass_proximity = max(0, 1 - min_dist / 200)
            else:
                underpass_proximity = 0.0
        
        elevation_risk = max(0, 1 - elevation_mean / 20)
        slope_risk = max(0, 1 - slope_mean / 10)
        impervious_risk = impervious_frac
        water_risk = max(0, 1 - dist_to_water / 3000)
        
        base_score = (
            0.25 * elevation_risk +
            0.15 * slope_risk +
            0.25 * impervious_risk +
            0.15 * water_risk +
            0.10 * highway_weight +
            0.10 * underpass_proximity
        )
        
        risk_score = min(base_score * rainfall_factor, 1.0)
        
        if is_underpass:
            risk_score = min(risk_score * 1.5, 1.0)
        
        risk_level = get_risk_level(risk_score)
        
        depth_estimate = risk_score * 100 * rainfall_factor
        if is_underpass:
            depth_estimate = min(depth_estimate * 2, 300)
        
        road_wgs84 = gpd.GeoSeries([road_geom], crs="EPSG:32644").to_crs("EPSG:4326").iloc[0]
        
        results.append({
            "road_id": str(idx),
            "name": road.get("name", f"Road {idx}"),
            "highway_type": highway_type,
            "risk_score": float(risk_score),
            "risk_level": risk_level,
            "is_underpass": bool(is_underpass),
            "flood_depth_estimate_m": float(depth_estimate / 100),
            "geometry": road_wgs84.__geo_interface__
        })
    
    results.sort(key=lambda x: x["risk_score"], reverse=True)
    return results[:100]