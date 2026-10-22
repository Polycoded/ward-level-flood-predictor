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
    rainfall_mm: float,
    max_results: int = 100
) -> List[Dict[str, Any]]:
    if len(roads_gdf) == 0:
        return []
    
    roads_utm = roads_gdf.to_crs("EPSG:32644") if roads_gdf.crs != "EPSG:32644" else roads_gdf
    wards_utm = wards_gdf.to_crs("EPSG:32644") if wards_gdf.crs != "EPSG:32644" else wards_gdf
    
    underpass_geoms = []
    if len(underpasses_gdf) > 0:
        underpasses_utm = underpasses_gdf.to_crs("EPSG:32644") if underpasses_gdf.crs != "EPSG:32644" else underpasses_gdf
        underpass_geoms = underpasses_utm.geometry.tolist()
    
    # Build spatial index for wards for fast intersection queries
    ward_sindex = wards_utm.sindex
    
    rainfall_factor = min(rainfall_mm / 150.0, 2.0)
    
    # Highway weights
    highway_weights = {
        "motorway": 1.0, "trunk": 0.9, "primary": 0.8,
        "secondary": 0.6, "tertiary": 0.5, "residential": 0.4, "service": 0.3
    }
    
    # Pre-compute ward risk factors
    ward_data = []
    for _, ward in wards_utm.iterrows():
        ward_data.append({
            "geometry": ward.geometry,
            "elevation_mean": ward.get("elevation_mean", 10.0),
            "slope_mean": ward.get("slope_mean", 2.0),
            "impervious_frac": ward.get("impervious_frac", 0.5),
            "dist_to_water": ward.get("dist_to_water_m", 1000.0),
        })
    
    results = []
    
    # Limit processing to major roads first for performance
    # Sort by highway importance to process most critical first
    highway_priority = {
        "motorway": 0, "trunk": 1, "primary": 2, 
        "secondary": 3, "tertiary": 4, "residential": 5, "service": 6, "unclassified": 7
    }
    roads_utm = roads_utm.copy()
    roads_utm["_priority"] = roads_utm["highway_type"].map(highway_priority).fillna(8)
    roads_utm = roads_utm.sort_values("_priority")
    
    # Only process up to 5000 roads for performance (covers all major + sample of minor)
    MAX_ROADS_PROCESS = 5000
    roads_to_process = roads_utm.head(MAX_ROADS_PROCESS)
    
    for idx, road in roads_to_process.iterrows():
        road_geom = road.geometry
        if road_geom.is_empty:
            continue
        
        highway_type = road.get("highway_type", "road")
        is_tunnel = road.get("is_tunnel", False)
        layer = road.get("layer", 0)
        
        # Fast spatial query using sindex
        possible_wards = list(ward_sindex.intersection(road_geom.bounds))
        if not possible_wards:
            continue
        
        # Find actual intersecting ward
        ward_idx = None
        for wi in possible_wards:
            if wards_utm.iloc[wi].geometry.intersects(road_geom):
                ward_idx = wi
                break
        
        if ward_idx is None:
            continue
        
        ward_info = ward_data[ward_idx]
        
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
        
        elevation_risk = max(0, 1 - ward_info["elevation_mean"] / 20)
        slope_risk = max(0, 1 - ward_info["slope_mean"] / 10)
        impervious_risk = ward_info["impervious_frac"]
        water_risk = max(0, 1 - ward_info["dist_to_water"] / 3000)
        
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
        
        # Only convert geometry for results we'll actually return
        road_wgs84 = gpd.GeoSeries([road_geom], crs="EPSG:32644").to_crs("EPSG:4326").iloc[0]
        
        road_name = road.get("name")
        if pd.isna(road_name):
            road_name = f"Road {idx}"
        
        results.append({
            "road_id": str(idx),
            "name": road_name,
            "highway_type": highway_type,
            "risk_score": float(risk_score),
            "risk_level": risk_level,
            "is_underpass": bool(is_underpass),
            "flood_depth_estimate_m": float(depth_estimate / 100),
            "geometry": road_wgs84.__geo_interface__
        })
    
    results.sort(key=lambda x: x["risk_score"], reverse=True)
    return results[:max_results]