"""Extract critical assets and shelter candidates for Chennai from OpenStreetMap.

Outputs
  data/processed/assets.parquet    hospitals, schools, fire/police, pumping stations,
                                   substations, stations — tagged with the ward they sit in
  data/processed/shelters.parquet  named schools / colleges / community halls usable as
                                   relief shelters (read by the API's /shelters endpoint)

Usage
  python pipeline/extract_assets.py                 # query Overpass
  python pipeline/extract_assets.py --input f.json  # reuse a saved Overpass response

No synthetic fallback on purpose: if OSM can't be reached the script fails, so a demo
never silently ships made-up infrastructure.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import geopandas as gpd
import httpx
import pandas as pd
import structlog
from shapely.geometry import Point

logger = structlog.get_logger()

# Overpass bbox order is south, west, north, east (same area as extract_osm.py).
BBOX = "12.8,80.0,13.3,80.35"

OVERPASS_QUERY = f"""
[out:json][timeout:180];
(
  nwr["amenity"~"^(hospital|clinic|school|college|university|fire_station|police|community_centre)$"]({BBOX});
  nwr["emergency"="assembly_point"]({BBOX});
  nwr["man_made"~"^(pumping_station|water_works|wastewater_plant)$"]({BBOX});
  nwr["power"="substation"]({BBOX});
  nwr["railway"="station"]({BBOX});
  nwr["amenity"="bus_station"]({BBOX});
);
out center tags;
"""

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
# overpass-api.de answers 406 to clients without a descriptive User-Agent.
HEADERS = {"User-Agent": "ward-flood-predictor/0.1 (hackathon prototype; github.com/Polycoded/ward-level-flood-predictor)"}

WARDS_PATH = Path("data/processed/wards.geojson")
RAW_PATH = Path("data/raw/osm_assets.json")
ASSETS_PATH = Path("data/processed/assets.parquet")
SHELTERS_PATH = Path("data/processed/shelters.parquet")

# (tag key, tag value) -> (asset_type, category)
ASSET_TYPES: dict[tuple[str, str], tuple[str, str]] = {
    ("amenity", "hospital"): ("hospital", "critical_care"),
    ("amenity", "clinic"): ("clinic", "critical_care"),
    ("amenity", "fire_station"): ("fire_station", "emergency_services"),
    ("amenity", "police"): ("police", "emergency_services"),
    ("amenity", "school"): ("school", "shelter_candidate"),
    ("amenity", "college"): ("college", "shelter_candidate"),
    ("amenity", "university"): ("university", "shelter_candidate"),
    ("amenity", "community_centre"): ("community_centre", "shelter_candidate"),
    ("emergency", "assembly_point"): ("assembly_point", "shelter_candidate"),
    ("man_made", "pumping_station"): ("pumping_station", "drainage_utility"),
    ("man_made", "water_works"): ("water_works", "drainage_utility"),
    ("man_made", "wastewater_plant"): ("wastewater_plant", "drainage_utility"),
    ("power", "substation"): ("substation", "power"),
    ("railway", "station"): ("railway_station", "transport"),
    ("amenity", "bus_station"): ("bus_station", "transport"),
}

# OSM has no capacity data for these; rough planning numbers, documented in docs/assumptions.md.
SHELTER_CAPACITY = {
    "school": 300,
    "college": 500,
    "university": 800,
    "community_centre": 200,
    "assembly_point": 150,
}


def fetch_overpass(query: str = OVERPASS_QUERY, attempts: int = 6) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        url = OVERPASS_URLS[attempt % len(OVERPASS_URLS)]
        try:
            logger.info("Querying Overpass", url=url, attempt=attempt + 1)
            response = httpx.post(url, data={"data": query}, headers=HEADERS, timeout=240.0)
            response.raise_for_status()
            data = response.json()
            # some mirrors answer 200 with an empty result when their database is stale
            if not data.get("elements"):
                raise ValueError("empty result")
            return data
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            logger.warning("Overpass request failed", url=url, error=str(exc))
            time.sleep(min(30, 5 * (attempt + 1)))
    raise RuntimeError(f"Overpass unavailable after {attempts} attempts: {last_error}")


def classify(tags: dict[str, str]) -> tuple[str, str] | None:
    for (key, value), result in ASSET_TYPES.items():
        if tags.get(key) == value:
            return result
    return None


def element_location(element: dict[str, Any]) -> tuple[float, float] | None:
    """Nodes carry lat/lon; ways and relations carry a `center` with `out center`."""
    if "lat" in element and "lon" in element:
        return float(element["lat"]), float(element["lon"])
    center = element.get("center")
    if center and "lat" in center and "lon" in center:
        return float(center["lat"]), float(center["lon"])
    return None


def parse_assets(data: dict[str, Any]) -> gpd.GeoDataFrame:
    rows = []
    seen: set[tuple[str, int]] = set()
    for element in data.get("elements", []):
        key = (element.get("type", ""), int(element.get("id", 0)))
        if key in seen:
            continue
        tags = element.get("tags") or {}
        kind = classify(tags)
        location = element_location(element)
        if kind is None or location is None:
            continue
        seen.add(key)
        lat, lon = location
        asset_type, category = kind
        rows.append(
            {
                "osm_type": key[0],
                "osm_id": key[1],
                "name": (tags.get("name:en") or tags.get("name") or "").strip(),
                "asset_type": asset_type,
                "category": category,
                "latitude": lat,
                "longitude": lon,
                "geometry": Point(lon, lat),
            }
        )

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326") if rows else gpd.GeoDataFrame(
        columns=["osm_type", "osm_id", "name", "asset_type", "category", "latitude", "longitude", "geometry"],
        geometry="geometry",
        crs="EPSG:4326",
    )
    gdf = gdf.sort_values(["category", "asset_type", "osm_id"]).reset_index(drop=True)
    gdf.insert(0, "asset_id", range(1, len(gdf) + 1))
    return gdf


def assign_wards(assets: gpd.GeoDataFrame, wards: gpd.GeoDataFrame | None) -> gpd.GeoDataFrame:
    """Tag each asset with the ward polygon containing it; assets outside every ward are dropped."""
    if wards is None or len(wards) == 0:
        logger.warning("No ward boundaries available; assets keep ward_id = None")
        assets = assets.copy()
        assets["ward_id"] = pd.array([None] * len(assets), dtype="Int64")
        return assets

    wards_wgs84 = wards[["ward_id", "geometry"]].to_crs("EPSG:4326")
    joined = gpd.sjoin(assets, wards_wgs84, how="inner", predicate="within")
    joined = joined.drop(columns=["index_right"]).drop_duplicates(subset="asset_id")
    joined["ward_id"] = joined["ward_id"].astype("Int64")
    dropped = len(assets) - len(joined)
    if dropped:
        logger.info("Dropped assets outside ward boundaries", count=dropped)
    return joined.reset_index(drop=True)


def build_shelters(assets: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    candidates = assets[(assets["category"] == "shelter_candidate") & (assets["name"] != "")].copy()
    candidates["capacity"] = candidates["asset_type"].map(SHELTER_CAPACITY).fillna(150).astype(int)
    candidates = candidates.reset_index(drop=True)
    candidates["shelter_id"] = range(1, len(candidates) + 1)
    columns = ["shelter_id", "name", "asset_type", "latitude", "longitude", "capacity", "ward_id", "osm_id", "geometry"]
    return gpd.GeoDataFrame(candidates[[c for c in columns if c in candidates.columns]], geometry="geometry", crs="EPSG:4326")


def load_wards(path: Path = WARDS_PATH) -> gpd.GeoDataFrame | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    return gpd.read_file(path)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, help="saved Overpass JSON to use instead of querying")
    args = parser.parse_args(argv)

    if args.input:
        data = json.loads(args.input.read_text())
    else:
        data = fetch_overpass()
        RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
        RAW_PATH.write_text(json.dumps(data))

    assets = assign_wards(parse_assets(data), load_wards())
    shelters = build_shelters(assets)

    ASSETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    assets.to_parquet(ASSETS_PATH)
    shelters.to_parquet(SHELTERS_PATH)
    logger.info(
        "Assets extracted",
        assets=len(assets),
        shelters=len(shelters),
        by_category=assets["category"].value_counts().to_dict(),
    )


if __name__ == "__main__":
    main()
