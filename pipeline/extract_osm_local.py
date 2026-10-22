"""Extract water bodies, roads, and underpasses for Chennai from Geofabrik Southern Zone OSM PBF.

Outputs:
  data/processed/water.gpkg      - Water bodies (polygons/lines)
  data/processed/roads.gpkg      - Road network (lines)
  data/processed/underpasses.gpkg - Underpasses and fords (points/polygons)

Source: Geofabrik Southern Zone extract (532 MB PBF)
  https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf

Uses local PBF with bbox filtering - no external API calls.
"""

from __future__ import annotations

import geopandas as gpd
import httpx
import pandas as pd
import structlog
from pathlib import Path
from typing import Optional
from shapely.geometry import Point, LineString, Polygon, MultiPolygon, mapping
from shapely.ops import unary_union

logger = structlog.get_logger()

# Chennai bounding box (WGS84)
CHENNAI_BBOX_WGS84 = (80.0, 12.8, 80.35, 13.3)  # minx, miny, maxx, maxy

# Geofabrik download URL
GEOFABRIK_URL = "https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf"
# Check for existing downloaded file first
EXISTING_PBF = Path("data/raw/southern-zone-261020.osm.pbf")
PBF_PATH = EXISTING_PBF if EXISTING_PBF.exists() else Path("data/raw/osm/southern-zone-latest.osm.pbf")

# Output paths
PROCESSED_DIR = Path("data/processed")
WATER_PATH = PROCESSED_DIR / "water.gpkg"
ROADS_PATH = PROCESSED_DIR / "roads.gpkg"
UNDERPASSES_PATH = PROCESSED_DIR / "underpasses.gpkg"


def download_pbf(url: str = GEOFABRIK_URL, output_path: Path = PBF_PATH, force: bool = False) -> Path:
    """Download Geofabrik PBF with resume support."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if output_path.exists() and not force:
        size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info("PBF already exists, skipping download", path=str(output_path), size_mb=round(size_mb, 1))
        return output_path
    
    logger.info("Downloading Geofabrik Southern Zone PBF", url=url, output=str(output_path))
    
    # Stream download with progress
    with httpx.stream("GET", url, timeout=3600.0, follow_redirects=True) as response:
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))
        
        downloaded = 0
        with open(output_path, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0 and downloaded % (50 * 1024 * 1024) == 0:  # Log every 50 MB
                    pct = (downloaded / total_size) * 100
                    logger.info("Download progress", pct=round(pct, 1), downloaded_mb=round(downloaded / (1024*1024), 1))
    
    final_size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info("Download complete", path=str(output_path), size_mb=round(final_size_mb, 1))
    return output_path


def read_osm_layer(pbf_path: Path, layer: str, bbox: tuple, columns: Optional[list] = None) -> gpd.GeoDataFrame:
    """Read a specific layer from OSM PBF with bbox filter.
    
    Args:
        pbf_path: Path to OSM PBF file
        layer: OSM layer name ('points', 'lines', 'multilinestrings', 'multipolygons', 'other_relations')
        bbox: (minx, miny, maxx, maxy) in WGS84
        columns: Optional list of columns to read (saves memory)
    
    Returns:
        GeoDataFrame with geometries in WGS84 (EPSG:4326)
    """
    logger.info("Reading OSM layer", layer=layer, bbox=bbox)
    
    try:
        # Read with bbox filter - geopandas/pyogrio passes this to GDAL
        gdf = gpd.read_file(
            pbf_path,
            layer=layer,
            bbox=bbox,
            columns=columns,
            engine="pyogrio"
        )
        
        if len(gdf) == 0:
            logger.warning("No features found in layer", layer=layer)
            return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        
        # Ensure CRS is WGS84
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        elif gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        
        logger.info("Layer read complete", layer=layer, features=len(gdf))
        return gdf
        
    except Exception as e:
        logger.error("Failed to read OSM layer", layer=layer, error=str(e))
        raise


def extract_water_features(pbf_path: Path, bbox: tuple) -> gpd.GeoDataFrame:
    """Extract water bodies from OSM multipolygons and lines."""
    logger.info("Extracting water features")
    
    water_geoms = []
    
    # Read multipolygons (water bodies as polygons)
    mpoly_gdf = read_osm_layer(pbf_path, "multipolygons", bbox, 
                               columns=["natural", "waterway", "name", "name:en"])
    
    if len(mpoly_gdf) > 0:
        # Filter for water bodies - handle missing columns
        natural_col = mpoly_gdf.get("natural", pd.Series("", index=mpoly_gdf.index))
        waterway_col = mpoly_gdf.get("waterway", pd.Series("", index=mpoly_gdf.index))
        
        water_mask = (
            (natural_col == "water") |
            (waterway_col.isin(["river", "canal", "drain", "stream", "riverbank"]))
        )
        water_polys = mpoly_gdf[water_mask].copy()
        
        for _, row in water_polys.iterrows():
            tags = {}
            for col in ["natural", "waterway", "name", "name:en"]:
                if col in row and row[col]:
                    tags[col] = row[col]
            
            water_geoms.append({
                "geometry": row.geometry,
                "water_type": tags.get("waterway", tags.get("natural", "water")),
                "name": tags.get("name:en", tags.get("name", "")),
                "source": "multipolygon"
            })
    
    # Read lines (waterways as lines)
    lines_gdf = read_osm_layer(pbf_path, "lines", bbox,
                               columns=["natural", "waterway", "name", "name:en"])
    
    if len(lines_gdf) > 0:
        natural_col = lines_gdf.get("natural", pd.Series("", index=lines_gdf.index))
        waterway_col = lines_gdf.get("waterway", pd.Series("", index=lines_gdf.index))
        
        water_mask = (
            (natural_col == "water") |
            (waterway_col.isin(["river", "canal", "drain", "stream"]))
        )
        water_lines = lines_gdf[water_mask].copy()
        
        for _, row in water_lines.iterrows():
            tags = {}
            for col in ["natural", "waterway", "name", "name:en"]:
                if col in row and row[col]:
                    tags[col] = row[col]
            
            water_geoms.append({
                "geometry": row.geometry,
                "water_type": tags.get("waterway", tags.get("natural", "water")),
                "name": tags.get("name:en", tags.get("name", "")),
                "source": "line"
            })
    
    if not water_geoms:
        logger.warning("No water features found")
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:32644")
    
    gdf = gpd.GeoDataFrame(water_geoms, crs="EPSG:4326")
    gdf = gdf.to_crs("EPSG:32644")
    logger.info("Water features extracted", count=len(gdf))
    return gdf[["geometry", "water_type", "name"]]


def parse_other_tags(tag_str: str) -> dict:
    """Parse OSM other_tags string into a dict.
    
    Format: '"key"=>"value","key2"=>"value2"'
    """
    if not tag_str or pd.isna(tag_str):
        return {}
    
    result = {}
    # Simple parsing for "key"=>"value" pairs
    import re
    pairs = re.findall(r'"([^"]+)"\s*=>\s*"([^"]*)"', str(tag_str))
    for key, value in pairs:
        result[key] = value
    return result


def extract_road_features(pbf_path: Path, bbox: tuple) -> gpd.GeoDataFrame:
    """Extract road network from OSM lines."""
    logger.info("Extracting road features")
    
    HIGHWAY_TYPES = {
        "motorway", "trunk", "primary", "secondary", 
        "tertiary", "residential", "service", "unclassified"
    }
    
    # Read lines layer with other_tags
    lines_gdf = read_osm_layer(pbf_path, "lines", bbox,
                               columns=["highway", "name", "name:en", "other_tags"])
    
    if len(lines_gdf) == 0:
        logger.warning("No line features found")
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:32644")
    
    # Filter for road types
    highway_col = lines_gdf.get("highway", pd.Series("", index=lines_gdf.index))
    road_mask = highway_col.isin(HIGHWAY_TYPES)
    roads = lines_gdf[road_mask].copy()
    
    if len(roads) == 0:
        logger.warning("No road features found after filtering")
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:32644")
    
    # Parse other_tags for tunnel, layer, bridge
    if "other_tags" in roads.columns:
        parsed = roads["other_tags"].apply(parse_other_tags)
        roads["tunnel"] = parsed.apply(lambda d: d.get("tunnel", "no"))
        roads["layer"] = parsed.apply(lambda d: d.get("layer", "0"))
        roads["bridge"] = parsed.apply(lambda d: d.get("bridge", "no"))
    else:
        roads["tunnel"] = "no"
        roads["layer"] = "0"
        roads["bridge"] = "no"
    
    # Build output records
    records = []
    for _, row in roads.iterrows():
        highway_type = row.get("highway", "road")
        is_tunnel = row.get("tunnel", "no") == "yes"
        
        # Parse layer
        layer_val = 0
        try:
            layer_val = int(str(row.get("layer", "0")).strip())
        except (ValueError, TypeError):
            pass
        
        is_bridge = row.get("bridge", "no") == "yes"
        
        records.append({
            "geometry": row.geometry,
            "highway_type": highway_type,
            "name": row.get("name:en", row.get("name", "")),
            "is_tunnel": is_tunnel,
            "layer": layer_val,
            "is_bridge": is_bridge
        })
    
    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    gdf = gdf.to_crs("EPSG:32644")
    logger.info("Road features extracted", count=len(gdf))
    return gdf[["geometry", "highway_type", "name", "is_tunnel", "layer", "is_bridge"]]


def extract_underpass_features(pbf_path: Path, bbox: tuple) -> gpd.GeoDataFrame:
    """Extract underpasses and fords from OSM lines and points."""
    logger.info("Extracting underpass features")
    
    underpass_geoms = []
    
    # Read lines (tunnels, roads with negative layer) with other_tags
    lines_gdf = read_osm_layer(pbf_path, "lines", bbox,
                               columns=["highway", "name", "name:en", "other_tags"])
    
    if len(lines_gdf) > 0:
        # Parse other_tags for tunnel, layer
        if "other_tags" in lines_gdf.columns:
            parsed = lines_gdf["other_tags"].apply(parse_other_tags)
            lines_gdf["tunnel"] = parsed.apply(lambda d: d.get("tunnel", "no"))
            lines_gdf["layer"] = parsed.apply(lambda d: d.get("layer", "0"))
        else:
            lines_gdf["tunnel"] = "no"
            lines_gdf["layer"] = "0"
        
        # Tunnel = yes
        tunnel_col = lines_gdf.get("tunnel", pd.Series("no", index=lines_gdf.index))
        tunnel_mask = tunnel_col == "yes"
        
        # Negative layer (excluding 0)
        layer_col = lines_gdf.get("layer", pd.Series("0", index=lines_gdf.index))
        layer_neg = layer_col.apply(
            lambda x: x is not None and str(x).lstrip("-").isdigit() and int(str(x)) < 0
        )
        
        underpass_mask = tunnel_mask | layer_neg
        underpass_lines = lines_gdf[underpass_mask].copy()
        
        for _, row in underpass_lines.iterrows():
            underpass_geoms.append({
                "geometry": row.geometry,
                "name": row.get("name:en", row.get("name", "")),
                "highway": row.get("highway", ""),
                "layer": str(row.get("layer", "0")),
                "tunnel": row.get("tunnel", "no"),
                "source": "line"
            })
    
    # Read points (fords) - check other_tags for ford
    points_gdf = read_osm_layer(pbf_path, "points", bbox,
                                columns=["highway", "name", "name:en", "ford", "other_tags"])
    
    if len(points_gdf) > 0:
        # Parse other_tags for ford
        if "other_tags" in points_gdf.columns:
            parsed = points_gdf["other_tags"].apply(parse_other_tags)
            points_gdf["ford"] = parsed.apply(lambda d: d.get("ford", "no"))
        else:
            points_gdf["ford"] = "no"
        
        highway_col = points_gdf.get("highway", pd.Series("", index=points_gdf.index))
        ford_col = points_gdf.get("ford", pd.Series("no", index=points_gdf.index))
        
        ford_mask = (
            (highway_col == "ford") |
            (ford_col == "yes")
        )
        fords = points_gdf[ford_mask].copy()
        
        for _, row in fords.iterrows():
            # Buffer point slightly for visibility
            geom = row.geometry.buffer(0.0001)  # ~10m in degrees
            underpass_geoms.append({
                "geometry": geom,
                "name": row.get("name:en", row.get("name", "Ford")),
                "highway": "ford",
                "layer": "0",
                "tunnel": "no",
                "source": "point"
            })
    
    if not underpass_geoms:
        logger.warning("No underpass features found")
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:32644")
    
    gdf = gpd.GeoDataFrame(underpass_geoms, crs="EPSG:4326")
    gdf = gdf.to_crs("EPSG:32644")
    logger.info("Underpass features extracted", count=len(gdf))
    return gdf[["geometry", "name", "highway", "layer", "tunnel"]]


def main(force_download: bool = False) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    
    if WATER_PATH.exists() and ROADS_PATH.exists() and UNDERPASSES_PATH.exists() and not force_download:
        logger.info("OSM data already exists, skipping")
        return
    
    # Step 1: Download PBF
    pbf_path = download_pbf(force=force_download)
    
    # Step 2: Extract features
    logger.info("Starting OSM feature extraction for Chennai")
    
    water_gdf = extract_water_features(pbf_path, CHENNAI_BBOX_WGS84)
    roads_gdf = extract_road_features(pbf_path, CHENNAI_BBOX_WGS84)
    underpass_gdf = extract_underpass_features(pbf_path, CHENNAI_BBOX_WGS84)
    
    # Step 3: Save
    water_gdf.to_file(WATER_PATH, driver="GPKG")
    roads_gdf.to_file(ROADS_PATH, driver="GPKG")
    underpass_gdf.to_file(UNDERPASSES_PATH, driver="GPKG")
    
    logger.info("OSM data saved", 
                water=len(water_gdf), 
                roads=len(roads_gdf), 
                underpasses=len(underpass_gdf))


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    main(force_download=force)