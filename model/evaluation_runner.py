"""Location-neutral six-feature baseline runner; see docs/evaluation_runner.md."""

import argparse
import csv
import os
import platform
import shutil
import sys
import tempfile
from io import BytesIO, StringIO
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import CRS
from pyproj import __version__ as pyproj_version

from model import validation
from model.risk_engine import effective_inputs, score_ward

BASELINE_ID = "six_feature_uncalibrated_baseline"
# Names only: units/ranges/formula live in docs/model_logic.md; validation is delegated.
FEATURES = ("elevation_mean", "slope_mean", "impervious_frac", "dist_to_water_m",
            "road_density_km_per_sqkm", "underpass_count")
ROOT = Path(__file__).resolve().parents[1]
FEATURE_UNITS = dict(zip(FEATURES, ("m", "degree", "fraction", "m", "km/km2", "count"), strict=True))


def _csv(data: bytes, name: str) -> pd.DataFrame:
    header = next(csv.reader(StringIO(data.decode("utf-8"))), [])
    if not header or len(header) != len(set(header)):
        raise ValueError(f"{name}: missing or duplicate CSV headers")
    return pd.read_csv(BytesIO(data), dtype=str, keep_default_na=False)


def _config(config: dict, metadata: dict) -> None:
    allowed = {"is_template", "location", "administrative_unit_type", "boundary_version",
               "model_id", "model_version", "projected_crs", "projection_review_ref",
               "identity_reference", "identity_mode", "id_mapping", "builtup_increase",
               "run_purpose", "feature_provenance"}
    if set(config) - allowed:
        raise ValueError(f"Unsupported configuration keys: {sorted(set(config) - allowed)}")
    if config.get("is_template"):
        raise ValueError("Complete the configuration template before running")
    if config.get("run_purpose") not in ("synthetic_demonstration", "historical_evaluation"):
        raise ValueError("Explicit run_purpose required")
    provenance = config.get("feature_provenance")
    if not isinstance(provenance, dict) or set(provenance) != set(FEATURES):
        raise ValueError("feature_provenance must cover exactly all six scoring features")
    for feature, declaration in provenance.items():
        if not isinstance(declaration, dict):
            raise ValueError(f"feature_provenance.{feature} must be an object")
        for field in ("source_ref", "dataset_version_or_date", "coverage_notes", "processing_ref"):
            validation._text(declaration.get(field), f"{feature}.{field}")
        if declaration.get("units") != FEATURE_UNITS[feature]:
            raise ValueError(f"{feature} units must be {FEATURE_UNITS[feature]}")
        if declaration.get("evidence_type") not in ("observed", "derived", "synthetic", "unknown"):
            raise ValueError(f"{feature}: unsupported evidence_type")
        if declaration.get("coverage_status") not in ("complete", "partial", "unknown"):
            raise ValueError(f"{feature}: unsupported coverage_status")
        if config["run_purpose"] == "historical_evaluation" and declaration["evidence_type"] in ("synthetic", "unknown"):
            raise ValueError(f"{feature}: historical evaluation rejects synthetic/unknown origin")
    for field in ("location", "administrative_unit_type", "boundary_version", "model_id",
                  "model_version", "projected_crs", "projection_review_ref", "identity_reference"):
        validation._text(config.get(field), f"config.{field}")
    if config["model_id"] != BASELINE_ID:
        raise ValueError(f"Only model_id={BASELINE_ID} is supported; no new coefficients assigned")
    for field in ("boundary_version", "model_id", "model_version", "location", "administrative_unit_type"):
        if metadata.get(field) != config[field]:
            raise ValueError(f"event metadata {field} must match configuration")
    if config.get("builtup_increase", 0) != 0 or isinstance(config.get("builtup_increase"), bool):
        raise ValueError("Historical baseline builtup_increase must be zero")
    if metadata.get("builtup_increase", 0) != 0:
        raise ValueError("Event metadata builtup_increase conflicts with historical baseline zero")
    if config.get("identity_mode") not in ("explicit_mapping", "same_as_official"):
        raise ValueError("identity_mode must be explicit_mapping or same_as_official")
    crs = CRS.from_user_input(config["projected_crs"])
    if not crs.is_projected or len(crs.axis_info) != 2 or not all(
        axis.unit_name in ("metre", "meter") and axis.unit_conversion_factor == 1
        for axis in crs.axis_info
    ):
        raise ValueError("projected_crs must have two projected metre axes; review local suitability")


def run(features_path: Path, labels_path: Path, metadata_path: Path, config_path: Path,
        output: Path, *, top_k: int = 20, invocation: list[str] | None = None) -> dict:
    paths = {"features": Path(features_path).resolve(), "labels": Path(labels_path).resolve(),
             "metadata": Path(metadata_path).resolve(), "configuration": Path(config_path).resolve()}
    output = Path(output).resolve()
    processed = ROOT / "data/processed"
    if output == processed or processed in output.parents or output in processed.parents:
        raise ValueError("Output must not replace or write within canonical processed data")
    if output.exists() or any(output == path or output in path.parents for path in paths.values()):
        raise ValueError("Output must be a new directory, distinct from inputs and their ancestors")
    raw = {name: path.read_bytes() for name, path in paths.items()}
    config = validation._read_json(raw["configuration"].decode("utf-8"), paths["configuration"])
    metadata = validation._metadata(validation._read_json(raw["metadata"].decode("utf-8"), paths["metadata"]))
    _config(config, metadata)
    features = _csv(raw["features"], "features")
    features = validation._read_csv(features.to_csv(index=False).encode())
    labels_text = _csv(raw["labels"], "labels")
    labels = validation._read_csv(labels_text.to_csv(index=False).encode())
    required = {"ward_id", "official_number", "event_id", "boundary_version", *FEATURES}
    if not required.issubset(features):
        raise ValueError(f"Missing feature columns: {sorted(required - set(features.columns))}")
    if features.empty:
        raise ValueError("No feature records supplied; real-data run remains pending")
    # Reuse evaluator identity and optional metadata checks, before any score is calculated.
    validation._records(features, ["ward_id", "event_id", "boundary_version"], metadata, "features")
    mapping = config.get("id_mapping", {})
    if not isinstance(mapping, dict):
        raise ValueError("id_mapping must be an object of internal ID -> official number strings")
    if config["identity_mode"] == "same_as_official" and mapping:
        raise ValueError("Do not combine an identity assertion with id_mapping")
    if config["identity_mode"] == "explicit_mapping":
        for key, value in mapping.items():
            validation._ward_id(key)
            validation._text(value, f"id_mapping.{key}")
        if set(mapping) != set(features.ward_id):
            raise ValueError("id_mapping must cover exactly the feature IDs")
    errors, measurements, official_numbers = [], [], []
    for position, (_, row) in enumerate(features.iterrows(), start=2):
        try:
            official = validation._text(row["official_number"], "official_number")
            expected = row["ward_id"] if config["identity_mode"] == "same_as_official" else mapping[row["ward_id"]]
            if official != expected:
                raise ValueError("official_number disagrees with reviewed identity/mapping")
            official_numbers.append(official)
            numeric = {}
            for name in FEATURES:
                try:
                    numeric[name] = float(row[name])
                except ValueError as exc:
                    raise ValueError(f"{name} must be numeric, not {row[name]!r}") from exc
            effective_inputs(numeric, metadata["rainfall_mm"], 0,
                             duration_hours=metadata["duration_hours"])
            measurements.append(numeric)
        except ValueError as exc:
            errors.append(f"CSV row {position}, ward_id={row['ward_id']!r}: {exc}")
    if len(set(official_numbers)) != len(official_numbers):
        errors.append("Duplicate official_number; resolve ambiguous administrative alignment")
    if errors:
        raise ValueError("Invalid feature records (none scored):\n" + "\n".join(errors))
    predictions = features[["ward_id", "event_id", "boundary_version"]].copy()
    predictions["risk_score"] = 0.0
    validation.evaluate_predictions(predictions, labels, metadata, top_k)  # Evidence preflight.
    predictions["risk_score"] = [score_ward(row, metadata["rainfall_mm"], 0,
                                duration_hours=metadata["duration_hours"])[0] for row in measurements]
    predictions["ward_id"] = predictions.ward_id.map(validation._ward_id)
    predictions = predictions.sort_values(["risk_score", "ward_id"], ascending=[False, True])
    predictions = predictions[["ward_id", "risk_score", "event_id", "boundary_version"]]
    report = validation.evaluate_predictions(predictions, labels, metadata, top_k)
    manifest = {
        "run_purpose": config["run_purpose"],
        "evidence_notice": ("SYNTHETIC DEMONSTRATION; not evidence of historical accuracy"
                            if config["run_purpose"] == "synthetic_demonstration" else
                            "Historical evaluation with caller-attested feature provenance; not independently verified"),
        "feature_coverage_notice": "Caller attestations only; finite numbers and zeros do not verify coverage of Chennai or any location",
        "features_without_complete_attested_coverage": sorted(
            name for name, item in config["feature_provenance"].items() if item["coverage_status"] != "complete"),
        "runner_version": "1", "baseline": "Uncalibrated six-feature index; local applicability unverified",
        "configuration": config,
        "unused_feature_columns": sorted(set(features.columns) - required),
        "scenario": {"rainfall_mm": metadata["rainfall_mm"], "duration_hours": metadata["duration_hours"],
                     "builtup_increase": 0},
        "input_files": {name: {"path": str(path), "sha256": validation._hash(raw[name])}
                        for name, path in paths.items()},
        "source_sha256": {name: validation._hash((ROOT / "model" / name).read_bytes())
                          for name in ("evaluation_runner.py", "risk_engine.py", "reasons.py", "validation.py")},
        "runtime": {"python": platform.python_version(), "pandas": pd.__version__,
                    "numpy": np.__version__, "pyproj": pyproj_version},
        "invocation": {"arguments": invocation, "cwd": str(Path.cwd()), "top_k": top_k,
                       "output": str(output), "entry_point": "model.evaluation_runner.run"},
        "geographic_processing": "None: supplied aggregate features only; CRS check is structural, not local accuracy validation",
    }
    report["runner_manifest"] = manifest
    report["run_purpose"] = manifest["run_purpose"]
    report["evidence_notice"] = manifest["evidence_notice"]
    report["warnings"].extend([manifest["evidence_notice"], manifest["feature_coverage_notice"]])
    csv_bytes = predictions.to_csv(index=False).encode("utf-8")
    manifest["predictions_sha256"] = validation._hash(csv_bytes)
    # Validate everything before creating output; stage a complete review bundle.
    validation._strict_json(report)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".baseline-", dir=output.parent))
    try:
        (staging / "predictions.csv").write_bytes(csv_bytes)
        validation.save_validation_metrics(report, staging / "evaluation.json")
        validation.save_validation_metrics(manifest, staging / "manifest.json")
        if output.exists():
            raise ValueError("Output appeared during evaluation; refusing overwrite")
        os.rename(staging, output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)  # Only this invocation's private staging directory.
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("features", "labels", "metadata", "config", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--top-k", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        run(args.features, args.labels, args.metadata, args.config, args.output,
            top_k=args.top_k, invocation=list(sys.argv[1:] if argv is None else argv))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Baseline run failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
