"""Precomputed road risk index.

The original ``score_roads`` re-did the road-to-ward spatial join, underpass
distance search and CRS conversion on every request (measured ~1.7 s). All of
that is static for a given dataset, so build it once and only apply the
rainfall factor per request (target < 50 ms).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union

HIGHWAY_WEIGHTS = {
    "motorway": 1.0, "trunk": 0.9, "primary": 0.8,
    "secondary": 0.6, "tertiary": 0.5, "residential": 0.4, "service": 0.3,
}

HIGHWAY_PRIORITY = {
    "motorway": 0, "trunk": 1, "primary": 2, "secondary": 3,
    "tertiary": 4, "residential": 5, "service": 6, "unclassified": 7,
}

RISK_THRESHOLDS = {
    "very_low": (0.0, 0.2), "low": (0.2, 0.35), "moderate": (0.35, 0.55),
    "high": (0.55, 0.75), "very_high": (0.75, 1.0),
}


def risk_level(score: float) -> str:
    for level, (low, high) in RISK_THRESHOLDS.items():
        if low <= score < high:
            return level
    return "very_high"


@dataclass(frozen=True)
class RoadRecord:
    road_id: str
    name: str
    highway_type: str
    is_underpass: bool
    base_score: float
    geometry: dict[str, Any]


class RoadRiskIndex:
    def __init__(self, records: list[RoadRecord], max_results: int = 100) -> None:
        self.records = records
        self.max_results = max_results

    def score(self, rainfall_mm: float, max_results: int | None = None) -> list[dict[str, Any]]:
        limit = max_results or self.max_results
        factor = min(max(rainfall_mm, 0.0) / 150.0, 2.0)
        results: list[dict[str, Any]] = []
        for record in self.records:
            score = min(record.base_score * factor, 1.0)
            if record.is_underpass:
                score = min(score * 1.5, 1.0)
            depth = score * 100.0 * factor
            if record.is_underpass:
                depth = min(depth * 2, 300)
            results.append({
                "road_id": record.road_id,
                "name": record.name,
                "highway_type": record.highway_type,
                "risk_score": float(score),
                "risk_level": risk_level(score),
                "is_underpass": record.is_underpass,
                "flood_depth_estimate_m": float(depth / 100.0),
                "geometry": record.geometry,
            })
        results.sort(key=lambda item: item["risk_score"], reverse=True)
        return results[:limit]


def build_index(
    roads_gdf: gpd.GeoDataFrame,
    underpasses_gdf: gpd.GeoDataFrame,
    wards_gdf: gpd.GeoDataFrame,
    max_roads: int = 5000,
) -> RoadRiskIndex:
    if roads_gdf is None or len(roads_gdf) == 0:
        return RoadRiskIndex([])

    roads = roads_gdf.to_crs("EPSG:32644") if roads_gdf.crs != "EPSG:32644" else roads_gdf.copy()
    wards = wards_gdf.to_crs("EPSG:32644") if wards_gdf.crs != "EPSG:32644" else wards_gdf

    underpass_geoms: list = []
    underpass_union = None
    if underpasses_gdf is not None and len(underpasses_gdf) > 0:
        under = underpasses_gdf.to_crs("EPSG:32644") if underpasses_gdf.crs != "EPSG:32644" else underpasses_gdf
        underpass_geoms = [geom for geom in under.geometry.tolist() if geom is not None and not geom.is_empty]
        if underpass_geoms:
            underpass_union = unary_union(underpass_geoms)

    ward_sindex = wards.sindex
    ward_data = [
        {
            "geometry": row.geometry,
            "elevation_mean": row.get("elevation_mean", 10.0),
            "slope_mean": row.get("slope_mean", 2.0),
            "impervious_frac": row.get("impervious_frac", 0.5),
            "dist_to_water": row.get("dist_to_water_m", 1000.0),
        }
        for _, row in wards.iterrows()
    ]

    roads = roads.copy()
    roads["_priority"] = roads["highway_type"].map(HIGHWAY_PRIORITY).fillna(8)
    roads = roads.sort_values("_priority").head(max_roads)

    wgs = gpd.GeoSeries(roads.geometry.values, crs="EPSG:32644").to_crs("EPSG:4326")

    records: list[RoadRecord] = []
    for position, (idx, road) in enumerate(roads.iterrows()):
        geom = road.geometry
        if geom is None or geom.is_empty:
            continue
        candidates = list(ward_sindex.intersection(geom.bounds))
        if not candidates:
            continue
        ward_info = None
        for wi in candidates:
            if wards.iloc[wi].geometry.intersects(geom):
                ward_info = ward_data[wi]
                break
        if ward_info is None:
            continue

        highway_type = road.get("highway_type", "road")
        if not isinstance(highway_type, str):
            highway_type = "road"
        try:
            layer = float(road.get("layer", 0) or 0)
        except (TypeError, ValueError):
            layer = 0.0
        is_underpass = bool(road.get("is_tunnel", False)) or layer < 0

        if is_underpass:
            underpass_proximity = 0.0
        elif underpass_union is not None:
            min_dist = geom.distance(underpass_union)
            underpass_proximity = max(0.0, 1.0 - min_dist / 200.0)
        else:
            underpass_proximity = 0.0

        elevation_risk = max(0.0, 1.0 - ward_info["elevation_mean"] / 20.0)
        slope_risk = max(0.0, 1.0 - ward_info["slope_mean"] / 10.0)
        impervious_risk = ward_info["impervious_frac"]
        water_risk = max(0.0, 1.0 - ward_info["dist_to_water"] / 3000.0)

        base_score = (
            0.25 * elevation_risk
            + 0.15 * slope_risk
            + 0.25 * impervious_risk
            + 0.15 * water_risk
            + 0.10 * HIGHWAY_WEIGHTS.get(highway_type, 0.5)
            + 0.10 * underpass_proximity
        )

        name = road.get("name")
        if pd.isna(name):
            name = f"Road {idx}"

        records.append(RoadRecord(
            road_id=str(idx),
            name=str(name),
            highway_type=highway_type,
            is_underpass=is_underpass,
            base_score=float(base_score),
            geometry=wgs.iloc[position].__geo_interface__,
        ))

    return RoadRiskIndex(records)
