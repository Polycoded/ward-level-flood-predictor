import geopandas as gpd
import numpy as np
from shapely.geometry import Point
from shapely.ops import nearest_points, unary_union
from typing import Union
import structlog

logger = structlog.get_logger()


def distance_to_nearest(geoms: gpd.GeoDataFrame, target_geoms: gpd.GeoDataFrame) -> gpd.GeoSeries:
    if geoms.crs != target_geoms.crs:
        target_geoms = target_geoms.to_crs(geoms.crs)
    
    target_union = unary_union(target_geoms.geometry.tolist())
    
    def get_distance(geom):
        if geom.is_empty:
            return np.nan
        centroid = geom.centroid
        nearest = nearest_points(centroid, target_union)[1]
        return centroid.distance(nearest)
    
    return geoms.geometry.apply(get_distance)


def compute_ward_water_distances(wards: gpd.GeoDataFrame, water: gpd.GeoDataFrame) -> gpd.GeoSeries:
    logger.info("Computing ward distances to water bodies")
    return distance_to_nearest(wards, water)


def compute_road_distances(points: gpd.GeoDataFrame, roads: gpd.GeoDataFrame) -> gpd.GeoSeries:
    logger.info("Computing point distances to roads")
    return distance_to_nearest(points, roads)


def point_to_line_distance(point: Point, line) -> float:
    nearest = nearest_points(point, line)[1]
    return point.distance(nearest)


def compute_feature_distances(
    wards: gpd.GeoDataFrame,
    features: dict[str, gpd.GeoDataFrame]
) -> dict[str, gpd.GeoSeries]:
    results = {}
    
    for name, feat_gdf in features.items():
        if len(feat_gdf) == 0:
            results[name] = gpd.GeoSeries([np.nan] * len(wards), index=wards.index)
            continue
        
        if wards.crs != feat_gdf.crs:
            feat_gdf = feat_gdf.to_crs(wards.crs)
        
        union = unary_union(feat_gdf.geometry.tolist())
        
        def get_dist(geom):
            if geom.is_empty:
                return np.nan
            centroid = geom.centroid
            nearest = nearest_points(centroid, union)[1]
            return centroid.distance(nearest)
        
        results[name] = wards.geometry.apply(get_dist)
        logger.info(f"Computed distances to {name}", count=len(wards))
    
    return results