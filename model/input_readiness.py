"""Read-only structural input diagnostics, not geographic or historical verification."""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import geopandas as gpd
import pandas as pd

from model.evaluation_runner import FEATURES, ROOT, _csv
from model.risk_engine import effective_inputs
from model.validation import _strict_json, _ward_id, load_validation_metrics


def _blank(value):
    return pd.isna(value) or not str(value).strip()


def _identity(frame, official_column):
    ids, missing, invalid = [], [], []
    for pos, value in enumerate(frame.get("ward_id", pd.Series([None] * len(frame)))):
        try:
            ids.append(_ward_id(value))
        except ValueError:
            (missing if _blank(value) else invalid).append(pos)
    numbers = frame.get(official_column, pd.Series([None] * len(frame))).tolist()
    nonblank = [str(value) for value in numbers if not _blank(value)]
    return {"missing_id_rows": missing, "invalid_id_rows": invalid,
            "duplicate_ids": sorted(value for value, count in Counter(ids).items() if count > 1),
            "blank_official_number_rows": [i for i, value in enumerate(numbers) if _blank(value)],
            "duplicate_official_numbers": sorted(value for value, count in Counter(nonblank).items() if count > 1)}, ids, numbers



def _overlap_diagnostics(wards, geometry_issues):
    """Positive-area intersections only; touching edges are allowed.

    Row positions are zero-based. No area units or geographic truth are inferred
    from a CRS declaration. Warnings do not certify or repair the partition.
    """
    if any(geometry_issues.values()):
        return {"status": "not_assessed", "reason": "Resolve invalid, empty or missing geometries first."}
    pairs = []
    for left, geom in enumerate(wards.geometry):
        for right in sorted(wards.sindex.query(geom, predicate="intersects")):
            right = int(right)
            if right > left and geom.intersection(wards.geometry.iloc[right]).area > 0:
                pairs.append({"rows": [left, right],
                              "ward_ids": [str(wards.iloc[left].get("ward_id")),
                                           str(wards.iloc[right].get("ward_id"))]})
    return {"status": "review_required" if pairs else "no_positive_area_overlap_detected",
            "pair_count": len(pairs), "pairs": pairs,
            "limitations": "No tolerance applied; tiny slivers may reflect precision. Does not assess gaps, coverage, source fidelity or historical applicability."}


def inspect_inputs(boundary: Path, features: Path | None = None, metrics: Path | None = None,
                   *, boundary_version: str = "", identity_reference: str = "",
                   administrative_unit: str = "ward") -> dict:
    blockers = []
    result = {"boundary": {}, "features": {}, "metrics": {}, "blockers": blockers,
              "attestations": {"boundary_version": boundary_version, "identity_reference": identity_reference},
              "limitations": ["Readiness is structural plus caller attestations, not verified geographic coverage or historical accuracy.",
                              "Finite measurements and valid zeros cannot prove upstream missingness was preserved.",
                              "Feature provenance still requires the runner configuration and local review."],
              "historical_evaluation_ready": False,
              "historical_blockers": ["Reviewed ward-aligned observations and supported rainfall metadata must pass the schema-2.0 evaluator; not assessed by this check."]}
    boundary_ids, boundary_numbers = [], []
    boundary_ok = False
    try:
        raw = json.loads(Path(boundary).read_text())
        result["boundary"]["declared_crs"] = raw.get("crs")
        result["boundary"]["crs_note"] = ("CRS declaration is caller metadata, not independent verification" if raw.get("crs") else
                                           "Absent declaration relies on GeoJSON WGS84 convention; not independent verification")
        wards = gpd.GeoDataFrame.from_features(raw["features"])
        issues, boundary_ids, boundary_numbers = _identity(wards, "ward_number")
        geometry_issues = {"missing_geometry_rows": [], "empty_geometry_rows": [], "invalid_geometry_rows": []}
        for i, geom in enumerate(wards.geometry):
            if geom is None:
                geometry_issues["missing_geometry_rows"].append(i)
            elif geom.is_empty:
                geometry_issues["empty_geometry_rows"].append(i)
            elif not geom.is_valid or geom.geom_type not in ("Polygon", "MultiPolygon"):
                geometry_issues["invalid_geometry_rows"].append(i)
        result["boundary"]["overlap_review"] = _overlap_diagnostics(wards, geometry_issues)
        zones = [str(name) for name in wards.get("ward_name", []) if re.search(r"\bzone\b", str(name), re.I)]
        result["boundary"].update(record_count=len(wards), **issues, **geometry_issues,
                                  zone_name_signals=zones if administrative_unit == "ward" else [])
        boundary_ok = bool(len(wards)) and not any(issues.values()) and not any(geometry_issues.values())
        if administrative_unit == "ward" and zones:
            boundary_ok = False
            blockers.append("Boundary names explicitly identify zones, not requested wards; John must verify/replace the boundary layer.")
        if not boundary_ok:
            blockers.append("Resolve boundary identity/official-number/geometry issues with a frozen reviewed ward layer.")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        blockers.append(f"Boundary unavailable/unreadable: {exc}; supply a nonempty GeoJSON FeatureCollection.")
    attested = bool(boundary_version.strip() and identity_reference.strip())
    if not attested:
        blockers.append("Supply reviewed boundary_version and identity_reference/crosswalk; identifiers alone do not establish truth.")
    result["identity_ready"] = boundary_ok and attested
    feature_ok = False
    try:
        if features is None:
            raise ValueError("feature path not supplied")
        path = Path(features)
        if not path.is_file():
            raise ValueError(f"feature artifact absent: {path}")
        frame = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else _csv(path.read_bytes(), "features")
        official = "official_number" if "official_number" in frame else "ward_number"
        issues, ids, numbers = _identity(frame, official)
        missing_columns = sorted(set(FEATURES) - set(frame.columns))
        invalid = []
        for i, row in enumerate(frame.to_dict("records")):
            for name in FEATURES:
                try:
                    value = row.get(name)
                    # CSV numbers require parsing; preserve strict boolean rejection for Parquet.
                    numeric = float(value) if isinstance(value, str) else value
                    # Isolate this field's validation failure, never score or export the probe.
                    # Original input cells are not modified or imputed.
                    probe = dict.fromkeys(FEATURES, 0.0)
                    probe[name] = numeric
                    effective_inputs(probe, 0, duration_hours=3)
                except (ValueError, TypeError, OverflowError) as exc:
                    invalid.append({"row": i, "ward_id": str(row.get("ward_id")), "feature": name, "reason": str(exc)})
        alignment = {"boundary_only_ids": sorted(set(boundary_ids) - set(ids)),
                     "feature_only_ids": sorted(set(ids) - set(boundary_ids))}
        # Only compare per-ID official numbers after uniqueness and ID validity checks.
        number_mismatches = []
        if not any(issues.values()) and len(boundary_ids) == len(boundary_numbers) and len(set(boundary_ids)) == len(boundary_ids):
            expected = dict(zip(boundary_ids, map(str, boundary_numbers), strict=True))
            number_mismatches = [ident for ident, number in zip(ids, numbers, strict=True)
                                 if ident in expected and str(number) != expected[ident]]
        crs = frame.attrs.get("crs")
        result["features"].update(record_count=len(frame), declared_crs=str(crs) if crs is not None else None,
                                  missing_columns=missing_columns, invalid_measurements=invalid,
                                  official_number_mismatches=number_mismatches, **issues, **alignment)
        feature_ok = bool(len(frame)) and not (missing_columns or invalid or number_mismatches or any(issues.values()) or any(alignment.values()))
        if not feature_ok:
            blockers.append("Repair feature measurements and boundary/feature ID alignment; preserve unknowns rather than zero-filling.")
    except (OSError, ValueError, ImportError, TypeError) as exc:
        blockers.append(f"Features unavailable/unreadable: {exc}; John must supply the feature artifact and provenance, plus explicit CSV export for the runner.")
    if metrics is not None:
        try:
            stored = load_validation_metrics(metrics)
            mock = bool(re.search(r"\bmock\b", json.dumps(stored), re.I))
            result["metrics"] = {"explicit_mock": mock, "status": "unsuitable_for_accuracy_claims" if mock else "unverified", "notes": stored.get("notes")}
            if mock:
                result["historical_blockers"].append("Explicit MOCK metrics are placeholders, unsuitable for historical accuracy claims; Ronit must suppress them.")
            elif stored.get("status") == "unavailable":
                result["metrics"]["status"] = "unavailable"
                result["historical_blockers"].append(stored["status_reason"])
        except (OSError, ValueError) as exc:
            result["metrics"] = {"status": "unavailable", "reason": str(exc)}
    result["structural_scoring_ready"] = result["identity_ready"] and feature_ok
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("boundary", "features", "metrics", "output"):
        parser.add_argument(f"--{name}", type=Path, required=name == "boundary")
    parser.add_argument("--boundary-version", default="")
    parser.add_argument("--identity-reference", default="")
    parser.add_argument("--administrative-unit", default="ward")
    args = parser.parse_args(argv)
    try:
        if args.output:
            out = args.output.resolve()
            inputs = [p.resolve() for p in (args.boundary, args.features, args.metrics) if p]
            if out.exists() or out in inputs or out == ROOT / "data/processed" or ROOT / "data/processed" in out.parents:
                raise ValueError("Output must be a new noncanonical path distinct from inputs")
        report = inspect_inputs(args.boundary, args.features, args.metrics, boundary_version=args.boundary_version,
                                identity_reference=args.identity_reference, administrative_unit=args.administrative_unit)
        print(f"Identity ready: {report['identity_ready']}; structural scoring ready: {report['structural_scoring_ready']}; historical ready: False")
        print(f"Boundary records: {report['boundary'].get('record_count', 'unavailable')}; feature records: {report['features'].get('record_count', 'unavailable')}")
        print(f"Blank boundary official numbers: {len(report['boundary'].get('blank_official_number_rows', []))}; zone-name signals: {len(report['boundary'].get('zone_name_signals', []))}")
        overlap = report["boundary"].get("overlap_review", {})
        if overlap.get("status") == "review_required":
            print(f"- Boundary overlap review required: {overlap['pair_count']} positive-area pairs; inspect JSON details. Structural readiness does not resolve these warnings.")
        for message in report["blockers"] + report["historical_blockers"]:
            print(f"- {message}")
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(_strict_json(report) + "\n")
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Readiness check failed: {exc}\n")
    return 0 if report["structural_scoring_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
