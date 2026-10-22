import geopandas as gpd
import httpx
import json
from pathlib import Path
import structlog

logger = structlog.get_logger()

CHENNAI_BBOX = [80.0, 12.8, 80.35, 13.3]

OVERPASS_QUERY = """
[out:json][timeout:120];
area["name"="Chennai"]["admin_level"="8"]->.searchArea;
(
  relation["admin_level"="9"]["boundary"="administrative"](area.searchArea);
);
out body;
>;
out skel qt;
"""

HEADERS = {"User-Agent": "ward-flood-predictor/0.1 (hackathon prototype; github.com/Polycoded/ward-level-flood-predictor)"}

def fetch_wards_from_overpass() -> dict:
    url = "https://overpass-api.de/api/interpreter"
    logger.info("Fetching Chennai wards from Overpass API")
    response = httpx.post(url, data={"data": OVERPASS_QUERY}, headers=HEADERS, timeout=180.0)
    response.raise_for_status()
    return response.json()

def parse_overpass_to_geojson(data: dict) -> gpd.GeoDataFrame:
    nodes = {node["id"]: (node["lon"], node["lat"]) for node in data["elements"] if node["type"] == "node"}
    ways = {way["id"]: way["nodes"] for way in data["elements"] if way["type"] == "way"}
    
    features = []
    for element in data["elements"]:
        if element["type"] != "relation":
            continue
        
        tags = element.get("tags", {})
        ward_name = tags.get("name", tags.get("name:en", f"Ward {tags.get('ward_number', 'unknown')}"))
        ward_number = tags.get("ward_number", tags.get("ward_no", ""))
        
        outer_rings = []
        inner_rings = []
        
        for member in element.get("members", []):
            if member["type"] != "way" or member["ref"] not in ways:
                continue
            way_nodes = ways[member["ref"]]
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
        
        if not polygons:
            continue
        
        geometry = MultiPolygon(polygons) if len(polygons) > 1 else polygons[0]
        
        features.append({
            "ward_number": str(ward_number),
            "ward_name": ward_name,
            "geometry": geometry,
        })
    
    gdf = gpd.GeoDataFrame(features, crs="EPSG:4326")
    gdf = gdf.to_crs("EPSG:32644")
    gdf["area_sqkm"] = gdf.geometry.area / 1e6
    gdf = gdf.sort_values("ward_number").reset_index(drop=True)
    gdf["ward_id"] = gdf.index + 1
    
    return gdf

def main():
    output_path = Path("data/processed/wards.geojson")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        data = fetch_wards_from_overpass()
        gdf = parse_overpass_to_geojson(data)
        
        if len(gdf) == 0:
            raise ValueError("No wards parsed from Overpass response")
        
        logger.info("Wards downloaded", count=len(gdf))
        gdf.to_file(output_path, driver="GeoJSON")
        logger.info("Wards saved", path=str(output_path))
        
    except Exception as e:
        logger.error("Failed to download wards", error=str(e))
        raise

if __name__ == "__main__":
    main()