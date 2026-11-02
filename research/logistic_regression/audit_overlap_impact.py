"""Quantify whether ward-polygon overlaps materially affect labels, features or folds.

Diagnostic only. Original geometries are never repaired, clipped or reassigned.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd
from audit_geometry import build_overlap_table
from spatial_common import write_json

METRIC_CRS = "EPSG:32644"


def _records(frame: pd.DataFrame) -> list[dict]:
    clean = frame.astype(object).where(pd.notna(frame), None)
    return clean.to_dict("records")


def load_fold_map(path: Path) -> dict:
    folds = pd.read_csv(path)
    if "ward_id" not in folds.columns or "unit" not in folds.columns:
        raise ValueError(f"{path} must contain ward_id and unit")
    folds["ward_id"] = pd.to_numeric(folds["ward_id"], errors="raise").astype(int)
    if folds["ward_id"].duplicated().any():
        raise ValueError(f"Duplicate ward_id in {path}")
    return dict(zip(folds["ward_id"], folds["unit"].astype(str)))


def audit(wards_path: Path, dataset_path: Path, zone_fold_path: Path,
          quadrant_fold_path: Path, underpasses_path: Path | None,
          output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    wards = gpd.read_file(wards_path)
    if wards.crs is None:
        raise ValueError("Ward file has no CRS")
    metric = wards.to_crs(METRIC_CRS)
    areas = dict(zip(metric["ward_id"].astype(int), metric.geometry.area))
    numbers = dict(zip(metric["ward_id"].astype(int),
                       metric["ward_number"].astype(str)))

    dataset = pd.read_csv(dataset_path)
    detections = dataset.groupby("ward_id")["experimental_proxy_target"].sum()
    positives = set(detections[detections > 0].index.astype(int))

    zone_folds = load_fold_map(zone_fold_path)
    quadrant_folds = load_fold_map(quadrant_fold_path)

    underpasses = None
    if underpasses_path and Path(underpasses_path).exists():
        underpasses = gpd.read_file(underpasses_path)
        if underpasses.crs is None:
            raise ValueError("Underpass file has no CRS")
        underpasses = underpasses.to_crs(METRIC_CRS)

    overlaps, summary = build_overlap_table(metric)
    geometries = dict(zip(metric["ward_id"].astype(int), metric.geometry))
    rows = []
    underpass_ids: set = set()
    for record in overlaps:
        a, b = record["ward_id_a"], record["ward_id_b"]
        intersection = geometries[a].intersection(geometries[b])
        underpass_count = 0
        if underpasses is not None and not intersection.is_empty:
            matched = underpasses.loc[underpasses.intersects(intersection)]
            underpass_count = int(len(matched))
            underpass_ids |= set(matched.index.tolist())
        zone_a, zone_b = zone_folds.get(a), zone_folds.get(b)
        quad_a, quad_b = quadrant_folds.get(a), quadrant_folds.get(b)
        positive_a, positive_b = a in positives, b in positives
        rows.append({
            **record,
            "ward_number_a": numbers.get(a, record["ward_number_a"]),
            "ward_number_b": numbers.get(b, record["ward_number_b"]),
            "fraction_of_ward_a": record["intersection_area_m2"] / areas[a],
            "fraction_of_ward_b": record["intersection_area_m2"] / areas[b],
            "zone_a": zone_a,
            "zone_b": zone_b,
            "quadrant_a": quad_a,
            "quadrant_b": quad_b,
            "split_across_zone_folds": bool(zone_a != zone_b),
            "split_across_quadrant_folds": bool(quad_a != quad_b),
            "positive_a": positive_a,
            "positive_b": positive_b,
            "both_positive": bool(positive_a and positive_b),
            "one_positive": bool(positive_a != positive_b),
            "underpasses_in_overlap": underpass_count,
        })
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame.to_csv(output / "overlap_impact_pairs.csv", index=False)

    substantial = frame.loc[frame["is_substantial"]] if not frame.empty else frame
    positive_all = frame.loc[frame["positive_a"] | frame["positive_b"]] \
        if not frame.empty else frame
    positive_pairs = positive_all.loc[positive_all["is_substantial"]] \
        if not positive_all.empty else positive_all
    report = {
        "wards_path": str(wards_path),
        "dataset_path": str(dataset_path),
        "crs": METRIC_CRS,
        "summary": summary,
        "substantial_pairs": int(len(substantial)),
        "pairs_split_across_zone_folds": int(
            substantial["split_across_zone_folds"].sum()) if not substantial.empty else 0,
        "pairs_split_across_quadrant_folds": int(
            substantial["split_across_quadrant_folds"].sum()) if not substantial.empty else 0,
        "positive_overlap_pairs": int(len(positive_pairs)),
        "positive_overlap_pairs_including_artifacts": int(len(positive_all)),
        "positive_overlap_artifact_pairs": int(
            len(positive_all) - len(positive_pairs)),
        "both_positive_pairs": int(positive_pairs["both_positive"].sum())
        if not positive_pairs.empty else 0,
        "one_positive_pairs": int(positive_pairs["one_positive"].sum())
        if not positive_pairs.empty else 0,
        "positive_pairs_split_zone": int(
            positive_pairs["split_across_zone_folds"].sum())
        if not positive_pairs.empty else 0,
        "positive_pairs_split_quadrant": int(
            positive_pairs["split_across_quadrant_folds"].sum())
        if not positive_pairs.empty else 0,
        "pairs_with_underpasses": int((frame["underpasses_in_overlap"] > 0).sum())
        if not frame.empty else 0,
        "unique_underpasses_in_overlaps": len(underpass_ids),
        "unique_underpasses_total": int(len(underpasses)) if underpasses is not None else None,
        "total_substantial_overlap_area_m2": float(
            substantial["intersection_area_m2"].sum()) if not substantial.empty else 0.0,
        "max_single_overlap_m2": float(substantial["intersection_area_m2"].max())
        if not substantial.empty else 0.0,
        "ward_27_28_overlap": next(
            (row for row in _records(frame)
             if {row["ward_id_a"], row["ward_id_b"]} == {27, 28}),
            None),
        "positive_ward_overlaps": _records(positive_pairs.head(20))
        if not positive_pairs.empty else [],
        "interpretation": [
            "Split folds indicate that one physical overlap area appears in both "
            "training and held-out geography.",
            "Area and underpass counts are quantified; zonal DEM/LULC statistics were "
            "not recomputed for overlap correction.",
            "No area was transferred between wards. The overlap remains unresolved.",
        ],
    }
    write_json(output / "overlap_impact.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wards", type=Path,
                        default=Path("data/processed/wards.geojson"))
    parser.add_argument("--dataset", type=Path,
                        default=Path("research/logistic_regression/results/spatial_eval/dataset_used.csv"))
    parser.add_argument("--zone-folds", type=Path,
                        default=Path("research/logistic_regression/results/spatial_eval/fold_assignments_zone.csv"))
    parser.add_argument("--quadrant-folds", type=Path,
                        default=Path("research/logistic_regression/results/spatial_eval/fold_assignments_quadrant.csv"))
    parser.add_argument("--underpasses", type=Path,
                        default=Path("data/processed/underpasses.gpkg"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.wards, args.dataset, args.zone_folds, args.quadrant_folds,
                   args.underpasses, args.output)
    print(f"substantial={report['substantial_pairs']} "
          f"split_zone={report['pairs_split_across_zone_folds']} "
          f"split_quadrant={report['pairs_split_across_quadrant_folds']} "
          f"positive_pairs={report['positive_overlap_pairs']} "
          f"both_positive={report['both_positive_pairs']} "
          f"underpasses_in_overlaps={report['unique_underpasses_in_overlaps']}")


if __name__ == "__main__":
    main()
