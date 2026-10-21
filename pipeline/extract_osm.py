import geopandas as gpd
import httpx
import json
from pathlib import Path
import structlog
from shapely.geometry import shape, LineString, Point
from shapely.ops import unary_union

logger = structlog.get_logger()

CHENNAI_BBOX = [80.0, 12.8, 80.35, 13.3]

OVERPASS_QUERIES = {
    "water": """
[out:json][timeout:120];
(
  way["natural"="water"](80.0,12.8,80.35,13.3);
  way["waterway"="river"](80.0,12.8,80.35,13.3);
  way["waterway"="canal"](80.0,12.8,80.35,13.3);
  way["waterway"="drain"](80.0,12.8,80.35,13.3);
  relation["natural"="water"](80.0,12.8,80.35,13.3);
  relation["waterway"="river"](80.0,12.8,80.35,13.3);
);
out body;
>;
out skel qt;
""",
    "roads": """
[out:json][timeout:120];
(
  way["highway"~"motorway|trunk|primary|secondary|tertiary|residential|service"](80.0,12.8,80.35,13.3);
);
out body;
>;
out skel qt;
""",
    "underpasses": """
[out:json][timeout:120];
(
  way["highway"~"motorway|trunk|primary|secondary|tertiary"]["tunnel"="yes"](80.0,12.8,80.35,13.3);
  way["highway"~"motorway|trunk|primary|secondary|tertiary"]["layer"="-1"](80.0,12.8,80.35,13.3);
  way["highway"~"motorway|trunk|primary|secondary|tertiary"]["layer"="-2"](80.0,12.8,80.35,13.3);
  node["highway"="ford"](80.0,12.8,80.35,13.3);
);
out body;
>;
out skel qt;
""",
}

def fetch_overpass(query: str) -> dict:
    url = "https://overpass-api.de/api/interpreter"
    response = httpx.post(url, data={"data": query}, timeout=180.0)
    response.raise_for_status()
    return response.json()

def parse_overpass_elements(data: dict) -> tuple[dict, dict]:
    nodes = {node["id"]: (node["lon"], node["lat"]) for node in data["elements"] if node["type"] == "node"}
    ways = {}
    relations = {}
    
    for element in data["elements"]:
        if element["type"] == "way":
            ways[element["id"]] = {
                "nodes": element["nodes"],
                "tags": element.get("tags", {}),
            }
        elif element["type"] == "relation":
            relations[element["id"]] = {
                "members": element["members"],
                "tags": element.get("tags", {}),
            }
    
    return nodes, ways, relations

def ways_to_geometries(nodes: dict, ways: dict, geom_type: str = "linestring") -> list:
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
                from shapely.geometry import Polygon
                geom = Polygon(coords)
            else:
                continue
        else:
            continue
        
        if geom.is_valid:
            geometries.append({"geometry": geom, "tags": way_data["tags"]})
    
    return geometries

def relations_to_geometries(nodes: dict, ways: dict, relations: dict) -> list:
    geometries = []
    for rel_id, rel_data in relations.items():
        outer_rings = []
        inner_rings = []
        
        for member in rel_data["members"]:
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
        
        from shapely.geometry import Polygon, MultiPolygon
        polygons = []
        for outer in outer_rings:
            poly = Polygon(outer, holes=inner_rings if inner_rings else None)
            if poly.is_valid:
                polygons.append(poly)
        
        if polygons:
            geometry = MultiPolygon(polygons) if len(polygons) > 1 else polygons[0]
            geometries.append({"geometry": geometry, "tags": rel_data["tags"]})
    
    return geometries

def extract_water_features(nodes: dict, ways: dict, relations: dict) -> gpd.GeoDataFrame:
    water_geoms = []
    
    for geom_data in ways_to_geometries(nodes, ways, "polygon"):
        tags = geom_data["tags"]
        if tags.get("natural") == "water" or tags.get("waterway") in ("river", "canal", "drain"):
            water_geoms.append(geom_data)
    
    for geom_data in relations_to_geometries(nodes, ways, relations):
        tags = geom_data["tags"]
        if tags.get("natural") == "water" or tags.get("waterway") in ("river", "canal", "drain"):
            water_geoms.append(geom_data)
    
    if not water_geoms:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    
    gdf = gpd.GeoDataFrame(water_geoms, crs="EPSG:4326")
    gdf = gdf.to_crs("EPSG:32644")
    gdf["water_type"] = gdf["tags"].apply(lambda t: t.get("waterway", t.get("natural", "water")))
    return gdf[["geometry", "water_type"]]

def extract_road_features(nodes: dict, ways: dict) -> gpd.GeoDataFrame:
    road_geoms = []
    
    for geom_data in ways_to_geometries(nodes, ways, "linestring"):
        tags = geom_data["tags"]
        highway = tags.get("highway", "")
        if highway in ("motorway", "trunk", "primary", "secondary", "tertiary", "residential", "service"):
            geom_data["tags"]["highway"] = highway
            road_geoms.append(geom_data)
    
    if not road_geoms:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    
    gdf = gpd.GeoDataFrame(road_geoms, crs="EPSG:4326")
    gdf = gdf.to_crs("EPSG:32644")
    gdf["highway_type"] = gdf["tags"].apply(lambda t: t.get("highway", "road"))
    gdf["is_tunnel"] = gdf["tags"].apply(lambda t: t.get("tunnel") == "yes")
    gdf["layer"] = gdf["tags"].apply(lambda t: int(t.get("layer", 0)))
    return gdf[["geometry", "highway_type", "is_tunnel", "layer"]]

def extract_underpass_features(nodes: dict, ways: dict) -> gpd.GeoDataFrame:
    underpass_geoms = []
    
    for geom_data in ways_to_geometries(nodes, ways, "linestring"):
        tags = geom_data["tags"]
        if tags.get("tunnel") == "yes" or tags.get("layer", "0") in ("-1", "-2"):
            underpass_geoms.append({
                "geometry": geom_data["geometry"],
                "name": tags.get("name", ""),
                "highway": tags.get("highway", ""),
                "layer": tags.get("layer", "0"),
            })
    
    for element in [e for e in ways.values() if e["tags"].get("highway") == "ford"]:
        coords = [nodes[nid] for nid in element["nodes"] if nid in nodes]
        if len(coords) >= 1:
            underpass_geoms.append({
                "geometry": Point(coords[0]),
                "name": element["tags"].get("name", ""),
                "highway": "ford",
                "layer": "0",
            })
    
    if not underpass_geoms:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    
    gdf = gpd.GeoDataFrame(underpass_geoms, crs="EPSG:4326")
    gdf = gdf.to_crs("EPSG:32644")
    return gdf

def create_synthetic_osm() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    logger.info("Creating synthetic OSM data for development")
    
    from shapely.geometry import LineString, Polygon, Point
    import numpy as np
    
    water_geoms = []
    roads_geoms = []
    underpass_geoms = []
    
    for i in range(5):
        x = 200000 + i * 8000
        y = 1420000 + i * 5000
        water_geoms.append({
            "geometry": LineString([(x, y), (x + 10000, y + 5000)]).buffer(50),
            "water_type": "canal",
        })
    
    water_geoms.append({
        "geometry": Polygon([
            (210000, 1440000), (215000, 1440000), 
            (215000, 1445000), (210000, 1445000)
        ]),
        "water_type": "water",
    })
    
    for i in range(10):
        x1 = 199000 + np.random.random() * 39000
        y1 = 1415000 + np.random.random() * 43000
        x2 = x1 + np.random.random() * 5000 - 2500
        y2 = y1 + np.random.random() * 5000 - 2500
        highway_type = np.random.choice(["primary", "secondary", "tertiary", "residential"])
        is_tunnel = np.random.random() < 0.1
        layer = -1 if is_tunnel else 0
        roads_geoms.append({
            "geometry": LineString([(x1, y1), (x2, y2)]),
            "highway_type": highway_type,
            "is_tunnel": is_tunnel,
            "layer": layer,
        })
    
    for i in range(8):
        x = 200000 + np.random.random() * 39000
        y = 1415000 + np.random.random() * 43000
        underpass_geoms.append({
            "geometry": Point(x, y).buffer(200),
            "name": f"Underpass {i+1}",
            "highway": "primary",
            "layer": "-1",
        })
    
    water_gdf = gpd.GeoDataFrame(water_geoms, crs="EPSG:32644")
    roads_gdf = gpd.GeoDataFrame(roads_geoms, crs="EPSG:32644")
    underpass_gdf = gpd.GeoDataFrame(underpass_geoms, crs="EPSG:32644")
    
    return water_gdf, roads_gdf, underpass_gdf

def main():
    processed_dir = Path("data/processed")
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    water_path = processed_dir / "water.gpkg"
    roads_path = processed_dir / "roads.gpkg"
    underpasses_path = processed_dir / "underpasses.gpkg"
    
    if water_path.exists() and roads_path.exists() and underpasses_path.exists():
        logger.info("OSM data already exists, skipping")
        return
    
    try:
        logger.info("Fetching water features from OSM")
        water_data = fetch_overpass(OVERPASS_QUERIES["water"])
        nodes, ways, relations = parse_overpass_elements(water_data)
        water_gdf = extract_water_features(nodes, ways, relations)
        
        logger.info("Fetching road features from OSM")
        roads_data = fetch_overpass(OVERPASS_QUERIES["roads"])
        nodes, ways, _ = parse_overpass_elements(roads_data)
        roads_gdf = extract_road_features(nodes, ways)
        
        logger.info("Fetching underpass features from OSM")
        underpass_data = fetch_overpass(OVERPASS_QUERIES["underpasses"])
        nodes, ways, _ = parse_overpass_elements(underpass_data)
        underpass_gdf = extract_underpass_features(nodes, ways)
        
    except Exception as e:
        logger.error("Failed to fetch OSM data", error=str(e))
        logger.warning("Creating synthetic OSM data for development")
        water_gdf, roads_gdf, underpass_gdf = create_synthetic_osm()
    
    water_gdf.to_file(water_path, driver="GPKG")
    roads_gdf.to_file(roads_path, driver="GPKG")
    underpass_gdf.to_file(underpasses_path, driver="GPKG")
    
    logger.info("OSM data saved", water=len(water_gdf), roads=len(roads_gdf), underpasses=len(underpass_gdf))

if __name__ == "__main__":
    main()