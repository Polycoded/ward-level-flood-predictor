import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point, LineString
from typing import List, Dict, Any, Optional
import structlog

logger = structlog.get_logger()

DEFAULT_SHELTERS = [
    {"shelter_id": 1, "name": "Chennai Corporation Community Hall - Zone 1", "latitude": 13.0827, "longitude": 80.2707, "capacity": 500},
    {"shelter_id": 2, "name": "Chennai Corporation Community Hall - Zone 2", "latitude": 13.0604, "longitude": 80.2495, "capacity": 400},
    {"shelter_id": 3, "name": "Chennai Corporation Community Hall - Zone 3", "latitude": 13.0333, "longitude": 80.2615, "capacity": 350},
    {"shelter_id": 4, "name": "Ripon Building Emergency Shelter", "latitude": 13.0840, "longitude": 80.2785, "capacity": 1000},
    {"shelter_id": 5, "name": "Koyambedu Marriage Hall", "latitude": 13.0720, "longitude": 80.2005, "capacity": 600},
    {"shelter_id": 6, "name": "Tambaram Taluk Office Shelter", "latitude": 12.9249, "longitude": 80.1246, "capacity": 300},
    {"shelter_id": 7, "name": "Adyar Community Center", "latitude": 13.0067, "longitude": 80.2206, "capacity": 250},
    {"shelter_id": 8, "name": "Anna Nagar Community Hall", "latitude": 13.0850, "longitude": 80.2101, "capacity": 450},
    {"shelter_id": 9, "name": "T. Nagar Community Hall", "latitude": 13.0418, "longitude": 80.2341, "capacity": 400},
    {"shelter_id": 10, "name": "Velachery Community Center", "latitude": 12.9751, "longitude": 80.2201, "capacity": 300},
]


def create_default_shelters() -> gpd.GeoDataFrame:
    shelters = gpd.GeoDataFrame(DEFAULT_SHELTERS, crs="EPSG:4326")
    shelters["geometry"] = shelters.apply(lambda r: Point(r.longitude, r.latitude), axis=1)
    return shelters


def find_nearest_shelters(
    latitude: float,
    longitude: float,
    shelters_gdf: gpd.GeoDataFrame,
    max_distance_km: float = 5.0,
    max_results: int = 5
) -> List[Dict[str, Any]]:
    if len(shelters_gdf) == 0:
        shelters_gdf = create_default_shelters()
    
    user_point = Point(longitude, latitude)
    shelters_wgs84 = shelters_gdf.to_crs("EPSG:4326") if shelters_gdf.crs != "EPSG:4326" else shelters_gdf
    
    distances = shelters_wgs84.geometry.apply(lambda geom: user_point.distance(geom) * 111.32)
    shelters_wgs84 = shelters_wgs84.copy()
    shelters_wgs84["distance_km"] = distances
    
    nearby = shelters_wgs84[shelters_wgs84["distance_km"] <= max_distance_km]
    nearby = nearby.nsmallest(max_results, "distance_km")
    
    results = []
    for _, row in nearby.iterrows():
        walking_time = int(row["distance_km"] * 15)
        
        route_coords = [
            [longitude, latitude],
            [row["longitude"], row["latitude"]]
        ]
        route_geometry = {
            "type": "LineString",
            "coordinates": route_coords
        }
        
        results.append({
            "shelter_id": int(row["shelter_id"]),
            "name": str(row["name"]),
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "capacity": int(row["capacity"]),
            "distance_km": float(row["distance_km"]),
            "walking_time_min": walking_time,
            "route_geometry": route_geometry
        })
    
    return results


def get_shelters_geojson(shelters_gdf: gpd.GeoDataFrame = None) -> Dict[str, Any]:
    if shelters_gdf is None or len(shelters_gdf) == 0:
        shelters_gdf = create_default_shelters()
    
    shelters_wgs84 = shelters_gdf.to_crs("EPSG:4326") if shelters_gdf.crs != "EPSG:4326" else shelters_gdf
    return shelters_wgs84.__geo_interface__