#!/usr/bin/env python3
"""
Extract 200 Chennai wards from official GCC KML 2022 and assign zones.
Produces: data/processed/wards.geojson, data/processed/ward_crosswalk.csv

This script reproduces the exact delivered artifacts at commit 40598b1.
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

    # Assign ward_id sequentially by KML feature order (1..200)
    # This matches the delivered wards.geojson where ward_id=1 corresponds to KML feature 0 (ward 168)
    wards['ward_id'] = range(1, len(wards) + 1)

    # Compute area in square km (in UTM CRS)
    wards_utm = wards.to_crs('EPSG:32644')
    wards['area_sqkm'] = wards_utm.geometry.area / 1_000_000

    # Save wards with required columns in correct order
    ward_cols = [
        'id', 'Name', 'description', 'timestamp', 'begin', 'end', 'altitudeMode',
        'tessellate', 'extrude', 'visibility', 'drawOrder', 'icon', 'id_2', 'name2',
        'ward_number', 'ward_name', 'ZONE', 'ZONE_NAME', 'ward_id', 'area_sqkm', 'geometry'
    ]
    # Keep only columns that exist
    existing_cols = [c for c in ward_cols if c in wards.columns]
    wards[existing_cols].to_crs('EPSG:32644').to_file(WARDS_OUT, driver='GeoJSON')
    print(f"Saved wards: {len(wards)} features")

    # Crosswalk - match exact delivered column order and values
    crosswalk = pd.DataFrame({
        'ward_id': wards['ward_id'],
        'ward_number': wards['ward_number'],
        'ward_name': wards['ward_name'],
        'zone_number': wards['ZONE'],
        'zone_name': wards['ZONE_NAME'],
        'source': 'chennai_gcc_kml_2022'
    })
    crosswalk.to_csv(CROSSWALK_OUT, index=False)
    print(f"Saved crosswalk: {len(crosswalk)} rows")

    # Zone distribution
    print("Zone distribution:")
    print(wards.groupby(['ZONE', 'ZONE_NAME']).size().to_string())


if __name__ == "__main__":
    import pandas as pd
    main()