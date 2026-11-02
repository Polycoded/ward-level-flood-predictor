"""Spatially blocked evaluation of historical flood-susceptibility rankings.

Primary estimate: leave-one-administrative-zone-out (geographically unseen wards).
Sensitivity estimate: leave-one-quadrant-out, matching the earlier research note.

Target = historical satellite-mapped inundation proxy. A 0 is a protocol
non-detection, not a confirmed dry ward. Unknown labels are excluded upstream and are
never converted to negatives here. Scores are rankings, not calibrated probabilities.
"""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from audit_geometry import audit_geometry  # noqa: E402
from matplotlib.cm import ScalarMappable  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402
from sklearn.metrics import precision_recall_curve  # noqa: E402
from spatial_common import (  # noqa: E402
    FEATURES,
    K_VALUES,
    SEED,
    TARGET,
    add_rank_normalized_score,
    attach_zones,
    block_bootstrap,
    code_tables,
    coefficient_stability,
    feature_correlations,
    fit_logistic,
    fold_assignments,
    load_dataset,
    load_zone_map,
    macro_metrics,
    make_folds,
    precision_recall_metrics,
    sha256_file,
    tune_logistic_c,
    write_json,
)

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]

try:
    from model.risk_engine import score_ward
except Exception as exc:  # noqa: BLE001
    raise RuntimeError("Cannot import model.risk_engine; run from the repository root") from exc

LABEL_PROVENANCE = {
    "source": "Global Flood Database events 2758 (2005) and 4309 (2015)",
    "citation": "Tellman et al. (2021), doi:10.1038/s41586-021-03695-w",
    "license": "GFD is CC BY-NC 4.0; derived proxy data are not unrestricted commercial data",
    "frozen_protocol": "quality >= .90, coverage >= .90, 4-connected components >= 4 native cells, "
                       "fraction >= .05, 250 m boundary sensitivity",
    "target_positive": "ward intersects at least one accepted satellite-mapped inundation component",
    "target_zero": "protocol non-detection; NOT confirmed dry and NOT confirmed non-flooded",
    "target_unknown": "excluded upstream; never converted to a negative in this evaluation",
    "confirmed_negatives_available": False,
    "confirmed_ground_truth_available": False,
}

FEATURE_PROVENANCE = [
    {"feature": "elevation_mean", "source": "Copernicus DEM 30 m", "resolution": "30 m",
     "vintage": "static terrain (acquisition varies by tile)", "dynamic": False,
     "available_for_use": True,
     "coupling_risk": "GFD label generation used terrain masks; different DEM but conceptually coupled"},
    {"feature": "slope_mean", "source": "Copernicus DEM 30 m via numpy.gradient",
     "resolution": "30 m", "vintage": "static terrain", "dynamic": False,
     "available_for_use": True,
     "coupling_risk": "same terrain-mask coupling as elevation"},
    {"feature": "impervious_frac", "source": "ESA WorldCover 10 m v200 built-up fraction",
     "resolution": "10 m", "vintage": "2021", "dynamic": False,
     "available_for_use": True,
     "coupling_risk": "not as-of-event for 2005/2015 labels"},
    {"feature": "dist_to_water_m", "source": "OSM/Geofabrik water, centroid distance",
     "resolution": "vector, 2026-10-20 snapshot", "vintage": "current", "dynamic": False,
     "available_for_use": True,
     "coupling_risk": "label generator excludes permanent water; proximity is conceptually related"},
    {"feature": "road_density_km_per_sqkm", "source": "OSM/Geofabrik roads",
     "resolution": "vector, 2026-10-20 snapshot", "vintage": "current", "dynamic": False,
     "available_for_use": True,
     "coupling_risk": "not as-of-event; urban growth after 2005/2015"},
    {"feature": "underpass_count", "source": "OSM/Geofabrik underpasses",
     "resolution": "vector, 2026-10-20 snapshot", "vintage": "current", "dynamic": False,
     "available_for_use": True,
     "coupling_risk": "not as-of-event; sparse OSM completeness"},
]

EXPECTED_SIGNS = {
    "elevation_mean": -1,
    "slope_mean": -1,
    "impervious_frac": 1,
    "dist_to_water_m": -1,
    "road_density_km_per_sqkm": 1,
    "underpass_count": 1,
}

NO_TERRAIN = [feature for feature in FEATURES
              if feature not in {"elevation_mean", "slope_mean"}]
NO_WATER = [feature for feature in FEATURES if feature != "dist_to_water_m"]
NO_TERRAIN_OR_WATER = [feature for feature in NO_TERRAIN
                       if feature != "dist_to_water_m"]

MODELS = {
    "random": {"kind": "random",
               "note": "uniform random ranking; analytic expectation also reported"},
    "elevation": {"kind": "elevation", "features": ["elevation_mean"],
                  "note": "lower mean elevation ranks higher; a simple terrain baseline"},
    "weighted_index": {"kind": "weighted", "features": FEATURES,
                       "note": "existing uncalibrated application index at 200 mm / 3 h, so R=1.0"},
    "logistic_current": {"kind": "logistic", "features": FEATURES, "C": 1.0,
                         "class_weight": "balanced",
                         "note": "frozen prior configuration: C=1, balanced, liblinear"},
    "logistic_l2_tuned": {"kind": "logistic_tuned", "features": FEATURES,
                          "class_weight": "balanced",
                          "note": "L2 C tuned by ward-grouped inner CV on training rows only"},
    "ablation_no_terrain": {"kind": "logistic", "features": NO_TERRAIN, "C": 1.0,
                            "class_weight": "balanced", "note": "drops elevation and slope"},
    "ablation_no_water_proximity": {"kind": "logistic", "features": NO_WATER, "C": 1.0,
                                   "class_weight": "balanced", "note": "drops dist_to_water_m"},
    "ablation_no_terrain_or_water": {"kind": "logistic",
                                    "features": NO_TERRAIN_OR_WATER, "C": 1.0,
                                    "class_weight": "balanced",
                                    "note": "drops elevation, slope and water proximity"},
}

MAIN_MODELS = ["random", "elevation", "weighted_index",
               "logistic_current", "logistic_l2_tuned"]


def audit_labels(df: pd.DataFrame, zone_map: pd.DataFrame) -> dict:
    with_zones = attach_zones(df, zone_map)
    per_event = with_zones.groupby("event_id")[TARGET].agg(["size", "sum"]).reset_index()
    per_block = with_zones.groupby("block")[TARGET].agg(["size", "sum"]).reset_index()
    per_zone = with_zones.groupby("zone_number")[TARGET].agg(["size", "sum"]).reset_index()
    repeated = with_zones.groupby("ward_id")[FEATURES].nunique()
    event_count = int(with_zones["event_id"].nunique())
    expected_rows = int(zone_map["ward_id"].nunique() * event_count)
    return {
        "provenance": LABEL_PROVENANCE,
        "rows": int(len(with_zones)),
        "wards": int(with_zones["ward_id"].nunique()),
        "wards_in_boundary": int(zone_map["ward_id"].nunique()),
        "wards_absent_entirely": int(zone_map["ward_id"].nunique()
                                     - with_zones["ward_id"].nunique()),
        "events": sorted(with_zones["event_id"].unique().tolist()),
        "positives": int(with_zones[TARGET].sum()),
        "positive_wards": sorted(with_zones.loc[
            with_zones[TARGET] == 1, "ward_id"].unique().tolist()),
        "prevalence": float(with_zones[TARGET].mean()),
        "rows_per_ward": with_zones.groupby("ward_id").size().value_counts()
        .sort_index().to_dict(),
        "static_features_identical_across_events": bool((repeated <= 1).all().all()),
        "unknown_excluded_upstream_inferred": expected_rows - int(len(with_zones)),
        "unknown_exclusion_note": (
            "Inferred from unique wards x events minus frozen rows. The 54 unknown rows "
            "are not present in the frozen table and cannot be individually audited here."),
        "accepted_label_values": sorted(
            with_zones["accepted_label"].astype(str).unique().tolist())
        if "accepted_label" in with_zones.columns else None,
        "per_event": per_event.to_dict("records"),
        "per_block": per_block.to_dict("records"),
        "per_zone": per_zone.to_dict("records"),
        "feature_provenance": FEATURE_PROVENANCE,
        "warnings": [
            "Zeros are protocol non-detections, not confirmed dry wards.",
            "Only seven proxy positives exist; model comparisons are exploratory.",
            "Static predictors cannot distinguish 2005 from 2015 rainfall.",
            "No probability calibration is claimed.",
        ],
    }


def _impute_from_train(train: pd.DataFrame, test: pd.DataFrame,
                       features) -> pd.DataFrame:
    medians = train[list(features)].median(numeric_only=True)
    filled = test[list(features)].copy()
    filled = filled.fillna(medians)
    filled = filled.fillna(0.0)
    if "underpass_count" in filled.columns:
        filled["underpass_count"] = filled["underpass_count"].round()
    return filled


def predict_model(name: str, spec: dict, train: pd.DataFrame, test: pd.DataFrame,
                  rng: np.random.Generator) -> tuple[np.ndarray | None, str, dict]:
    kind = spec["kind"]
    features = spec.get("features", FEATURES)
    info: dict = {}
    if kind == "random":
        return rng.random(len(test)), "ok", info
    if kind == "elevation":
        filled = _impute_from_train(train, test, ["elevation_mean"])
        return -filled["elevation_mean"].to_numpy(dtype=float), "ok", info
    if kind == "weighted":
        filled = _impute_from_train(train, test, features)
        scores = []
        for _, row in filled.iterrows():
            index, _risk_level, _depth, _window, _reasons = score_ward(
                row, 200.0, 0.0, duration_hours=3.0)
            scores.append(index)
        return np.asarray(scores, dtype=float), "ok", info
    if kind == "logistic":
        pipeline = fit_logistic(train, features, C=spec.get("C", 1.0),
                                class_weight=spec.get("class_weight", "balanced"))
        if pipeline is None:
            return None, "insufficient_classes_in_training", info
        return pipeline.predict_proba(test[list(features)])[:, 1], "ok", info
    if kind == "logistic_tuned":
        best_c, tune_info = tune_logistic_c(train, features, seed=SEED)
        info["tuning"] = tune_info
        pipeline = fit_logistic(train, features, C=best_c,
                                class_weight=spec.get("class_weight", "balanced"))
        if pipeline is None:
            return None, "insufficient_classes_in_training", info
        info["selected_C"] = best_c
        return pipeline.predict_proba(test[list(features)])[:, 1], "ok", info
    raise ValueError(f"Unknown model kind: {kind}")


def _rank_rows(frame: pd.DataFrame, scores: np.ndarray) -> pd.DataFrame:
    out = frame.copy()
    out["score"] = scores
    out = out.sort_values(["score", "ward_id", "event_id"],
                          ascending=[False, True, True]).reset_index(drop=True)
    out["rank_in_fold"] = np.arange(1, len(out) + 1)
    return out


def run_evaluation(args) -> Path:
    output = args.output
    if output.exists():
        raise FileExistsError(f"Output directory already exists: {output}")
    output.mkdir(parents=True)
    df, dataset_audit = load_dataset(args.dataset, target=TARGET)
    if getattr(args, "exclude_wards", None):
        excluded = sorted(set(int(value) for value in args.exclude_wards))
        before = len(df)
        df = df.loc[~df["ward_id"].isin(excluded)].reset_index(drop=True)
        dataset_audit["excluded_wards"] = excluded
        dataset_audit["rows_before_exclusion"] = before
        dataset_audit["rows_after_exclusion"] = int(len(df))
        if df.empty:
            raise ValueError("All rows were excluded")
    df.to_csv(output / "dataset_used.csv", index=False)
    zone_map = load_zone_map(args.crosswalk)
    label_audit = audit_labels(df, zone_map)
    write_json(output / "label_audit.json", label_audit)
    write_json(output / "dataset_audit.json", dataset_audit)
    geometry_report = audit_geometry(args.wards, args.crosswalk,
                                     output / "dataset_used.csv", output)

    schemes = ["zone", "quadrant"] if args.schemes == "both" else [args.schemes]
    oof_parts: list[pd.DataFrame] = []
    fold_assignments_all: list[pd.DataFrame] = []
    tuning_by_scheme: dict = {}
    coefficients: dict = {}
    fold_metadata: dict = {}

    for scheme_index, scheme in enumerate(schemes):
        folds = make_folds(df, scheme, zone_map)
        assignments = fold_assignments(df, scheme, zone_map)
        assignments.to_csv(output / f"fold_assignments_{scheme}.csv", index=False)
        fold_assignments_all.append(assignments)
        fold_metadata[scheme] = []
        tuning_by_scheme[scheme] = {}
        coefficients[scheme] = {}
        for fold_index, fold in enumerate(folds):
            train = df.iloc[fold["train_idx"]].reset_index(drop=True)
            test = df.iloc[fold["test_idx"]].reset_index(drop=True)
            fold_metadata[scheme].append({
                "fold": fold["fold"],
                "test_unit": fold["test_unit"],
                "n_train": fold["n_train"],
                "n_test": fold["n_test"],
                "train_positives": fold["train_positives"],
                "test_positives": fold["test_positives"],
                "test_wards": fold["test_wards"],
            })
            for model_index, (name, spec) in enumerate(MODELS.items()):
                rng = np.random.default_rng(
                    args.seed + scheme_index * 10_000 + fold_index * 100 + model_index)
                scores, status, info = predict_model(name, spec, train, test, rng)
                if info.get("tuning") is not None:
                    tuning_by_scheme[scheme].setdefault(name, {})[fold["fold"]] = info["tuning"]
                if status == "ok":
                    ranked = _rank_rows(test, scores)
                else:
                    ranked = test.copy()
                    ranked["score"] = np.nan
                    ranked["rank_in_fold"] = np.nan
                ranked["scheme"] = scheme
                ranked["model"] = name
                ranked["fold"] = fold["fold"]
                ranked["test_unit"] = fold["test_unit"]
                ranked["status"] = status
                oof_parts.append(ranked[[
                    "scheme", "model", "fold", "test_unit", "event_id", "ward_id",
                    "ward_number", "block", TARGET, "score", "rank_in_fold", "status",
                ]])
                if name in {"logistic_current", "logistic_l2_tuned"} and status == "ok":
                    pipeline = fit_logistic(train, spec["features"],
                                            C=info.get("selected_C", spec.get("C", 1.0)),
                                            class_weight=spec.get("class_weight", "balanced"))
                    if pipeline is not None:
                        coefficients[scheme].setdefault(name, {})[fold["fold"]] = \
                            code_tables({fold["fold"]: pipeline})[fold["fold"]]

    oof = pd.concat(oof_parts, ignore_index=True)
    oof.to_csv(output / "oof_predictions.csv", index=False)
    pd.concat(fold_assignments_all, ignore_index=True).to_csv(
        output / "fold_assignments.csv", index=False)

    results: dict = {
        "meta": {
            "schemes": schemes,
            "primary_scheme": schemes[0],
            "target": TARGET,
            "target_definition": LABEL_PROVENANCE,
            "k_values": list(args.k),
            "seed": args.seed,
            "n_boot": args.n_boot,
            "scores_are_rankings_not_probabilities": True,
            "negative_labels_are_protocol_non_detections": True,
            "pooled_metric_policy": (
                "Raw scores from separately trained fold models are not comparable. "
                "Headline pooled metrics use within-fold percentile ranks; raw pooled "
                "scores are retained as a diagnostic only. Per-fold metrics and their "
                "macro averages are reported separately."),
            "folds": fold_metadata,
            "fold_diagnostics": {
                scheme: {
                    "n_folds": len(meta),
                    "folds_without_test_positives": [
                        fold["fold"] for fold in meta if fold["test_positives"] == 0],
                    "folds_without_training_positives": [
                        fold["fold"] for fold in meta if fold["train_positives"] == 0],
                }
                for scheme, meta in fold_metadata.items()
            },
        },
        "label_audit": label_audit,
        "geometry_audit": {
            "ward_count": geometry_report["ward_count"],
            "invalid_geometries": geometry_report["invalid_geometries"],
            "overlap_summary": geometry_report["overlap_summary"],
            "positive_ward_overlaps": geometry_report["positive_ward_overlaps"],
            "positive_wards_with_substantial_overlap":
                geometry_report["positive_wards_with_substantial_overlap"],
        },
        "schemes": {},
        "tuning": tuning_by_scheme,
        "coefficients_by_fold": coefficients,
    }

    for scheme in schemes:
        subset = oof.loc[oof["scheme"].eq(scheme)]
        scheme_result: dict = {"models": {}, "random_analytic": {}}
        for name in MODELS:
            model_rows = subset.loc[subset["model"].eq(name)]
            valid = model_rows.loc[model_rows["status"].eq("ok")].copy()
            valid = add_rank_normalized_score(valid)
            pooled = precision_recall_metrics(
                valid[TARGET], valid["rank_score"], valid["ward_id"],
                valid["event_id"], tuple(args.k))
            pooled_raw = precision_recall_metrics(
                valid[TARGET], valid["score"], valid["ward_id"],
                valid["event_id"], tuple(args.k))
            per_fold = []
            for meta in fold_metadata[scheme]:
                fold_rows = valid.loc[valid["fold"].eq(meta["fold"])]
                metrics = precision_recall_metrics(
                    fold_rows[TARGET], fold_rows["score"], fold_rows["ward_id"],
                    fold_rows["event_id"], tuple(args.k))
                metrics.update({
                    "fold": meta["fold"],
                    "test_unit": meta["test_unit"],
                    "n_train": meta["n_train"],
                    "test_positives": meta["test_positives"],
                    "train_positives": meta["train_positives"],
                })
                per_fold.append(metrics)
            entry = {
                "note": MODELS[name]["note"],
                "pooled": pooled,
                "pooled_raw_scores_diagnostic_only": pooled_raw,
                "per_fold": per_fold,
                "macro": macro_metrics(per_fold, tuple(args.k)),
                "status_counts": model_rows["status"].value_counts().to_dict(),
            }
            if name in MAIN_MODELS:
                entry["bootstrap_all_blocks"] = block_bootstrap(
                    valid, tuple(args.k), n_boot=args.n_boot, seed=args.seed,
                    score_column="rank_score",
                    estimand=("with-replacement resample of all geographic blocks; "
                              "conditional on at least one positive"))
                positive_folds = [
                    fold for fold in sorted(valid["fold"].unique())
                    if int(valid.loc[valid["fold"].eq(fold), TARGET].sum()) > 0]
                if len(positive_folds) >= 2:
                    entry["bootstrap_positive_blocks"] = block_bootstrap(
                        valid, tuple(args.k), n_boot=args.n_boot, seed=args.seed,
                        score_column="rank_score", fold_subset=positive_folds,
                        estimand=("with-replacement resample of positive-containing "
                                  "geographic blocks only"))
            scheme_result["models"][name] = entry

        for name, spec in MODELS.items():
            model_rows = subset.loc[subset["model"].eq(name)]
            valid = model_rows.loc[model_rows["status"].eq("ok")]
            pooled = analytic_random(valid, tuple(args.k))
            per_fold = []
            for meta in fold_metadata[scheme]:
                fold_rows = valid.loc[valid["fold"].eq(meta["fold"])]
                metrics = analytic_random(fold_rows, tuple(args.k))
                metrics.update({
                    "fold": meta["fold"],
                    "test_unit": meta["test_unit"],
                    "n_train": meta["n_train"],
                    "test_positives": meta["test_positives"],
                    "train_positives": meta["train_positives"],
                })
                per_fold.append(metrics)
            scheme_result["random_analytic"][name] = {
                "note": "analytic expectation for a uniform random ranking; no sampling noise",
                "pooled": pooled,
                "pooled_raw_scores_diagnostic_only": pooled,
                "per_fold": per_fold,
                "macro": macro_metrics(per_fold, tuple(args.k)),
            }
        results["schemes"][scheme] = scheme_result

    results["feature_sign_audit"] = sign_audit(df)
    results["feature_correlations"] = feature_correlations(df)
    results["coefficient_stability"] = {
        scheme: {
            model: coefficient_stability(by_fold)
            for model, by_fold in models.items()
        }
        for scheme, models in coefficients.items()
    }
    write_json(output / "metrics.json", results)
    write_metrics_csv(output / "metrics_per_fold.csv", results)
    plot_precision_recall(output, oof, schemes, tuple(args.k))
    plot_geography(output, args.wards, oof, schemes[0], tuple(args.k))
    write_manifest(output, args, df, schemes, geometry_report)
    return output


def analytic_random(rows: pd.DataFrame, k_values) -> dict:
    n = int(len(rows))
    positives = int(rows[TARGET].sum()) if n else 0
    if n == 0:
        return {"n": 0, "positives": 0, "prevalence": None, "average_precision": None,
                "pr_auc_trapezoidal": None, "k": {}}
    prevalence = positives / n
    result = {
        "n": n,
        "positives": positives,
        "negatives": n - positives,
        "prevalence": prevalence,
        "average_precision": prevalence if positives else None,
        "pr_auc_trapezoidal": prevalence if positives else None,
        "k": {},
    }
    for requested_k in k_values:
        effective_k = min(int(requested_k), n)
        recall = effective_k / n if positives else None
        result["k"][str(requested_k)] = {
            "requested_k": int(requested_k),
            "effective_k": effective_k,
            "reduced": bool(effective_k < requested_k),
            "true_positives": None,
            "precision": prevalence if positives else 0.0,
            "recall": recall,
            "lift": 1.0 if prevalence > 0 else None,
            "cutoff_score": None,
        }
    return result


def write_metrics_csv(path: Path, results: dict) -> None:
    rows = []
    for scheme, scheme_result in results["schemes"].items():
        for name, entry in scheme_result["models"].items():
            rows.append(_flatten(scheme, name, entry["pooled"],
                                 entry.get("pooled_raw_scores_diagnostic_only")))
            for metrics in entry["per_fold"]:
                rows.append(_flatten(scheme, name, metrics))
        for name, entry in scheme_result["random_analytic"].items():
            rows.append(_flatten(scheme, f"{name}_analytic", entry["pooled"]))
            for metrics in entry["per_fold"]:
                rows.append(_flatten(scheme, f"{name}_analytic", metrics))
    frame = pd.DataFrame(rows)
    integer_columns = ["n", "positives", "n_train", "train_positives", "test_positives"]
    integer_columns += [column for column in frame.columns
                        if column.startswith("effective_k_")]
    for column in integer_columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Int64")
    frame.to_csv(path, index=False, na_rep="")


def _flatten(scheme: str, model: str, metrics: dict,
             raw_pooled: dict | None = None) -> dict:
    row = {
        "scheme": scheme,
        "model": model,
        "fold": metrics.get("fold", "pooled"),
        "test_unit": metrics.get("test_unit", ""),
        "n": metrics.get("n"),
        "positives": metrics.get("positives"),
        "prevalence": metrics.get("prevalence"),
        "average_precision": metrics.get("average_precision"),
        "pr_auc_trapezoidal": metrics.get("pr_auc_trapezoidal"),
        "n_train": metrics.get("n_train"),
        "train_positives": metrics.get("train_positives"),
        "test_positives": metrics.get("test_positives"),
    }
    if raw_pooled is not None:
        row["average_precision_raw_pooled"] = raw_pooled.get("average_precision")
        row["pr_auc_raw_pooled"] = raw_pooled.get("pr_auc_trapezoidal")
    for key, block in metrics.get("k", {}).items():
        row[f"effective_k_{key}"] = block["effective_k"]
        row[f"precision_at_{key}"] = block["precision"]
        row[f"recall_at_{key}"] = block["recall"]
        row[f"lift_at_{key}"] = block["lift"]
    if raw_pooled is not None:
        for key, block in raw_pooled.get("k", {}).items():
            row[f"precision_at_{key}_raw_pooled"] = block["precision"]
    return row


def plot_precision_recall(output: Path, oof: pd.DataFrame, schemes, k_values) -> None:
    for scheme in schemes:
        subset = oof.loc[(oof["scheme"].eq(scheme)) & (oof["status"].eq("ok"))].copy()
        if subset.empty:
            continue
        subset = add_rank_normalized_score(subset)
        y = subset[TARGET].to_numpy()
        if y.sum() == 0:
            continue
        fig, ax = plt.subplots(figsize=(6.4, 5.2))
        prevalence = y.mean()
        ax.axhline(prevalence, color="black", linestyle=":", linewidth=1,
                   label=f"no-skill (prevalence {prevalence:.3f})")
        for name in MAIN_MODELS:
            rows = subset.loc[subset["model"].eq(name)]
            if rows.empty or rows[TARGET].sum() == 0:
                continue
            precision, recall, _ = precision_recall_curve(rows[TARGET], rows["rank_score"])
            ax.plot(recall, precision, linewidth=1.6, label=name)
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.02)
        ax.grid(alpha=0.25)
        ax.set_title(
            f"Pooled within-fold percentile ranks ({scheme} folds; raw scores not pooled)")
        ax.legend(fontsize=8, loc="upper right")
        fig.tight_layout()
        fig.savefig(output / f"precision_recall_{scheme}.png", dpi=200)
        plt.close(fig)


def plot_geography(output: Path, wards_path: Path, oof: pd.DataFrame,
                   scheme: str, k_values) -> None:
    import geopandas as gpd
    wards = gpd.read_file(wards_path)
    subset = oof.loc[(oof["scheme"].eq(scheme)) & (oof["status"].eq("ok"))].copy()
    subset = add_rank_normalized_score(subset)
    models = ["weighted_index", "elevation", "logistic_current", "logistic_l2_tuned"]
    figure, axes = plt.subplots(2, 2, figsize=(12, 11))
    positives = set(oof.loc[oof[TARGET] == 1, "ward_id"].unique().tolist())
    for ax, name in zip(axes.ravel(), models):
        rows = subset.loc[subset["model"].eq(name)]
        if rows.empty:
            ax.set_axis_off()
            continue
        per_ward = rows.groupby("ward_id", as_index=False)["rank_score"].mean()
        merged = wards.merge(per_ward, on="ward_id", how="left")
        merged.plot(column="rank_score", cmap="viridis", vmin=0, vmax=1, linewidth=0.15,
                    edgecolor="white", ax=ax, missing_kwds={"color": "lightgrey"})
        marked = merged.loc[merged["ward_id"].isin(positives)]
        if not marked.empty:
            marked.centroid.plot(ax=ax, color="red", marker="x", markersize=45,
                                 linewidth=1.4)
        ax.set_title(f"{name}: within-fold percentile rank ({scheme} folds)", fontsize=10)
        ax.set_axis_off()
    sm = ScalarMappable(norm=Normalize(vmin=0, vmax=1), cmap="viridis")
    sm.set_array([])
    figure.colorbar(sm, ax=axes.ravel().tolist(), fraction=0.025, pad=0.02,
                    label="Within-fold percentile rank (held-out)")
    figure.suptitle("Held-out ward susceptibility; red X = proxy-positive wards",
                    fontsize=12)
    figure.savefig(output / "geographic_oof.png", dpi=200, bbox_inches="tight")
    plt.close(figure)


def sign_audit(df: pd.DataFrame) -> dict:
    pipeline = fit_logistic(df, FEATURES, C=1.0, class_weight="balanced")
    if pipeline is None:
        return {"status": "unavailable"}
    model = pipeline.named_steps["logisticregression"]
    feature_names = list(pipeline.feature_names_in_)
    coefficients = dict(zip(feature_names, model.coef_[0].tolist()))
    warnings = []
    for feature, expected in EXPECTED_SIGNS.items():
        observed = coefficients.get(feature)
        if observed is None:
            continue
        if np.sign(observed) != expected:
            warnings.append({
                "feature": feature,
                "coefficient": observed,
                "expected_sign": "positive" if expected > 0 else "negative",
                "observed_sign": "positive" if observed > 0 else "negative",
                "interpretation": "unexpected sign; do not treat as a physical relationship",
            })
    return {
        "scope": "full-data refit for diagnosis only; not an out-of-fold result",
        "coefficients_standardised": coefficients,
        "intercept": float(model.intercept_[0]),
        "sign_warnings": warnings,
    }


def write_manifest(output: Path, args, df: pd.DataFrame, schemes, geometry_report) -> None:
    import geopandas
    import matplotlib as mpl
    import sklearn

    write_json(output / "run_manifest.json", {
        "command": " ".join(sys.argv),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__,
        "geopandas": geopandas.__version__,
        "matplotlib": mpl.__version__,
        "seed": args.seed,
        "k_values": list(args.k),
        "n_boot": args.n_boot,
        "schemes": schemes,
        "dataset_sha256": sha256_file(args.dataset),
        "dataset_used_sha256": sha256_file(output / "dataset_used.csv"),
        "excluded_wards": getattr(args, "exclude_wards", None) or [],
        "script_sha256": sha256_file(Path(__file__)),
        "common_sha256": sha256_file(HERE / "spatial_common.py"),
        "geometry_audit_sha256": sha256_file(output / "geometry_audit.json"),
        "rows": int(len(df)),
        "wards": int(df["ward_id"].nunique()),
        "positives": int(df[TARGET].sum()),
        "geometry_summary": geometry_report["overlap_summary"],
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path,
                        default=HERE / "dataset.csv")
    parser.add_argument("--wards", type=Path,
                        default=REPO_ROOT / "data/processed/wards.geojson")
    parser.add_argument("--crosswalk", type=Path,
                        default=REPO_ROOT / "data/processed/ward_crosswalk.csv")
    parser.add_argument("--output", type=Path, required=True,
                        help="new directory for outputs")
    parser.add_argument("--schemes", choices=["zone", "quadrant", "both"],
                        default="both")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--bootstrap", dest="n_boot", type=int, default=1000)
    parser.add_argument("--k", type=int, nargs="+", default=list(K_VALUES))
    parser.add_argument("--exclude-wards", type=int, nargs="*", default=[],
                        help="optional label/geometry sensitivity: drop these ward IDs")
    args = parser.parse_args()
    output = run_evaluation(args)
    print(f"Wrote evaluation to {output}")


if __name__ == "__main__":
    main()
