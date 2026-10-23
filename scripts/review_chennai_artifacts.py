"""Read-only Chennai artifact audit; stdout JSON, no data writes or attestations."""
import argparse
import hashlib
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


def audit(review_dir):
    root = Path(__file__).resolve().parents[1]
    processed = root / "data/processed"
    wards = gpd.read_file(processed / "wards.geojson").sort_values("ward_id").set_index("ward_id")
    converted = gpd.read_file(review_dir / "wards.geojson").sort_values("ward_id").set_index("ward_id")
    if wards.crs != converted.crs or wards.crs.to_epsg() != 32644:
        raise ValueError("Review requires matching declared EPSG:32644 layers for metre diagnostics")
    crosswalk = pd.read_csv(processed / "ward_crosswalk.csv").set_index("ward_id")
    new_crosswalk = pd.read_csv(review_dir / "ward_crosswalk.csv").set_index("ward_id")
    tables = {name: pd.read_parquet(processed / f"{name}.parquet").set_index("ward_id")
              for name in ("features", "zonal_stats")}
    files = sorted((root / "data/raw").glob("*.kml")) + [
        processed / name for name in ("wards.geojson", "ward_crosswalk.csv", "features.parquet",
                                     "zonal_stats.parquet", "validation_metrics.json", "validation_labels.csv",
                                     "roads.gpkg", "water.gpkg", "underpasses.gpkg")]
    hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    identity = {}
    for name, frame in {"crosswalk": crosswalk, "converted": converted,
                        "converted_crosswalk": new_crosswalk, **tables}.items():
        common = wards.index.intersection(frame.index)
        identity[name] = {"rows": len(frame), "unique_ids": bool(frame.index.is_unique),
                          "missing_ids": sorted(set(wards.index) - set(frame.index)),
                          "extra_ids": sorted(set(frame.index) - set(wards.index)),
                          "official_mismatches": [int(i) for i in common
                              if int(wards.loc[i, "ward_number"]) != int(frame.loc[i, "ward_number"])]}
    ranges = {}
    for name, frame in tables.items():
        ranges[name] = {}
        for field in ("elevation_mean", "slope_mean", "impervious_frac", "dist_to_water_m",
                      "road_density_km_per_sqkm", "underpass_count"):
            values = pd.to_numeric(frame[field], errors="coerce")
            finite = values[np.isfinite(values)]
            ranges[name][field] = {"missing": int(values.isna().sum()),
                "nonfinite": int((~np.isfinite(values)).sum()), "zero_count": int(values.eq(0).sum()),
                "min": float(finite.min()) if len(finite) else None,
                "max": float(finite.max()) if len(finite) else None}
    pairs = []
    ids = list(wards.index)
    for pos, left in enumerate(ids):
        for right in ids[pos + 1:]:
            area = wards.loc[left].geometry.intersection(wards.loc[right].geometry).area
            if area > 0:
                pairs.append({"internal_ids": [int(left), int(right)], "area_m2": area})
    differences = []
    for ident in wards.index.intersection(converted.index):
        old, new = wards.loc[ident], converted.loc[ident]
        area = old.geometry.symmetric_difference(new.geometry).area
        if not old.geometry.equals(new.geometry) or old.ZONE != new.ZONE or old.ZONE_NAME != new.ZONE_NAME:
            differences.append({"ward_id": int(ident), "official_number": int(old.ward_number),
                "geometry_equal": old.geometry.equals(new.geometry), "symmetric_difference_m2": area,
                "old_zone": old.ZONE, "new_zone": new.ZONE,
                "old_zone_name": old.ZONE_NAME, "new_zone_name": new.ZONE_NAME})
    union = wards.geometry.union_all()
    geometries = {}
    for name in tables:
        if "geometry" not in tables[name]:
            geometries[name] = {"status": "no_geometry_column"}
            continue
        layer = gpd.read_parquet(processed / f"{name}.parquet").set_index("ward_id")
        geometries[name] = {"crs_matches": layer.crs == wards.crs,
            "unequal_geometry_ids": [int(i) for i in wards.index
                                     if not wards.loc[i].geometry.equals(layer.loc[i].geometry)]}
    return {"interpretation": "Structural consistency only; no source authenticity, coverage or historical approval.",
        "hashes_sha256": hashes, "declared_crs": str(wards.crs), "identity": identity,
        "required_features": ranges, "parquet_geometry_agreement": geometries,
        "source_invalid_wards": int((~gpd.read_file(root / "data/raw/Chennai GCC Ward Map - 2022.kml").geometry.is_valid).sum()),
        "valid_polygons": int(wards.geometry.is_valid.sum()),
        "overlaps": {"positive_area_pairs": len(pairs), "pairs_over_1_m2": sum(p['area_m2'] > 1 for p in pairs),
                     "sum_area_m2": float(wards.geometry.area.sum()), "union_area_m2": union.area,
                     "largest_pairs": sorted(pairs, key=lambda p: -p['area_m2'])[:10]},
        "conversion": {"review_directory": str(review_dir), "repair_acknowledged": None,
                       "repair_acknowledgement_status": "unverified_from_directory",
                       "compared_ids": len(wards.index.intersection(converted.index)),
                       "unequal_geometry_count": sum(not d['geometry_equal'] for d in differences),
                       "max_symmetric_difference_m2": max((d['symmetric_difference_m2'] for d in differences), default=0),
                       "zone_difference_count": sum(d['old_zone'] != d['new_zone'] or d['old_zone_name'] != d['new_zone_name'] for d in differences),
                       "differences": differences},
        "canonical_crosswalk_zone_mismatches": [int(i) for i in wards.index
            if wards.loc[i, 'ZONE'] != crosswalk.loc[i, 'zone_number'] or
            wards.loc[i, 'ZONE_NAME'] != crosswalk.loc[i, 'zone_name']]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.review_dir), indent=2, allow_nan=False))
