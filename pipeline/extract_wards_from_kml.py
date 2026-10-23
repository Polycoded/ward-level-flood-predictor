<<<<<<< Updated upstream
#!/usr/bin/env python3
"""
Extract 200 Chennai wards from official GCC KML 2022 and assign zones.
Produces: data/processed/wards.geojson, data/processed/ward_crosswalk.csv

This script reproduces the exact delivered artifacts at commit 40598b1.
=======
"""Convert supplied GCC KMLs with explicit IDs; never overwrite outputs by default.

Source row order defines internal IDs and must be frozen with the source hashes.
This conversion does not certify legal vintage or resolve between-ward overlaps.
>>>>>>> Stashed changes
"""
from pathlib import Path
import argparse

import geopandas as gpd


def prepare_wards(wards, zones, *, repair_invalid=False):
    if wards.crs is None or zones.crs is None:
        raise ValueError("Both source layers need declared CRS")
    wards = wards.copy()
    zones = zones.copy()
    for name, layer in (("Ward", wards), ("Zone", zones)):
        if layer.geometry.isna().any() or layer.geometry.is_empty.any():
            raise ValueError(f"{name} geometry is missing")
        if not layer.geom_type.isin(["Polygon", "MultiPolygon"]).all():
            raise ValueError(f"{name} geometry must be polygonal")
        if not layer.geometry.is_valid.all():
            if not repair_invalid:
                raise ValueError(f"Invalid source {name.lower()}s; acknowledge repair explicitly")
            layer.geometry = layer.geometry.buffer(0)
        if not layer.geometry.is_valid.all() or layer.geometry.is_empty.any():
            raise ValueError(f"{name} repair produced invalid or empty geometry")
    numbers = wards["Name"].str.extract(r"^\s*(\d+)\s*$", expand=False)
    if numbers.isna().any():
        raise ValueError("Ward Name must contain only an official ward number")
    wards["ward_number"] = numbers.astype(int)
    if len(wards) != 200 or set(wards.ward_number) != set(range(1, 201)):
        raise ValueError("Expected unique official ward numbers 1–200")
    wards["ward_id"] = range(1, len(wards) + 1)
    wards["ward_name"] = "Ward " + wards.ward_number.astype(str)
    if wards.geometry.isna().any() or wards.geometry.is_empty.any():
        raise ValueError("Ward geometry is missing")
    if not wards.geometry.is_valid.all():
        if not repair_invalid:
            raise ValueError("Invalid source wards; review before opting into buffer(0) repair")
        wards.geometry = wards.geometry.buffer(0)
    wards_utm = wards.to_crs("EPSG:32644")
    zones_utm = zones.to_crs("EPSG:32644")
    intersections = gpd.overlay(
        wards_utm[["ward_id", "geometry"]],
        zones_utm[["ZONE", "ZONE_NAME", "geometry"]],
        how="intersection", keep_geom_type=False,
    )
    intersections["overlap_area"] = intersections.geometry.area
    intersections = intersections[intersections.overlap_area > 0]
    # Aggregate multipart pieces of each zone before choosing largest overlap.
    areas = intersections.groupby(["ward_id", "ZONE", "ZONE_NAME"], dropna=False,
                                  as_index=False).overlap_area.sum()
    chosen = areas.sort_values(["overlap_area", "ZONE"], ascending=[False, True]).drop_duplicates("ward_id")
    result = wards_utm.drop(columns=["ZONE", "ZONE_NAME"], errors="ignore").merge(
        chosen[["ward_id", "ZONE", "ZONE_NAME"]], on="ward_id", how="left", validate="one_to_one"
    ).sort_values("ward_id")
    if result[["ZONE", "ZONE_NAME"]].isna().any().any():
        raise ValueError("Every ward needs a zone assignment")
    if not result.geometry.is_valid.all() or result.geometry.is_empty.any():
        raise ValueError("Conversion produced invalid or empty geometry")
    result["area_sqkm"] = result.geometry.area / 1e6
    crosswalk = result[["ward_id", "ward_number", "ward_name", "ZONE", "ZONE_NAME"]].rename(
        columns={"ZONE": "zone_number", "ZONE_NAME": "zone_name"}
    ).copy()
    crosswalk["source"] = "chennai_gcc_kml_2022"
    return result, crosswalk


<<<<<<< Updated upstream
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
=======
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wards-kml", type=Path, default=Path("data/raw/Chennai GCC Ward Map - 2022.kml"))
    parser.add_argument("--zones-kml", type=Path, default=Path("data/raw/Chennai GCC Zones Map - 2022.kml"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repair-invalid", action="store_true")
    args = parser.parse_args(argv)
    paths = [args.output_dir / "wards.geojson", args.output_dir / "ward_crosswalk.csv"]
    if any(path.exists() for path in paths):
        parser.error("Output files already exist; choose a new review directory")
    wards, crosswalk = prepare_wards(gpd.read_file(args.wards_kml), gpd.read_file(args.zones_kml),
                                   repair_invalid=args.repair_invalid)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    wards.to_file(paths[0], driver="GeoJSON")
    crosswalk.to_csv(paths[1], index=False)


if __name__ == "__main__":
    main()
>>>>>>> Stashed changes
