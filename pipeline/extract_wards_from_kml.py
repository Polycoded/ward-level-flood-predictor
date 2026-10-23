#!/usr/bin/env python3
"""
Extract 200 Chennai wards from official GCC KML 2022 and assign zones.
Produces: data/processed/wards.geojson, data/processed/ward_crosswalk.csv
"""

import geopandas as gpd
import re
from pathlib import Path

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

WARDS_KML = RAW_DIR / "Chennai GCC Ward Map - 2022.kml"
ZONES_KML = RAW_DIR / "Chennai GCC Zones Map - 2022.kml"
WARDS_OUT = PROCESSED_DIR / "wards.geojson"
CROSSWALK_OUT = PROCESSED_DIR / "ward_crosswalk.csv"


def main():
    print("Reading KML files...")
    wards = gpd.read_file(WARDS_KML)
    zones = gpd.read_file(ZONES_KML)

    print(f"Wards: {len(wards)} features, CRS: {wards.crs}")
    print(f"Zones: {len(zones)} features, CRS: {zones.crs}")

    # Extract ward number from Name field (format: "\n    168\n   ")
    wards['ward_number'] = wards['Name'].str.extract(r'(\d+)').astype(int)
    wards['ward_name'] = 'Ward ' + wards['ward_number'].astype(str)

    # Ensure CRS
    if wards.crs is None:
        wards = wards.set_crs('EPSG:4326')
    if zones.crs is None:
        zones = zones.set_crs('EPSG:4326')

    # Spatial join by largest overlap
    wards_utm = wards.to_crs('EPSG:32644')
    zones_utm = zones.to_crs('EPSG:32644')

    intersections = gpd.overlay(
        wards_utm, zones_utm[['ZONE', 'ZONE_NAME', 'geometry']],
        how='intersection', keep_geom_type=False
    )
    intersections['area'] = intersections.geometry.area

    max_area_idx = intersections.groupby('ward_number')['area'].idxmax()
    ward_zones = intersections.loc[max_area_idx][['ward_number', 'ZONE', 'ZONE_NAME']]

    wards = wards.merge(ward_zones, on='ward_number', how='left')

    # Repair invalid geometries (9/200 had self-intersections)
    wards['geometry'] = wards.geometry.buffer(0)

    # Save wards
    wards.to_crs('EPSG:32644').to_file('data/processed/wards.geojson', driver='GeoJSON')
    print(f"Saved wards: {len(wards)} features")

    # Crosswalk
    crosswalk = wards[['ward_number', 'ZONE', 'ZONE_NAME']].copy()
    crosswalk['ward_id'] = range(1, 201)
    crosswalk['ward_name'] = 'Ward ' + crosswalk['ward_number'].astype(str)
    crosswalk.columns = ['ward_id', 'ward_number', 'ward_name', 'zone_number', 'zone_name']
    crosswalk['source'] = 'chennai_gcc_kml_2022'
    crosswalk.to_csv('data/processed/ward_crosswalk.csv', index=False)
    print(f"Saved crosswalk: {len(crosswalk)} rows")

    # Zone distribution
    print("Zone distribution:")
    print(wards.groupby(['ZONE', 'ZONE_NAME']).size().to_string())


if __name__ == "__main__":
    main()