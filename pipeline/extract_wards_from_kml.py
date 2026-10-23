#!/usr/bin/env python3
"""Convert supplied GCC KMLs with explicit IDs; never overwrite outputs by default.

Source row order defines internal IDs and must be frozen with the source hashes.
This conversion does not certify legal vintage or resolve between-ward overlaps.
"""
import argparse
from pathlib import Path

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
