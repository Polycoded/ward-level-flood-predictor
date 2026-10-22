"""Projected centroid distances, not hydraulic connectivity or street-level distances."""

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import CRS
from shapely import get_coordinates
from shapely.geometry import Point
from shapely.ops import unary_union


def _validate_crs(crs, *, metric: bool = False) -> CRS:
    if crs is None:
        raise ValueError("Missing CRS; assign the verified source CRS before computing distances")
    parsed = CRS.from_user_input(crs)
    axes = parsed.axis_info
    if not metric and parsed.is_geographic and len(axes) == 2:
        if all(axis.unit_name == "degree" for axis in axes):
            return parsed
    if not parsed.is_projected or len(axes) != 2 or not all(
        axis.unit_name in {"metre", "meter"} and axis.unit_conversion_factor == 1
        for axis in axes
    ):
        raise ValueError("Distances require a projected metre CRS; unsupported units/CRS. "
                         "Use EPSG:32644 for Chennai")
    return parsed


def _missing(geom) -> bool:
    return geom is None or geom.is_empty


def _validate_geometry(geom) -> None:
    if _missing(geom):
        return
    if not geom.is_valid or not np.isfinite(get_coordinates(geom)).all():
        raise ValueError("Invalid or non-finite geometry; repair/verify the source geometry first")
    if geom.has_z:
        raise ValueError("Only 2D geometries are supported; explicitly remove Z coordinates first")


def distance_to_nearest(geoms: gpd.GeoDataFrame, target_geoms: gpd.GeoDataFrame,
                        *, metric_crs: str = "EPSG:32644") -> pd.Series:
    """Metres from projected source centroids to nearest target geometry.

    A missing source yields NaN; empty/partly missing target coverage yields all NaN.
    Both inputs need verified CRS even if empty. Original indices/order are retained.
    """
    _validate_crs(metric_crs, metric=True)
    for frame in (geoms, target_geoms):
        _validate_crs(frame.crs)
        for geom in frame.geometry:
            _validate_geometry(geom)
    sources = geoms.to_crs(metric_crs)
    targets = target_geoms.to_crs(metric_crs)
    for frame in (sources, targets):
        for geom in frame.geometry:
            _validate_geometry(geom)
    if len(targets) == 0 or any(_missing(geom) for geom in targets.geometry):
        return pd.Series(np.nan, index=geoms.index, dtype="float64")
    union = unary_union(targets.geometry.tolist())
    distances = [np.nan if _missing(geom) else geom.centroid.distance(union)
                 for geom in sources.geometry]
    return pd.Series(distances, index=geoms.index, dtype="float64")


def compute_ward_water_distances(wards: gpd.GeoDataFrame, water: gpd.GeoDataFrame,
                                 *, metric_crs: str = "EPSG:32644") -> pd.Series:
    return distance_to_nearest(wards, water, metric_crs=metric_crs)


def compute_road_distances(points: gpd.GeoDataFrame, roads: gpd.GeoDataFrame,
                           *, metric_crs: str = "EPSG:32644") -> pd.Series:
    return distance_to_nearest(points, roads, metric_crs=metric_crs)


def point_to_line_distance(point: Point, line, *, crs: str | None = None) -> float:
    """Raw Shapely coordinates must already be in metres; no CRS can be inferred."""
    if crs is not None:
        _validate_crs(crs, metric=True)
    for geom in (point, line):
        _validate_geometry(geom)
    if _missing(point) or _missing(line):
        return float("nan")
    return float(point.distance(line))


def compute_feature_distances(wards: gpd.GeoDataFrame,
                              features: dict[str, gpd.GeoDataFrame], *,
                              metric_crs: str = "EPSG:32644") -> dict[str, pd.Series]:
    _validate_crs(wards.crs)
    _validate_crs(metric_crs, metric=True)
    return {name: distance_to_nearest(wards, frame, metric_crs=metric_crs)
            for name, frame in features.items()}
