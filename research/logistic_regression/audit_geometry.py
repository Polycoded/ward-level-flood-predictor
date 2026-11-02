"""Reproducible geometry, identity and overlap audit for the ward dataset.

The audit is diagnostic. It never repairs, clips or reassigns canonical geometries.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon
from shapely.ops import unary_union
from spatial_common import write_json

METRIC_CRS = "EPSG:32644"
ARTIFACT_AREA_M2 = 1.0


def build_overlap_table(wards: gpd.GeoDataFrame) -> tuple[list[dict], dict]:
    geometries = wards.geometry.to_numpy()
    ids = wards["ward_id"].to_numpy()
    numbers = wards["ward_number"].astype(str).to_numpy()
    records: list[dict] = []
    errors = []
    for i in range(len(geometries)):
        for j in range(i + 1, len(geometries)):
            first, second = geometries[i], geometries[j]
            try:
                if not first.intersects(second):
                    continue
                intersection = first.intersection(second)
                area = float(intersection.area)
            except Exception as exc:  # noqa: BLE001 - record, never repair
                errors.append({"ward_id_a": int(ids[i]), "ward_id_b": int(ids[j]),
                               "error": str(exc)})
                continue
            if area <= 0:
                continue
            min_area = min(float(first.area), float(second.area))
            union_area = float(first.area) + float(second.area) - area
            records.append({
                "ward_id_a": int(ids[i]),
                "ward_id_b": int(ids[j]),
                "ward_number_a": numbers[i],
                "ward_number_b": numbers[j],
                "intersection_area_m2": area,
                "relative_to_smaller_area": area / min_area if min_area > 0 else None,
                "relative_to_pair_union": area / union_area if union_area > 0 else None,
                "is_numerical_artifact": bool(area <= ARTIFACT_AREA_M2),
                "is_substantial": bool(area > ARTIFACT_AREA_M2),
            })
    records.sort(key=lambda row: row["intersection_area_m2"], reverse=True)
    summary = {
        "positive_area_pairs": len(records),
        "pairs_gt_1m2": int(sum(row["is_substantial"] for row in records)),
        "pairs_le_1m2": int(sum(row["is_numerical_artifact"] for row in records)),
        "sum_pairwise_overlap_m2": float(sum(
            row["intersection_area_m2"] for row in records)),
        "max_overlap_m2": float(records[0]["intersection_area_m2"]) if records else 0.0,
        "intersection_errors": errors,
    }
    return records, summary


def audit_geometry(wards_path: Path, crosswalk_path: Path, dataset_path: Path,
                   output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    wards = gpd.read_file(wards_path)
    if "ward_id" not in wards.columns or "geometry" not in wards.columns:
        raise ValueError("ward file must contain ward_id and geometry")
    for column in ["ward_id", "ward_number"]:
        if column not in wards.columns:
            raise ValueError(f"ward file must contain {column}")
    original_crs = None if wards.crs is None else str(wards.crs)
    metric = wards.to_crs(METRIC_CRS)
    invalid_mask = ~metric.geometry.is_valid
    empty_mask = metric.geometry.is_empty
    duplicate_ward_ids = int(metric["ward_id"].duplicated().sum())
    duplicate_ward_numbers = int(metric["ward_number"].astype(str).duplicated().sum())

    area_sum = float(metric.geometry.area.sum())
    union_area = None
    interior_rings = []
    interior_area = None
    union_error = None
    valid_geometries = metric.geometry[metric.geometry.is_valid]
    try:
        union = unary_union(valid_geometries.tolist()) if len(valid_geometries) else None
        if union is not None:
            union_area = float(union.area)
            holes = [polygon.interiors for polygon in getattr(union, "geoms", [union])]
            interior_rings = [ring for group in holes for ring in group]
            interior_area = float(sum(Polygon(ring).area for ring in interior_rings))
    except Exception as exc:  # noqa: BLE001 - record, never repair
        union_error = str(exc)

    overlaps, overlap_summary = build_overlap_table(metric)

    dataset = pd.read_csv(dataset_path)
    positive_wards = sorted(dataset.loc[
        dataset["experimental_proxy_target"] == 1, "ward_id"].unique().tolist())
    dataset_wards = set(dataset["ward_id"].unique().tolist())
    ward_ids = set(metric["ward_id"].tolist())
    missing_from_wards = sorted(dataset_wards - ward_ids)
    missing_from_dataset = sorted(ward_ids - dataset_wards)

    crosswalk = pd.read_csv(crosswalk_path)
    crosswalk["ward_id"] = pd.to_numeric(crosswalk["ward_id"], errors="raise").astype(int)
    merged = metric[["ward_id", "ward_number"]].merge(
        crosswalk[["ward_id", "ward_number"]], on="ward_id", how="outer",
        suffixes=("_wards", "_crosswalk"), indicator=True)
    identity_mismatches = merged.loc[
        (merged["_merge"] != "both") |
        (merged["ward_number_wards"].astype(str) !=
         merged["ward_number_crosswalk"].astype(str)),
        ["ward_id", "ward_number_wards", "ward_number_crosswalk", "_merge"],
    ].to_dict("records")

    positive_set = set(positive_wards)
    positive_overlaps = [row for row in overlaps
                         if row["ward_id_a"] in positive_set or row["ward_id_b"] in positive_set]
    overlap_frame = pd.DataFrame(overlaps)
    if not overlap_frame.empty:
        overlap_frame.to_csv(output_dir / "geometry_overlaps.csv", index=False)

    report = {
        "wards_path": str(wards_path),
        "dataset_path": str(dataset_path),
        "crosswalk_path": str(crosswalk_path),
        "declared_crs": original_crs,
        "metric_crs": METRIC_CRS,
        "ward_count": int(len(metric)),
        "invalid_geometries": int(invalid_mask.sum()),
        "invalid_ward_ids": sorted(
            metric.loc[invalid_mask, "ward_id"].astype(int).tolist()),
        "empty_geometries": int(empty_mask.sum()),
        "duplicate_ward_ids": duplicate_ward_ids,
        "duplicate_ward_numbers": duplicate_ward_numbers,
        "area_sum_km2": area_sum / 1e6,
        "union_area_km2": None if union_area is None else union_area / 1e6,
        "area_sum_minus_union_m2": None if union_area is None else area_sum - union_area,
        "union_error": union_error,
        "interior_ring_count": len(interior_rings),
        "interior_ring_area_km2": None if interior_area is None else interior_area / 1e6,
        "overlap_summary": overlap_summary,
        "top_overlaps": overlaps[:20],
        "positive_wards": positive_wards,
        "positive_ward_overlaps": positive_overlaps[:20],
        "positive_wards_with_substantial_overlap": sorted({
            number for row in positive_overlaps if row["is_substantial"]
            for number in [row["ward_id_a"], row["ward_id_b"]]
            if number in positive_set
        }),
        "missing_from_wards": missing_from_wards,
        "missing_from_dataset": missing_from_dataset,
        "identity_mismatches": identity_mismatches,
    }
    write_json(output_dir / "geometry_audit.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wards", type=Path,
                        default=Path("data/processed/wards.geojson"))
    parser.add_argument("--crosswalk", type=Path,
                        default=Path("data/processed/ward_crosswalk.csv"))
    parser.add_argument("--dataset", type=Path,
                        default=Path("research/logistic_regression/dataset.csv"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit_geometry(args.wards, args.crosswalk, args.dataset, args.output)
    summary = report["overlap_summary"]
    print(f"wards={report['ward_count']} invalid={report['invalid_geometries']} "
          f"overlap_pairs>{ARTIFACT_AREA_M2:g}m2={summary['pairs_gt_1m2']} "
          f"sum_overlap_m2={summary['sum_pairwise_overlap_m2']:.1f}")


if __name__ == "__main__":
    main()
