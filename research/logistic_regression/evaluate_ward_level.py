"""Ward-level historical flood-susceptibility evaluation.

One row per ward. Two explicit targets are compared on the same wards and folds:

A. ``any_detection``: 1 if any available event has a proxy detection.
B. ``detection_frequency``: detections divided by available events (0, 0.5, 1).

Neither target is verified flood susceptibility. A non-detection is not dryness, and a
ward with one available event has partial observation coverage. B is restricted to
complete-coverage wards (both events available) for its primary evaluation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from evaluate_spatial import MAIN_MODELS, MODELS, predict_model  # noqa: E402
from matplotlib.cm import ScalarMappable  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402
from scipy.stats import kendalltau, spearmanr  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.linear_model import Ridge  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
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
    macro_metrics,
    make_folds,
    precision_recall_metrics,
    sha256_file,
    write_json,
)

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
A_TARGET = "any_detection"
B_TARGET = "detection_frequency"
TOTAL_EVENTS = 2

TARGET_DEFINITIONS = {
    "A_any_detection": {
        "field": A_TARGET,
        "definition": "1 if at least one available event has a proxy detection; "
                      "0 if all available events are non-detections.",
        "population": "all wards with at least one available event",
        "limitation": "Ignores recurrence; a one-event ward can be a negative with "
                      "partial coverage; non-detection is not confirmed dryness.",
    },
    "B_detection_frequency": {
        "field": B_TARGET,
        "definition": "detections / available events (0, 0.5 or 1 for two events).",
        "population": "complete-coverage wards only (both events available) for primary; "
                      "all wards as a sensitivity.",
        "limitation": "Event-weighted, not ward-weighted; only two events; frequency "
                      "0 does not establish dryness; partial coverage is excluded.",
    },
}


def aggregate_wards(df: pd.DataFrame, total_events: int = TOTAL_EVENTS) -> pd.DataFrame:
    """Collapse ward-event rows to one row per ward without inventing unknown labels."""
    if df.empty:
        raise ValueError("Cannot aggregate an empty dataset")
    static = df.groupby("ward_id")[FEATURES].nunique()
    if (static > 1).any().any():
        raise ValueError("Static features differ across events for at least one ward")
    grouped = df.groupby("ward_id", sort=True)
    wards = grouped.agg({
        "ward_number": "first",
        "block": "first",
        "event_id": lambda values: ";".join(sorted({str(value) for value in values})),
        TARGET: "sum",
        **{feature: "first" for feature in FEATURES},
    }).reset_index()
    wards = wards.rename(columns={"event_id": "available_events", TARGET: "n_detections"})
    wards["n_available_events"] = wards["available_events"].str.count(";") + 1
    wards["n_missing_events"] = total_events - wards["n_available_events"]
    if (wards["n_missing_events"] < 0).any():
        raise ValueError("A ward has more events than the declared total")
    wards["coverage_status"] = np.where(
        wards["n_available_events"] >= total_events, "complete", "partial")
    wards[A_TARGET] = (wards["n_detections"] > 0).astype(int)
    wards[B_TARGET] = wards["n_detections"] / wards["n_available_events"]
    wards["experimental_proxy_target"] = wards[A_TARGET]
    wards["event_id"] = "ward"
    return wards.sort_values("ward_id").reset_index(drop=True)


def ward_label_audit(wards: pd.DataFrame, boundary_wards=None) -> dict:
    frequency = wards[B_TARGET].value_counts().sort_index().to_dict()
    complete = wards.loc[wards["coverage_status"].eq("complete")]
    frequency_values_all = sorted(wards[B_TARGET].dropna().unique().tolist())
    frequency_values_complete = sorted(complete[B_TARGET].dropna().unique().tolist())
    b_all_equals_a = bool(np.array_equal(
        wards[A_TARGET].to_numpy(), wards[B_TARGET].to_numpy()))
    b_complete_supported = bool(
        complete[A_TARGET].sum() >= 2 and len(frequency_values_complete) >= 3)
    a_complete_supported = bool(complete[A_TARGET].sum() >= 2)
    audit = {
        "ward_count": int(len(wards)),
        "target_definitions": TARGET_DEFINITIONS,
        "coverage_counts": wards["coverage_status"].value_counts().to_dict(),
        "events_available_counts": wards["n_available_events"].value_counts()
        .sort_index().to_dict(),
        "n_detections_distribution": wards["n_detections"].value_counts()
        .sort_index().to_dict(),
        "target_A_positives": int(wards[A_TARGET].sum()),
        "target_A_prevalence": float(wards[A_TARGET].mean()),
        "target_B_mean_frequency": float(wards[B_TARGET].mean()),
        "target_B_frequency_distribution": {str(key): int(value)
                                            for key, value in frequency.items()},
        "frequency_distinct_values_all": frequency_values_all,
        "frequency_distinct_values_complete": frequency_values_complete,
        "complete_coverage_wards": int(len(complete)),
        "complete_target_A_positives": int(complete[A_TARGET].sum()),
        "B_all_equals_A": b_all_equals_a,
        "B_complete_supported": b_complete_supported,
        "A_complete_supported": a_complete_supported,
        "A_complete_reason": (
            "Complete-coverage population has at least two positives."
            if a_complete_supported else
            f"Complete-coverage population has only "
            f"{int(complete[A_TARGET].sum())} positive ward(s); metrics there are "
            f"descriptive only, not a comparison."),
        "B_support_reason": _b_support_reason(
            b_all_equals_a, b_complete_supported, complete, frequency_values_complete),
        "target_A_vs_B_spearman": _spearman(wards[A_TARGET], wards[B_TARGET]),
        "partial_wards": sorted(wards.loc[wards["coverage_status"].eq("partial"),
                                          "ward_id"].tolist()),
        "positive_wards_A": sorted(wards.loc[wards[A_TARGET].eq(1), "ward_id"].tolist()),
        "positive_wards_B": sorted(wards.loc[wards[B_TARGET] > 0, "ward_id"].tolist()),
        "notes": [
            "A ward with one available event is partial coverage, not a confirmed dry ward.",
            "Target B is event-weighted; target A is ward-weighted.",
            "No ward absent from the frozen table is assigned a label.",
        ],
    }
    if boundary_wards is not None:
        missing = sorted(set(boundary_wards) - set(wards["ward_id"]))
        audit["absent_wards"] = missing
        audit["absent_ward_count"] = len(missing)
    return audit


def _b_support_reason(equals_a: bool, complete_supported: bool,
                      complete: pd.DataFrame, frequency_values) -> str:
    if complete_supported:
        return "Frequency target has at least two complete-coverage positives and graded values."
    if equals_a:
        return ("Frequency is 0 or 1 for every ward and is identical to target A. "
                "Every detection occurs in a ward with only one available event, "
                "or in ward 16 where both events are positive; no ward has a 0.5 "
                "frequency. Target B is not separable from target A on this dataset.")
    if len(complete) and int(complete[A_TARGET].sum()) < 2:
        return (f"Complete-coverage population has only "
                f"{int(complete[A_TARGET].sum())} positive ward(s); frequency-based "
                f"ranking metrics are not estimable.")
    return (f"Frequency values are {frequency_values}; at least two complete-coverage "
            f"positives and graded frequency values are required.")


def _spearman(left, right):
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    if left.size < 2 or np.ptp(left) == 0 or np.ptp(right) == 0:
        return None
    result = spearmanr(left, right, nan_policy="omit")
    value = float(result.correlation)
    return None if not np.isfinite(value) else value


def _kendall(left, right):
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    if left.size < 2 or np.ptp(left) == 0 or np.ptp(right) == 0:
        return None
    result = kendalltau(left, right, nan_policy="omit")
    value = float(result.correlation)
    return None if not np.isfinite(value) else value


def _ndcg_at_k(relevance, score, ward_id, k: int) -> float | None:
    relevance = np.asarray(relevance, dtype=float)
    score = np.asarray(score, dtype=float)
    if len(relevance) == 0:
        return None
    order = np.lexsort((np.asarray(ward_id), -score))
    effective_k = min(int(k), len(relevance))
    top = order[:effective_k]
    discounts = 1.0 / np.log2(np.arange(2, effective_k + 2))
    dcg = float(np.sum((2 ** relevance[top] - 1) * discounts))
    ideal = np.sort(relevance)[::-1][:effective_k]
    idcg = float(np.sum((2 ** ideal - 1) * discounts))
    return dcg / idcg if idcg > 0 else None


def graded_metrics(relevance, score, ward_id, k_values=K_VALUES) -> dict:
    relevance = np.asarray(relevance, dtype=float)
    score = np.asarray(score, dtype=float)
    if len(relevance) != len(score):
        raise ValueError("relevance and score lengths differ")
    if not np.isfinite(score).all():
        raise ValueError("Scores must be finite")
    ward_id = np.asarray(ward_id)
    n = int(len(relevance))
    total = float(relevance.sum())
    mean = float(relevance.mean()) if n else None
    result = {
        "n": n,
        "mean_frequency": mean,
        "nonzero_wards": int((relevance > 0).sum()),
        "spearman": _spearman(score, relevance) if n > 1 else None,
        "kendall": _kendall(score, relevance) if n > 1 else None,
        "k": {},
    }
    for requested_k in k_values:
        effective_k = min(int(requested_k), n)
        order = np.lexsort((ward_id, -score))
        top = order[:effective_k]
        top_mean = float(relevance[top].mean())
        recall = float(relevance[top].sum() / total) if total > 0 else None
        lift = top_mean / mean if mean and mean > 0 else None
        result["k"][str(requested_k)] = {
            "requested_k": int(requested_k),
            "effective_k": effective_k,
            "reduced": bool(effective_k < requested_k),
            "ndcg": _ndcg_at_k(relevance, score, ward_id, requested_k),
            "mean_frequency": top_mean,
            "frequency_recall": recall,
            "lift": None if lift is None else float(lift),
        }
    return result


def macro_graded(per_fold: list[dict], k_values=K_VALUES) -> dict:
    keys = ["spearman", "kendall"]
    for k in k_values:
        keys += [f"ndcg_at_{k}", f"mean_frequency_at_{k}",
                 f"frequency_recall_at_{k}", f"lift_at_{k}"]
    output = {}
    for key in keys:
        values = []
        for fold in per_fold:
            if key in {"spearman", "kendall"}:
                value = fold.get(key)
            else:
                k = key.rsplit("_", 1)[1]
                block = fold.get("k", {}).get(k)
                if block is None:
                    continue
                if key.startswith("ndcg_at_"):
                    value = block["ndcg"]
                elif key.startswith("mean_frequency_at_"):
                    value = block["mean_frequency"]
                elif key.startswith("frequency_recall_at_"):
                    value = block["frequency_recall"]
                else:
                    value = block["lift"]
            if value is not None and np.isfinite(value):
                values.append(float(value))
        output[key] = {
            "mean": float(np.mean(values)) if values else None,
            "median": float(np.median(values)) if values else None,
            "min": float(np.min(values)) if values else None,
            "max": float(np.max(values)) if values else None,
            "defined_folds": len(values),
            "total_folds": len(per_fold),
        }
    return output


def block_bootstrap_graded(oof: pd.DataFrame, k_values=K_VALUES, n_boot: int = 1000,
                           seed: int = SEED, fold_subset=None,
                           estimand: str | None = None) -> dict:
    rng = np.random.default_rng(seed)
    all_folds = sorted(oof["fold"].unique())
    folds = all_folds if fold_subset is None else sorted(set(all_folds) & set(fold_subset))
    if len(folds) < 2:
        return {"status": "insufficient_blocks", "n_blocks": len(folds)}
    positive_blocks = [fold for fold in folds
                       if int((oof.loc[oof["fold"].eq(fold), B_TARGET] > 0).sum()) > 0]
    collected: dict[str, list[float]] = {}
    undefined = 0
    for _ in range(int(n_boot)):
        sampled = rng.choice(folds, size=len(folds), replace=True)
        sample = pd.concat([oof.loc[oof["fold"].eq(fold)] for fold in sampled],
                           ignore_index=True)
        metrics = graded_metrics(sample[B_TARGET], sample["rank_score"],
                                 sample["ward_id"], k_values)
        if metrics["spearman"] is None:
            undefined += 1
            continue
        collected.setdefault("spearman", []).append(metrics["spearman"])
        for k in k_values:
            block = metrics["k"][str(k)]
            if block["ndcg"] is not None:
                collected.setdefault(f"ndcg_at_{k}", []).append(block["ndcg"])
            collected.setdefault(f"mean_frequency_at_{k}", []).append(
                block["mean_frequency"])
    summary = {
        "n_boot": int(n_boot),
        "n_blocks": len(folds),
        "positive_blocks": positive_blocks,
        "n_positive_blocks": len(positive_blocks),
        "estimand": estimand or (
            "with-replacement resample of geographic blocks; Spearman/NDCG against "
            "detection frequency, conditional on a defined correlation"),
        "undefined_replicates": int(undefined),
        "metrics": {},
    }
    for key, values in collected.items():
        arr = np.asarray(values, dtype=float)
        summary["metrics"][key] = {
            "mean": float(arr.mean()),
            "lower_2_5": float(np.percentile(arr, 2.5)),
            "upper_97_5": float(np.percentile(arr, 97.5)),
            "valid_replicates": int(arr.size),
        }
    return summary


def fit_ridge_frequency(train: pd.DataFrame):
    if train[B_TARGET].nunique() < 2:
        return None
    pipeline = make_pipeline(
        SimpleImputer(strategy="median", keep_empty_features=True),
        StandardScaler(),
        Ridge(alpha=1.0),
    )
    pipeline.fit(train[FEATURES], train[B_TARGET])
    return pipeline


def rank_frame(frame: pd.DataFrame, scores: np.ndarray) -> pd.DataFrame:
    out = frame.copy()
    out["score"] = scores
    out = out.sort_values(["score", "ward_id"], ascending=[False, True]).reset_index(drop=True)
    out["rank_in_fold"] = np.arange(1, len(out) + 1)
    return out


def wide_predictions(oof: pd.DataFrame, wards: pd.DataFrame, scheme: str,
                     population: str) -> pd.DataFrame:
    subset = oof.loc[(oof["scheme"].eq(scheme)) & (oof["population"].eq(population))]
    duplicated = subset.duplicated(["ward_id", "model"])
    if duplicated.any():
        raise ValueError("Ward-level OOF input contains duplicate ward/model rows")
    scores = subset.pivot_table(index="ward_id", columns="model", values="score",
                                aggfunc="first")
    folds = subset.groupby("ward_id")["fold"].first().rename("fold")
    base = wards[["ward_id", "ward_number", "block", "zone_number",
                  "n_available_events", "n_missing_events", "n_detections",
                  A_TARGET, B_TARGET, "coverage_status", "available_events"]].copy()
    base = base.merge(folds, on="ward_id", how="left")
    merged = base.merge(scores, on="ward_id", how="left")
    if merged["ward_id"].duplicated().any():
        raise ValueError("Ward-level prediction output duplicates a ward")
    if len(merged) != wards["ward_id"].nunique():
        raise ValueError("Ward-level prediction output does not cover every ward once")
    return merged.sort_values("ward_id").reset_index(drop=True)


def evaluate_population(frame: pd.DataFrame, zone_map: pd.DataFrame, scheme: str,
                        population: str, args) -> tuple[pd.DataFrame, dict]:
    folds = make_folds(frame, scheme, zone_map)
    oof_parts = []
    fold_meta = []
    for fold_index, fold in enumerate(folds):
        train = frame.iloc[fold["train_idx"]].reset_index(drop=True)
        test = frame.iloc[fold["test_idx"]].reset_index(drop=True)
        fold_meta.append({
            "fold": fold["fold"],
            "test_unit": fold["test_unit"],
            "test_wards": fold["test_wards"],
            "n_train": fold["n_train"],
            "n_test": fold["n_test"],
            "train_positives_A": fold["train_positives"],
            "test_positives_A": fold["test_positives"],
            "test_frequency": float(test[B_TARGET].mean()),
        })
        for model_index, (name, spec) in enumerate(MODELS.items()):
            rng = np.random.default_rng(
                args.seed + fold_index * 100 + model_index + (1000 if scheme == "quadrant" else 0))
            scores, status, _info = predict_model(name, spec, train, test, rng)
            if status == "ok":
                ranked = rank_frame(test, scores)
            else:
                ranked = test.copy()
                ranked["score"] = np.nan
                ranked["rank_in_fold"] = np.nan
            ranked["population"] = population
            ranked["scheme"] = scheme
            ranked["model"] = name
            ranked["fold"] = fold["fold"]
            ranked["status"] = status
            oof_parts.append(ranked[[
                "population", "scheme", "model", "fold", "ward_id", "ward_number",
                "block", A_TARGET, B_TARGET, "coverage_status", "score",
                "rank_in_fold", "status",
            ]])
        if population == "complete":
            pipeline = fit_ridge_frequency(train)
            if pipeline is None:
                scores, status = np.full(len(test), np.nan), "insufficient_frequency_values"
            else:
                scores, status = pipeline.predict(test[FEATURES]), "ok"
            if status == "ok":
                ranked = rank_frame(test, scores)
            else:
                ranked = test.copy()
                ranked["score"] = np.nan
                ranked["rank_in_fold"] = np.nan
            ranked["population"] = population
            ranked["scheme"] = scheme
            ranked["model"] = "ridge_frequency"
            ranked["fold"] = fold["fold"]
            ranked["status"] = status
            oof_parts.append(ranked[[
                "population", "scheme", "model", "fold", "ward_id", "ward_number",
                "block", A_TARGET, B_TARGET, "coverage_status", "score",
                "rank_in_fold", "status",
            ]])
    return pd.concat(oof_parts, ignore_index=True), {
        "folds": fold_meta,
        "fold_diagnostics": {
            "n_folds": len(folds),
            "folds_without_A_positives": [
                fold["fold"] for fold in fold_meta if fold["test_positives_A"] == 0],
            "folds_without_training_A_positives": [
                fold["fold"] for fold in fold_meta if fold["train_positives_A"] == 0],
            "folds_without_frequency": [
                fold["fold"] for fold in fold_meta if fold["test_frequency"] == 0],
        },
    }


def evaluate_models(oof: pd.DataFrame, results: dict, args) -> dict:
    output = {}
    for population in oof["population"].unique():
        output[population] = {}
        for scheme in oof["scheme"].unique():
            subset = oof.loc[(oof["population"].eq(population)) &
                             (oof["scheme"].eq(scheme))]
            scheme_output = {}
            for model in subset["model"].unique():
                rows = subset.loc[subset["model"].eq(model)].copy()
                valid = rows.loc[rows["status"].eq("ok")].copy()
                if valid.empty:
                    continue
                valid = add_rank_normalized_score(valid)
                valid["event_id"] = "ward"
                valid[TARGET] = valid[A_TARGET]
                binary_pooled = precision_recall_metrics(
                    valid[A_TARGET], valid["rank_score"], valid["ward_id"],
                    valid["event_id"], tuple(args.k))
                binary_raw = precision_recall_metrics(
                    valid[A_TARGET], valid["score"], valid["ward_id"],
                    ["ward"] * len(valid), tuple(args.k))
                graded_pooled = graded_metrics(
                    valid[B_TARGET], valid["rank_score"], valid["ward_id"], tuple(args.k))
                graded_raw = graded_metrics(
                    valid[B_TARGET], valid["score"], valid["ward_id"], tuple(args.k))
                binary_folds, graded_folds = [], []
                for fold in sorted(valid["fold"].unique()):
                    fold_rows = valid.loc[valid["fold"].eq(fold)]
                    bm = precision_recall_metrics(
                        fold_rows[A_TARGET], fold_rows["score"], fold_rows["ward_id"],
                        ["ward"] * len(fold_rows), tuple(args.k))
                    bm["fold"] = fold
                    gm = graded_metrics(
                        fold_rows[B_TARGET], fold_rows["score"], fold_rows["ward_id"],
                        tuple(args.k))
                    gm["fold"] = fold
                    binary_folds.append(bm)
                    graded_folds.append(gm)
                entry = {
                    "target_A": {
                        "pooled_rank": binary_pooled,
                        "pooled_raw_diagnostic": binary_raw,
                        "per_fold": binary_folds,
                        "macro": macro_metrics(binary_folds, tuple(args.k)),
                    },
                    "target_B": {
                        "pooled_rank": graded_pooled,
                        "pooled_raw_diagnostic": graded_raw,
                        "per_fold": graded_folds,
                        "macro": macro_graded(graded_folds, tuple(args.k)),
                    },
                }
                if model in MAIN_MODELS:
                    entry["target_A"]["bootstrap"] = block_bootstrap(
                        valid, tuple(args.k), n_boot=args.n_boot, seed=args.seed,
                        score_column="rank_score")
                    positive_folds = [
                        fold for fold in sorted(valid["fold"].unique())
                        if int(valid.loc[valid["fold"].eq(fold), A_TARGET].sum()) > 0]
                    if len(positive_folds) >= 2:
                        entry["target_A"]["bootstrap_positive_blocks"] = block_bootstrap(
                            valid, tuple(args.k), n_boot=args.n_boot, seed=args.seed,
                            score_column="rank_score", fold_subset=positive_folds,
                            estimand="with-replacement resample of positive blocks")
                    entry["target_B"]["bootstrap"] = block_bootstrap_graded(
                        valid, tuple(args.k), n_boot=args.n_boot, seed=args.seed)
                scheme_output[model] = entry
            output[population][scheme] = scheme_output
    return output


def apply_target_support(results: dict, audit: dict) -> dict:
    """Do not present an unsupported frequency target as evidence."""
    support = {
        "target_A_supported": True,
        "target_A_complete_supported": audit["A_complete_supported"],
        "target_A_complete_reason": audit["A_complete_reason"],
        "target_B_all_equals_A": audit["B_all_equals_A"],
        "target_B_complete_supported": audit["B_complete_supported"],
        "target_B_support_reason": audit["B_support_reason"],
        "frequency_distinct_values_all": audit["frequency_distinct_values_all"],
        "frequency_distinct_values_complete": audit["frequency_distinct_values_complete"],
        "complete_coverage_wards": audit["complete_coverage_wards"],
        "complete_target_A_positives": audit["complete_target_A_positives"],
    }
    for population, schemes in results.items():
        for models in schemes.values():
            for entry in models.values():
                target_b = entry.get("target_B", {})
                if population == "complete" and not audit["A_complete_supported"]:
                    entry["target_A"]["support_status"] = (
                        "descriptive_only_insufficient_positives")
                    entry["target_A"]["support_reason"] = audit["A_complete_reason"]
                if population == "complete" and not audit["B_complete_supported"]:
                    entry["target_B"] = {
                        "status": "unsupported",
                        "reason": audit["B_support_reason"],
                        "descriptive_metrics_not_evidence": target_b,
                    }
                elif population == "all" and audit["B_all_equals_A"]:
                    entry["target_B"] = {
                        "status": "binary_only",
                        "equals_target_A": True,
                        "reason": audit["B_support_reason"],
                        "descriptive_metrics_not_evidence": target_b,
                    }
    return support


def write_fold_assignments(output: Path, meta: dict, wards: pd.DataFrame) -> None:
    rows = []
    lookup = wards.set_index("ward_id")
    for population, info in meta["populations"].items():
        for scheme in ["zone", "quadrant"]:
            for fold in info[f"{scheme}_folds"]["folds"]:
                for ward_id in fold["test_wards"]:
                    row = lookup.loc[ward_id]
                    rows.append({
                        "population": population,
                        "scheme": scheme,
                        "fold": fold["fold"],
                        "ward_id": ward_id,
                        "n_available_events": int(row["n_available_events"]),
                        "coverage_status": row["coverage_status"],
                        A_TARGET: int(row[A_TARGET]),
                        B_TARGET: float(row[B_TARGET]),
                    })
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "ward_level_fold_assignments.csv", index=False)


def write_per_fold_csv(output: Path, results: dict) -> None:
    rows = []
    for population, schemes in results["results"].items():
        for scheme, models in schemes.items():
            for model, entry in models.items():
                for target_key, label in [("target_A", "A"), ("target_B", "B")]:
                    target = entry[target_key]
                    if target_key == "target_B" and target.get("status"):
                        continue
                    for fold in target["per_fold"]:
                        row = {
                            "population": population,
                            "scheme": scheme,
                            "model": model,
                            "target": label,
                            "fold": fold.get("fold", "pooled"),
                            "n": fold.get("n"),
                            "positives_A": fold.get("positives"),
                            "mean_frequency": fold.get("mean_frequency"),
                            "average_precision": fold.get("average_precision"),
                            "spearman": fold.get("spearman"),
                            "kendall": fold.get("kendall"),
                        }
                        for k, block in fold.get("k", {}).items():
                            row[f"precision_at_{k}"] = block.get("precision")
                            row[f"recall_at_{k}"] = block.get("recall")
                            row[f"ndcg_at_{k}"] = block.get("ndcg")
                            row[f"mean_frequency_at_{k}"] = block.get("mean_frequency")
                            row[f"frequency_recall_at_{k}"] = block.get("frequency_recall")
                        rows.append(row)
    pd.DataFrame(rows).to_csv(output / "ward_level_metrics_per_fold.csv",
                              index=False, na_rep="")


def run(args) -> Path:
    output = args.output
    if output.exists():
        raise FileExistsError(f"Output directory already exists: {output}")
    output.mkdir(parents=True)
    from spatial_common import load_dataset, load_zone_map

    df, dataset_audit = load_dataset(args.dataset, target=TARGET,
                                     status_column=args.status_column)
    zone_map = load_zone_map(args.crosswalk)
    wards = aggregate_wards(df)
    wards = attach_zones(wards, zone_map)
    boundary = pd.read_csv(args.crosswalk)
    boundary_wards = pd.to_numeric(boundary["ward_id"], errors="raise").astype(int).tolist()
    audit = ward_label_audit(wards, boundary_wards)
    write_json(output / "ward_level_label_audit.json", audit)
    write_json(output / "dataset_audit.json", dataset_audit)
    wards.to_csv(output / "ward_level_input.csv", index=False)

    complete = wards.loc[wards["coverage_status"].eq("complete")].reset_index(drop=True)
    datasets = {"all": wards, "complete": complete}
    oof_parts = []
    meta: dict = {"populations": {}, "schemes": ["zone", "quadrant"],
                  "targets": TARGET_DEFINITIONS, "seed": args.seed,
                  "n_boot": args.n_boot, "k_values": list(args.k)}
    for population, frame in datasets.items():
        meta["populations"][population] = {
            "wards": int(len(frame)),
            "target_A_positives": int(frame[A_TARGET].sum()),
            "target_A_prevalence": float(frame[A_TARGET].mean()),
            "target_B_mean_frequency": float(frame[B_TARGET].mean()),
            "target_B_nonzero": int((frame[B_TARGET] > 0).sum()),
        }
        for scheme in ["zone", "quadrant"]:
            oof, fold_meta = evaluate_population(frame, zone_map, scheme, population, args)
            oof_parts.append(oof)
            meta["populations"][population][f"{scheme}_folds"] = fold_meta
    oof = pd.concat(oof_parts, ignore_index=True)
    oof.to_csv(output / "ward_level_oof_long.csv", index=False)

    results = {
        "meta": meta,
        "label_audit": audit,
        "results": evaluate_models(oof, {}, args),
    }
    results["target_support"] = apply_target_support(results["results"], audit)
    results["feature_sign_audit"] = _ward_sign_audit(complete)
    results["feature_correlations_target_A_all"] = feature_correlations(
        wards, target=A_TARGET)
    results["coefficient_stability_zone_all"] = _ward_coefficient_stability(
        wards, zone_map)
    write_json(output / "ward_level_metrics.json", results)
    write_fold_assignments(output, meta, wards)
    write_per_fold_csv(output, results)

    wide = wide_predictions(oof, wards, "zone", "all")
    wide.to_csv(output / "ward_level_predictions.csv", index=False)
    if wide["ward_id"].duplicated().any():
        raise ValueError("wide ward output contains duplicate wards")
    plot_ward_geography(output, args.wards, wide, "logistic_l2_tuned")
    write_manifest(output, args, wards, meta)
    return output


def _ward_coefficient_stability(frame: pd.DataFrame, zone_map: pd.DataFrame) -> dict:
    folds = make_folds(frame, "zone", zone_map)
    by_fold = {}
    for fold in folds:
        train = frame.iloc[fold["train_idx"]].reset_index(drop=True)
        pipeline = fit_logistic(train, FEATURES, C=1.0, class_weight="balanced")
        if pipeline is None:
            by_fold[fold["fold"]] = None
        else:
            by_fold[fold["fold"]] = code_tables({fold["fold"]: pipeline})[fold["fold"]]
    return coefficient_stability(by_fold)


def _ward_sign_audit(frame: pd.DataFrame) -> dict:
    pipeline = fit_logistic(frame, FEATURES, C=1.0, class_weight="balanced")
    if pipeline is None:
        return {"status": "unavailable"}
    model = pipeline.named_steps["logisticregression"]
    names = list(pipeline.feature_names_in_)
    coefficients = dict(zip(names, model.coef_[0].tolist()))
    expected = {
        "elevation_mean": -1, "slope_mean": -1, "impervious_frac": 1,
        "dist_to_water_m": -1, "road_density_km_per_sqkm": 1,
        "underpass_count": 1,
    }
    warnings = []
    for feature, sign in expected.items():
        value = coefficients.get(feature)
        if value is not None and np.sign(value) != sign:
            warnings.append({"feature": feature, "coefficient": value,
                             "expected_sign": sign,
                             "interpretation": "unexpected sign; not causal"})
    return {"scope": "full-data refit for diagnosis, not an OOF result",
            "coefficients_standardised": coefficients,
            "sign_warnings": warnings}


def plot_ward_geography(output: Path, wards_path: Path, wide: pd.DataFrame,
                        model: str) -> None:
    import geopandas as gpd
    geometry = gpd.read_file(wards_path)
    column = model if model in wide.columns else None
    if column is None:
        return
    merged = geometry.merge(wide[["ward_id", column, A_TARGET]], on="ward_id", how="left")
    figure, ax = plt.subplots(figsize=(8, 7))
    merged.plot(column=column, cmap="viridis", vmin=0, vmax=1, linewidth=0.2,
                edgecolor="white", ax=ax, missing_kwds={"color": "lightgrey"})
    positives = merged.loc[merged[A_TARGET].eq(1)]
    if not positives.empty:
        positives.centroid.plot(ax=ax, color="red", marker="x", markersize=45)
    ax.set_axis_off()
    ax.set_title(f"Ward-level out-of-fold score ({model}); red X = any detection")
    sm = ScalarMappable(norm=Normalize(vmin=0, vmax=1), cmap="viridis")
    sm.set_array([])
    figure.colorbar(sm, ax=ax, fraction=0.03, pad=0.02)
    figure.savefig(output / "ward_level_geographic_oof.png", dpi=200,
                   bbox_inches="tight")
    plt.close(figure)


def write_manifest(output: Path, args, wards: pd.DataFrame, meta: dict) -> None:
    import geopandas
    import sklearn

    write_json(output / "run_manifest.json", {
        "command": " ".join(__import__("sys").argv),
        "python": __import__("platform").python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__,
        "geopandas": geopandas.__version__,
        "seed": args.seed,
        "k_values": list(args.k),
        "n_boot": args.n_boot,
        "dataset_sha256": sha256_file(args.dataset),
        "script_sha256": sha256_file(Path(__file__)),
        "rows": int(len(wards)),
        "wards": int(wards["ward_id"].nunique()),
        "target_A_positives": int(wards[A_TARGET].sum()),
        "target_B_mean_frequency": float(wards[B_TARGET].mean()),
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=HERE / "dataset.csv")
    parser.add_argument("--status-column", default=None,
                        help="optional label-status column; unknown rows are excluded")
    parser.add_argument("--wards", type=Path,
                        default=REPO_ROOT / "data/processed/wards.geojson")
    parser.add_argument("--crosswalk", type=Path,
                        default=REPO_ROOT / "data/processed/ward_crosswalk.csv")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--bootstrap", dest="n_boot", type=int, default=1000)
    parser.add_argument("--k", type=int, nargs="+", default=list(K_VALUES))
    args = parser.parse_args()
    path = run(args)
    print(f"Wrote ward-level evaluation to {path}")


if __name__ == "__main__":
    main()
