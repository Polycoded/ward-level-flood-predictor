"""Shared, dependency-light utilities for spatially blocked susceptibility evaluation.

The evaluation target is a historical flood-detection proxy, not confirmed flooding and
not a forecast. See the research README for provenance and limits.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import auc, average_precision_score, precision_recall_curve
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FEATURES = [
    "elevation_mean",
    "slope_mean",
    "impervious_frac",
    "dist_to_water_m",
    "road_density_km_per_sqkm",
    "underpass_count",
]
TARGET = "experimental_proxy_target"
BLOCKS = ("NE", "NW", "SE", "SW")
REQUIRED_COLUMNS = [
    "event_id",
    "ward_id",
    "ward_number",
    "block",
    TARGET,
    *FEATURES,
]
K_VALUES = (10, 20, 50)
SEED = 42


def _json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot serialise {type(value)!r}")


def write_json(path: Path, payload) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False,
                   default=_json_default) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv_checked(path: Path) -> pd.DataFrame:
    header = pd.read_csv(path, nrows=0)
    if not header.columns.is_unique:
        duplicates = header.columns[header.columns.duplicated()].tolist()
        raise ValueError(f"Duplicate columns in {path}: {duplicates}")
    return pd.read_csv(path)


def require_columns(df: pd.DataFrame, columns) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def normalise_ward_ids(series: pd.Series, name: str = "ward_id") -> pd.Series:
    numeric = pd.to_numeric(series, errors="raise")
    if numeric.isna().any():
        raise ValueError(f"{name} contains missing values")
    if not np.isfinite(numeric).all():
        raise ValueError(f"{name} contains non-finite values")
    if (numeric % 1 != 0).any():
        raise ValueError(f"{name} must contain integers")
    if (numeric <= 0).any():
        raise ValueError(f"{name} must be positive")
    return numeric.astype("int64")


def drop_unknown_rows(df: pd.DataFrame, status_column: str) -> tuple[pd.DataFrame, dict]:
    """Exclude unknown labels instead of converting them to negatives."""
    if status_column not in df.columns:
        return df, {"status_column": None, "unknown_excluded": 0}
    status = df[status_column].astype("string").str.strip().str.lower()
    allowed = {"flooded", "non_flooded", "non-flooded", "negative", "positive", "unknown"}
    unexpected = sorted(set(status.dropna().unique()) - allowed)
    if unexpected:
        raise ValueError(f"Unexpected {status_column} values: {unexpected}")
    unknown_mask = status.eq("unknown") | status.isna()
    audit = {
        "status_column": status_column,
        "unknown_excluded": int(unknown_mask.sum()),
        "kept": int((~unknown_mask).sum()),
        "unknown_wards": sorted(df.loc[unknown_mask, "ward_id"].unique().tolist()),
    }
    return df.loc[~unknown_mask].copy(), audit


def validate_features(df: pd.DataFrame) -> dict:
    missing = {}
    nonnumeric = {}
    for feature in FEATURES:
        values = df[feature]
        if values.map(lambda value: isinstance(value, (bool, np.bool_))).any():
            raise ValueError(f"{feature} cannot contain booleans")
        numeric = pd.to_numeric(values, errors="coerce")
        bad = values.notna() & numeric.isna()
        if bad.any():
            nonnumeric[feature] = int(bad.sum())
        finite = numeric.replace([np.inf, -np.inf], np.nan)
        if finite.isna().sum() != values.isna().sum():
            raise ValueError(f"{feature} contains infinite values")
        missing[feature] = int(values.isna().sum())
        df[feature] = numeric.astype("float64")
    if nonnumeric:
        raise ValueError(f"Non-numeric feature values: {nonnumeric}")
    return {"missing_by_feature": missing}


def load_dataset(path: Path, target: str = TARGET,
                 status_column: str | None = None) -> tuple[pd.DataFrame, dict]:
    df = read_csv_checked(path)
    require_columns(df, REQUIRED_COLUMNS)
    audit: dict = {"path": str(path), "rows_in_file": int(len(df))}
    if status_column:
        df, status_audit = drop_unknown_rows(df, status_column)
        audit["status_audit"] = status_audit
    if df.empty:
        raise ValueError("No eligible rows after unknown-label exclusion")
    df = df.copy()
    df["ward_id"] = normalise_ward_ids(df["ward_id"])
    df[target] = pd.to_numeric(df[target], errors="raise")
    if df[target].isna().any() or not df[target].isin([0, 1]).all():
        raise ValueError(f"{target} must contain only 0 and 1 (unknowns excluded upstream)")
    df[target] = df[target].astype("int64")
    if df["event_id"].isna().any() or df["event_id"].astype(str).str.strip().eq("").any():
        raise ValueError("event_id must be nonempty")
    df["event_id"] = df["event_id"].astype(str)
    if df["block"].isna().any() or not df["block"].isin(BLOCKS).all():
        raise ValueError(f"block must be one of {BLOCKS}")
    if df["ward_number"].isna().any() or df["ward_number"].astype(str).str.strip().eq("").any():
        raise ValueError("ward_number must be nonempty")
    df["ward_number"] = df["ward_number"].astype(str)
    duplicates = df.duplicated(["event_id", "ward_id"])
    if duplicates.any():
        raise ValueError(f"Duplicate event_id/ward_id rows: {int(duplicates.sum())}")
    block_counts = df.groupby("ward_id")["block"].nunique()
    if (block_counts > 1).any():
        raise ValueError("A ward is assigned to more than one geographic block")
    feature_audit = validate_features(df)
    audit.update(feature_audit)
    audit["rows_eligible"] = int(len(df))
    audit["wards"] = int(df["ward_id"].nunique())
    audit["events"] = sorted(df["event_id"].unique().tolist())
    audit["positives"] = int(df[target].sum())
    audit["positive_wards"] = sorted(df.loc[df[target] == 1, "ward_id"].unique().tolist())
    audit["prevalence"] = float(df[target].mean())
    static = df.groupby("ward_id")[FEATURES].nunique()
    audit["static_features_identical_per_ward"] = bool((static <= 1).all().all())
    audit["rows_per_ward"] = df.groupby("ward_id").size().value_counts().sort_index().to_dict()
    audit["target"] = target
    return df.sort_values(["ward_id", "event_id"]).reset_index(drop=True), audit


def load_zone_map(path: Path) -> pd.DataFrame:
    zones = read_csv_checked(path)
    require_columns(zones, ["ward_id", "zone_number"])
    zones = zones.copy()
    zones["ward_id"] = normalise_ward_ids(zones["ward_id"])
    if zones["ward_id"].duplicated().any():
        raise ValueError("ward_crosswalk.csv contains duplicate ward_id values")
    zones["zone_number"] = zones["zone_number"].astype(str)
    return zones[["ward_id", "zone_number"]]


def attach_zones(df: pd.DataFrame, zone_map: pd.DataFrame) -> pd.DataFrame:
    merged = df.merge(zone_map, on="ward_id", how="left", validate="many_to_one")
    if merged["zone_number"].isna().any():
        missing = sorted(merged.loc[merged["zone_number"].isna(), "ward_id"].unique())
        raise ValueError(f"Missing zone assignments for ward_id: {missing}")
    return merged


def make_folds(df: pd.DataFrame, scheme: str, zone_map: pd.DataFrame | None = None) -> list[dict]:
    """Build leave-one-unit-out folds with all events of a ward kept together."""
    if scheme == "quadrant":
        frame = df.copy()
        fold_column = "block"
    elif scheme == "zone":
        if zone_map is None:
            raise ValueError("zone_map is required for zone folds")
        lookup = zone_map.set_index("ward_id")["zone_number"]
        frame = df.copy()
        frame["zone_number"] = frame["ward_id"].map(lookup)
        if frame["zone_number"].isna().any():
            missing = sorted(frame.loc[frame["zone_number"].isna(), "ward_id"].unique())
            raise ValueError(f"Missing zone assignments for ward_id: {missing}")
        fold_column = "zone_number"
    else:
        raise ValueError(f"Unknown fold scheme: {scheme}")
    folds = []
    for unit in sorted(frame[fold_column].unique()):
        test_mask = frame[fold_column].eq(unit)
        train_mask = ~test_mask
        train = frame.loc[train_mask]
        test = frame.loc[test_mask]
        if train.empty or test.empty:
            raise ValueError(f"Fold {unit} has an empty train or test set")
        train_wards = set(train["ward_id"].unique())
        test_wards = set(test["ward_id"].unique())
        if train_wards & test_wards:
            raise ValueError(f"Ward leakage in fold {unit}")
        folds.append({
            "scheme": scheme,
            "fold": f"{scheme}:{unit}",
            "test_unit": str(unit),
            "train_idx": np.flatnonzero(train_mask.to_numpy()),
            "test_idx": np.flatnonzero(test_mask.to_numpy()),
            "train_wards": sorted(train_wards),
            "test_wards": sorted(test_wards),
            "n_train": int(len(train)),
            "n_test": int(len(test)),
            "train_positives": int(train[TARGET].sum()),
            "test_positives": int(test[TARGET].sum()),
        })
    covered = set()
    for fold in folds:
        if covered & set(fold["test_wards"]):
            raise ValueError("A ward appears in more than one held-out fold")
        covered |= set(fold["test_wards"])
    if covered != set(df["ward_id"].unique()):
        raise ValueError("Held-out folds do not cover every ward exactly once")
    return folds


def fold_assignments(df: pd.DataFrame, scheme: str,
                     zone_map: pd.DataFrame | None = None) -> pd.DataFrame:
    if scheme == "quadrant":
        frame = df.copy()
        unit_column = "block"
    else:
        if zone_map is None:
            raise ValueError("zone_map is required for zone assignments")
        frame = attach_zones(df, zone_map)
        unit_column = "zone_number"
    grouped = frame.groupby("ward_id").agg(
        unit=(unit_column, "first"),
        n_events=("event_id", "nunique"),
        positives=(TARGET, "sum"),
        events=("event_id", lambda values: ";".join(sorted(set(values)))),
    ).reset_index()
    grouped["scheme"] = scheme
    grouped["fold"] = scheme + ":" + grouped["unit"].astype(str)
    return grouped[["scheme", "ward_id", "unit", "fold", "n_events", "positives", "events"]]


def make_logistic_pipeline(C: float, class_weight: str | None = "balanced",
                           max_iter: int = 2000, seed: int = SEED):
    return make_pipeline(
        SimpleImputer(strategy="median", keep_empty_features=True),
        StandardScaler(),
        LogisticRegression(C=C, solver="liblinear", class_weight=class_weight,
                           max_iter=max_iter, random_state=seed),
    )


def fit_logistic(train: pd.DataFrame, features, C: float = 1.0,
                 class_weight: str | None = "balanced", seed: int = SEED):
    if train[TARGET].nunique() < 2:
        return None
    pipeline = make_logistic_pipeline(C=C, class_weight=class_weight, seed=seed)
    pipeline.fit(train[list(features)], train[TARGET])
    return pipeline


def tune_logistic_c(train: pd.DataFrame, features, seed: int = SEED,
                    grid=(0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0)) -> tuple[float, dict]:
    """Tune C with ward-grouped inner CV using training rows only."""
    groups = train["ward_id"]
    n_groups = int(groups.nunique())
    n_splits = min(3, n_groups)
    info = {"inner_splits": n_splits, "grid": list(grid), "scores": {},
            "status": "ok"}
    if n_splits < 2:
        info["status"] = "fallback_insufficient_wards"
        return 1.0, info
    splitter = GroupKFold(n_splits=n_splits)
    best_C, best_score = 1.0, -np.inf
    for C in grid:
        fold_scores = []
        for train_idx, valid_idx in splitter.split(train, train[TARGET], groups):
            inner_train = train.iloc[train_idx]
            inner_valid = train.iloc[valid_idx]
            if inner_train[TARGET].nunique() < 2 or inner_valid[TARGET].nunique() < 2:
                continue
            pipeline = make_logistic_pipeline(C=C, seed=seed)
            pipeline.fit(inner_train[list(features)], inner_train[TARGET])
            probabilities = pipeline.predict_proba(inner_valid[list(features)])[:, 1]
            fold_scores.append(float(average_precision_score(
                inner_valid[TARGET], probabilities)))
        if fold_scores:
            score = float(np.mean(fold_scores))
            info["scores"][str(C)] = score
            if score > best_score + 1e-12:
                best_C, best_score = float(C), score
    if not info["scores"]:
        info["status"] = "fallback_no_valid_inner_folds"
        return 1.0, info
    info["selected_C"] = best_C
    info["inner_mean_ap"] = best_score
    return best_C, info


def precision_recall_metrics(y, score, ward_id, event_id,
                             k_values=K_VALUES) -> dict:
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    if len(y) != len(score):
        raise ValueError("y and score lengths differ")
    if len(y) == 0:
        raise ValueError("Cannot evaluate an empty set")
    if not np.isfinite(score).all():
        raise ValueError("Scores must be finite")
    n = int(len(y))
    positives = int(y.sum())
    negatives = n - positives
    prevalence = positives / n
    event_codes = pd.factorize(pd.Series(event_id).astype(str))[0]
    ward_array = np.asarray(ward_id)
    order = np.lexsort((event_codes, ward_array, -score))
    sorted_score = score[order]
    sorted_y = y[order]
    result = {
        "n": n,
        "positives": positives,
        "negatives": negatives,
        "prevalence": prevalence,
        "average_precision": None,
        "pr_auc_trapezoidal": None,
        "k": {},
    }
    if positives > 0:
        result["average_precision"] = float(average_precision_score(y, score))
        precision, recall, _ = precision_recall_curve(y, score)
        result["pr_auc_trapezoidal"] = float(auc(recall, precision))
    for requested_k in k_values:
        effective_k = min(int(requested_k), n)
        cutoff = sorted_score[effective_k - 1]
        above = sorted_score > cutoff
        tied = sorted_score == cutoff
        above_count = int(above.sum())
        tie_count = int(tied.sum())
        above_positives = int(sorted_y[above].sum())
        tie_positives = int(sorted_y[tied].sum())
        selected_from_tie = effective_k - above_count
        expected_tp = above_positives
        if selected_from_tie > 0:
            expected_tp += selected_from_tie * (tie_positives / tie_count)
        exact_top = order[:effective_k]
        exact_tp = int(y[exact_top].sum())
        precision_at_k = expected_tp / effective_k
        recall_at_k = expected_tp / positives if positives else None
        lift = precision_at_k / prevalence if prevalence > 0 else None
        result["k"][str(requested_k)] = {
            "requested_k": int(requested_k),
            "effective_k": effective_k,
            "reduced": bool(effective_k < requested_k),
            "true_positives": exact_tp,
            "expected_true_positives": float(expected_tp),
            "tie_aware": True,
            "ties_at_cutoff": tie_count,
            "tie_positive_fraction": (tie_positives / tie_count) if tie_count else None,
            "precision": float(precision_at_k),
            "recall": None if recall_at_k is None else float(recall_at_k),
            "lift": None if lift is None else float(lift),
            "cutoff_score": float(cutoff),
        }
    return result


def macro_metrics(per_fold: list[dict], k_values=K_VALUES) -> dict:
    keys = ["average_precision", "pr_auc_trapezoidal"]
    for k in k_values:
        keys += [f"precision_at_{k}", f"recall_at_{k}", f"lift_at_{k}"]
    values: dict = {}
    for key in keys:
        vals = []
        for fold in per_fold:
            if key.startswith(("precision_at_", "recall_at_", "lift_at_")):
                k = key.rsplit("_", 1)[1]
                block = fold.get("k", {}).get(k)
                if block is None:
                    continue
                if key.startswith("precision_at_"):
                    value = block["precision"]
                elif key.startswith("recall_at_"):
                    value = block["recall"]
                else:
                    value = block["lift"]
            else:
                value = fold.get(key)
            if value is not None and np.isfinite(value):
                vals.append(float(value))
        values[key] = {
            "mean": float(np.mean(vals)) if vals else None,
            "median": float(np.median(vals)) if vals else None,
            "min": float(np.min(vals)) if vals else None,
            "max": float(np.max(vals)) if vals else None,
            "defined_folds": len(vals),
            "total_folds": len(per_fold),
        }
    return values


def add_rank_normalized_score(df: pd.DataFrame, score_column: str = "score",
                              group_columns=("fold",)) -> pd.DataFrame:
    """Map scores to within-fold percentile ranks so fold-specific models can be pooled.

    Raw scores from separately trained fold models are not on a comparable scale.
    """
    out = df.copy()
    out["rank_score"] = out.groupby(list(group_columns))[score_column].rank(
        method="average", pct=True)
    return out


def block_bootstrap(oof: pd.DataFrame, k_values=K_VALUES, n_boot: int = 1000,
                    seed: int = SEED, score_column: str = "rank_score",
                    fold_subset=None, estimand: str | None = None) -> dict:
    """Indicative block bootstrap; only four quadrants or fifteen zones exist."""
    rng = np.random.default_rng(seed)
    all_folds = sorted(oof["fold"].unique())
    if fold_subset is None:
        folds = all_folds
    else:
        folds = sorted(set(all_folds) & set(fold_subset))
    if len(folds) < 2:
        return {"status": "insufficient_blocks", "n_blocks": len(folds),
                "estimand": estimand}
    positive_blocks = [
        fold for fold in folds
        if int(oof.loc[oof["fold"].eq(fold), TARGET].sum()) > 0]
    collected: dict[str, list[float]] = {}
    undefined = 0
    for _ in range(int(n_boot)):
        sampled = rng.choice(folds, size=len(folds), replace=True)
        parts = [oof.loc[oof["fold"].eq(fold)] for fold in sampled]
        sample = pd.concat(parts, ignore_index=True)
        metrics = precision_recall_metrics(
            sample[TARGET], sample[score_column], sample["ward_id"],
            sample["event_id"], k_values,
        )
        if metrics["average_precision"] is None:
            undefined += 1
            continue
        collected.setdefault("average_precision", []).append(metrics["average_precision"])
        collected.setdefault("pr_auc_trapezoidal", []).append(
            metrics["pr_auc_trapezoidal"])
        for k in k_values:
            block = metrics["k"][str(k)]
            collected.setdefault(f"precision_at_{k}", []).append(block["precision"])
            if block["recall"] is not None:
                collected.setdefault(f"recall_at_{k}", []).append(block["recall"])
            if block["lift"] is not None:
                collected.setdefault(f"lift_at_{k}", []).append(block["lift"])
    default_estimand = (
        "average precision of a with-replacement resample of geographic blocks, "
        "conditional on the resample containing at least one positive")
    summary = {"n_boot": int(n_boot), "n_blocks": len(folds),
               "positive_blocks": positive_blocks,
               "n_positive_blocks": len(positive_blocks),
               "estimand": estimand or default_estimand,
               "conditional_on_positive": True,
               "undefined_replicates": int(undefined), "metrics": {}}
    for key, values in collected.items():
        arr = np.asarray(values, dtype=float)
        summary["metrics"][key] = {
            "mean": float(arr.mean()),
            "lower_2_5": float(np.percentile(arr, 2.5)),
            "upper_97_5": float(np.percentile(arr, 97.5)),
            "valid_replicates": int(arr.size),
        }
    return summary


def feature_correlations(df: pd.DataFrame, target: str = TARGET,
                         features=None) -> dict:
    """Univariate associations for diagnosis; not causal or leakage-proof."""
    features = list(features or FEATURES)
    output = {}
    for feature in features:
        subset = df[[feature, target]].dropna()
        output[feature] = {
            "n": int(len(subset)),
            "pearson": (float(subset[feature].corr(subset[target], method="pearson"))
                        if len(subset) > 1 else None),
            "spearman": (float(subset[feature].corr(subset[target], method="spearman"))
                         if len(subset) > 1 else None),
        }
    return output


def coefficient_stability(by_fold: dict) -> dict:
    """Summarise coefficient signs and spread across folds; not causal evidence."""
    values: dict[str, list[float]] = {}
    for table in by_fold.values():
        if not table:
            continue
        for feature, coefficient in zip(table["features"],
                                        table["coefficients_standardised"]):
            values.setdefault(feature, []).append(float(coefficient))
    output = {}
    for feature, coefficients in values.items():
        array = np.asarray(coefficients, dtype=float)
        signs = np.sign(array)
        output[feature] = {
            "folds": int(array.size),
            "mean": float(array.mean()),
            "std": float(array.std(ddof=1)) if array.size > 1 else 0.0,
            "min": float(array.min()),
            "max": float(array.max()),
            "positive_folds": int((signs > 0).sum()),
            "negative_folds": int((signs < 0).sum()),
            "sign_consistent": bool((signs == signs[0]).all()),
        }
    return output


def code_tables(fold_pipelines: dict) -> dict:
    """Record fitted coefficients per fold for diagnosis, not causal interpretation."""
    tables = {}
    for fold, pipeline in fold_pipelines.items():
        if pipeline is None:
            tables[fold] = None
            continue
        scaler = pipeline.named_steps["standardscaler"]
        model = pipeline.named_steps["logisticregression"]
        feature_names = list(getattr(pipeline, "feature_names_in_", []))
        tables[fold] = {
            "features": feature_names,
            "coefficients_standardised": model.coef_[0].tolist(),
            "intercept": float(model.intercept_[0]),
            "means": scaler.mean_.tolist(),
            "scales": scaler.scale_.tolist(),
        }
    return tables
