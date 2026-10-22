"""Extract water bodies, roads, and underpasses for Chennai from OpenStreetMap via Overpass API.

Outputs:
  data/processed/water.gpkg      - Water bodies (polygons/lines)
  data/processed/roads.gpkg      - Road network (lines)
  data/processed/underpasses.gpkg - Underpasses and fords (points/polygons)

Uses the same robust multi-endpoint retry logic as extract_assets.py.
No synthetic fallback: if OSM is unreachable the script fails.
"""

from __future__ import annotations

import httpx
import json
import time
import structlog
from pathlib import Path
from typing import Any
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon, MultiPolygon, mapping
from shapely.ops import unary_union

logger = structlog.get_logger()

CHENNAI_BBOX = "12.8,80.0,13.3,80.35"  # south,west,north,east

# Split Chennai bbox into 4 smaller tiles to avoid Overpass timeouts
CHENNAI_TILES = [
    "12.8,80.0,13.05,80.175",   # SW
    "13.05,80.0,13.3,80.175",   # NW
    "12.8,80.175,13.05,80.35",  # SE
    "13.05,80.175,13.3,80.35",  # NE
]

OVERPASS_QUERIES = {
    "water": """
[out:json][timeout:120];
(
  way["natural"="water"]({bbox});
  way["waterway"~"river|canal"]({bbox});
  relation["natural"="water"]({bbox});
);
out body;
>;
out skel qt;
""",
    "roads": """
[out:json][timeout:120];
(
  way["highway"~"motorway|trunk|primary|secondary|tertiary|residential|service|unclassified"]({bbox});
);
out body;
>;
out skel qt;
""",
    "underpasses": """
[out:json][timeout:120];
(
  way["highway"~"motorway|trunk|primary|secondary|tertiary"]["tunnel"="yes"]({bbox});
  way["highway"~"motorway|trunk|primary|secondary|tertiary"]["layer"~"^-?[1-9]"]["layer"!="0"]({bbox});
  node["highway"="ford"]({bbox});
);
out body;
>;
out skel qt;
""",
}

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

HEADERS = {
    "User-Agent": "ward-flood-predictor/0.1 (hackathon prototype; github.com/Polycoded/ward-level-flood-predictor)"
}

RAW_DIR = Path("data/raw/osm")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

WATER_PATH = PROCESSED_DIR / "water.gpkg"
ROADS_PATH = PROCESSED_DIR / "roads.gpkg"
UNDERPASSES_PATH = PROCESSED_DIR / "underpasses.gpkg"


def fetch_overpass_tiled(query_template: str, max_attempts: int = 3) -> dict[str, Any]:
    """Query Overpass across multiple tiles and combine results."""
    all_elements = []
    seen_ids = set()

    for tile_idx, bbox in enumerate(CHENNAI_TILES):
        query = query_template.format(bbox=bbox)
        logger.info("Querying Overpass tile", tile=tile_idx + 1, bbox=bbox)

        tile_elements = []
        for attempt in range(max_attempts):
            url = OVERPASS_URLS[(attempt + tile_idx) % len(OVERPASS_URLS)]
            try:
                logger.info("Querying Overpass", tile=tile_idx + 1, url=url, attempt=attempt + 1)
                response = httpx.post(url, data={"data": query}, headers=HEADERS, timeout=180.0)
                response.raise_for_status()
                data = response.json()
                elements = data.get("elements", [])
                # Deduplicate by (type, id)
                for elem in elements:
                    key = (elem.get("type"), elem.get("id"))
                    if key not in seen_ids:
                        seen_ids.add(key)
                        tile_elements.append(elem)
                logger.info("Tile query successful", tile=tile_idx + 1, elements=len(tile_elements), url=url)
                break
            except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
                logger.warning("Tile query failed", tile=tile_idx + 1, url=url, error=str(exc))
                time.sleep(min(30, 10 * (attempt + 1)))
        else:
            logger.error("Tile failed after all attempts", tile=tile_idx + 1)
            raise RuntimeError(f"Tile {tile_idx + 1} failed after {max_attempts} attempts")

        all_elements.extend(tile_elements)

    return {"elements": all_elements}


def parse_overpass_elements(data: dict[str, Any]) -> tuple[dict, dict]:
    """Extract nodes and ways from Overpass response."""
    nodes = {
        node["id"]: (node["lon"], node["lat"])
        for node in data["elements"]
        if node["type"] == "node"
    }
    ways = {
        way["id"]: {"nodes": way["nodes"], "tags": way.get("tags", {})}
        for way in data["elements"]
        if way["type"] == "way"
    }
    return nodes, ways


def ways_to_geometries(nodes: dict, ways: dict, geom_type: str = "linestring") -> list[dict]:
    """Convert OSM ways to Shapely geometries."""
    geometries = []
    for way_id, way_data in ways.items():
        coords = [nodes[nid] for nid in way_data["nodes"] if nid in nodes]
        if len(coords) < 2:
            continue

        if geom_type == "linestring":
            geom = LineString(coords)
        elif geom_type == "polygon":
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            if len(coords) >= 4:
                geom = Polygon(coords)
            else:
                continue
        else:
            continue

        if geom.is_valid:
            geometries.append({"geometry": geom, "tags": way_data["tags"]})
    return geometries


def relations_to_geometries(nodes: dict, ways: dict, data: dict) -> list[dict]:
    """Convert OSM relations (multipolygons) to Shapely geometries."""
    geometries = []
    for element in data["elements"]:
        if element["type"] != "relation":
            continue
        tags = element.get("tags", {})
        outer_rings = []
        inner_rings = []

        for member in element.get("members", []):
            if member["type"] != "way" or member["ref"] not in ways:
                continue
            way_nodes = ways[member["ref"]]["nodes"]
            coords = [nodes[nid] for nid in way_nodes if nid in nodes]
            if len(coords) < 4:
                continue
            if member["role"] == "outer":
                outer_rings.append(coords)
            elif member["role"] == "inner":
                inner_rings.append(coords)

        if not outer_rings:
            continue

        polygons = []
        for outer in outer_rings:
            poly = Polygon(outer, holes=inner_rings if inner_rings else None)
            if poly.is_valid:
                polygons.append(poly)

        if polygons:
            geometry = MultiPolygon(polygons) if len(polygons) > 1 else polygons[0]
            geometries.append({"geometry": geometry, "tags": tags})

    return geometries


def extract_water(nodes: dict, ways: dict, data: dict) -> gpd.GeoDataFrame:
    water_geoms = []

    # Ways tagged as water bodies or waterways
    for geom_data in ways_to_geometries(nodes, ways, "polygon"):
        tags = geom_data["tags"]
        if tags.get("natural") == "water" or tags.get("waterway") in ("river", "canal", "drain", "stream"):
            water_geoms.append(geom_data)

    # Relations (multipolygons) for water bodies
    for geom_data in relations_to_geometries(nodes, ways, data):
        tags = geom_data["tags"]
        if tags.get("natural") == "water" or tags.get("waterway") in ("river", "canal"):
            water_geoms.append(geom_data)

    if not water_geoms:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    gdf = gpd.GeoDataFrame(water_geoms, crs="EPSG:4326")
    gdf = gdf.to_crs("EPSG:32644")
    gdf["water_type"] = gdf["tags"].apply(lambda t: t.get("waterway", t.get("natural", "water")))
    gdf["name"] = gdf["tags"].apply(lambda t: t.get("name:en", t.get("name", "")))
    return gdf[["geometry", "water_type", "name"]]


def extract_roads(nodes: dict, ways: dict) -> gpd.GeoDataFrame:
    road_geoms = []

    for geom_data in ways_to_geometries(nodes, ways, "linestring"):
        tags = geom_data["tags"]
        highway = tags.get("highway", "")
        if highway in ("motorway", "trunk", "primary", "secondary", "tertiary", "residential", "service", "unclassified"):
            geom_data["tags"]["highway"] = highway
            road_geoms.append(geom_data)

    if not road_geoms:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    gdf = gpd.GeoDataFrame(road_geoms, crs="EPSG:4326")
    gdf = gdf.to_crs("EPSG:32644")
    gdf["highway_type"] = gdf["tags"].apply(lambda t: t.get("highway", "road"))
    gdf["name"] = gdf["tags"].apply(lambda t: t.get("name:en", t.get("name", "")))
    gdf["is_tunnel"] = gdf["tags"].apply(lambda t: t.get("tunnel") == "yes")
    gdf["layer"] = gdf["tags"].apply(lambda t: int(t.get("layer", 0)) if t.get("layer", "0").lstrip("-").isdigit() else 0)
    gdf["is_bridge"] = gdf["tags"].apply(lambda t: t.get("bridge") == "yes")
    return gdf[["geometry", "highway_type", "name", "is_tunnel", "layer", "is_bridge"]]


def extract_underpasses(nodes: dict, ways: dict, data: dict) -> gpd.GeoDataFrame:
    underpass_geoms = []

    # Ways that are tunnels or have negative layer
    for geom_data in ways_to_geometries(nodes, ways, "linestring"):
        tags = geom_data["tags"]
        if tags.get("tunnel") == "yes" or (tags.get("layer", "0").lstrip("-").isdigit() and int(tags.get("layer", "0")) < 0):
            underpass_geoms.append({
                "geometry": geom_data["geometry"],
                "name": tags.get("name:en", tags.get("name", "")),
                "highway": tags.get("highway", ""),
                "layer": tags.get("layer", "0"),
                "tunnel": tags.get("tunnel", "no"),
            })

    # Ford nodes
    for element in data["elements"]:
        if element["type"] == "node" and element.get("tags", {}).get("highway") == "ford":
            if "lat" in element and "lon" in element:
                underpass_geoms.append({
                    "geometry": Point(element["lon"], element["lat"]).buffer(10),
                    "name": element["tags"].get("name:en", element["tags"].get("name", "Ford")),
                    "highway": "ford",
                    "layer": "0",
                    "tunnel": "no",
                })

    if not underpass_geoms:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    gdf = gpd.GeoDataFrame(underpass_geoms, crs="EPSG:4326")
    gdf = gdf.to_crs("EPSG:32644")
    return gdf


def save_raw_response(data: dict, filename: str) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / filename).write_text(json.dumps(data))
    logger.info("Saved raw Overpass response", path=str(RAW_DIR / filename))


def main() -> None:
    if WATER_PATH.exists() and ROADS_PATH.exists() and UNDERPASSES_PATH.exists():
        logger.info("OSM data already exists, skipping")
        return

    try:
        logger.info("Fetching water features from OSM (4 tiles)")
        water_data = fetch_overpass_tiled(OVERPASS_QUERIES["water"])
        save_raw_response(water_data, "osm_water.json")
        nodes, ways = parse_overpass_elements(water_data)
        water_gdf = extract_water(nodes, ways, water_data)

        logger.info("Fetching road features from OSM (4 tiles)")
        roads_data = fetch_overpass_tiled(OVERPASS_QUERIES["roads"])
        save_raw_response(roads_data, "osm_roads.json")
        nodes, ways = parse_overpass_elements(roads_data)
        roads_gdf = extract_roads(nodes, ways)

        logger.info("Fetching underpass features from OSM (4 tiles)")
        underpass_data = fetch_overpass_tiled(OVERPASS_QUERIES["underpasses"])
        save_raw_response(underpass_data, "osm_underpasses.json")
        nodes, ways = parse_overpass_elements(underpass_data)
        underpass_gdf = extract_underpasses(nodes, ways, underpass_data)

    except Exception as e:
        logger.error("Failed to fetch OSM data", error=str(e))
        raise

    water_gdf.to_file(WATER_PATH, driver="GPKG")
    roads_gdf.to_file(ROADS_PATH, driver="GPKG")
    underpass_gdf.to_file(UNDERPASSES_PATH, driver="GPKG")

    logger.info("OSM data saved", water=len(water_gdf), roads=len(roads_gdf), underpasses=len(underpass_gdf))


if __name__ == "__main__":
    main()