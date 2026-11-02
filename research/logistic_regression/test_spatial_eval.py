import json
import tempfile
import unittest
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from audit_geometry import audit_geometry
from shapely.geometry import Polygon
from spatial_common import (
    FEATURES,
    TARGET,
    add_rank_normalized_score,
    block_bootstrap,
    drop_unknown_rows,
    fit_logistic,
    load_dataset,
    macro_metrics,
    make_folds,
    precision_recall_metrics,
    tune_logistic_c,
)

HERE = Path(__file__).resolve().parent


def synthetic_frame(n_wards=8, blocks=("NE", "NW")):
    rows = []
    for ward in range(1, n_wards + 1):
        block = blocks[(ward - 1) % len(blocks)]
        for event in (2758, 4309):
            rows.append({
                "event_id": event,
                "ward_id": ward,
                "ward_number": str(100 + ward),
                "block": block,
                TARGET: int(ward == 1 and event == 2758),
                "elevation_mean": float(20 - ward),
                "slope_mean": 1.0 + ward / 10,
                "impervious_frac": 0.1 * (ward % 5),
                "dist_to_water_m": 100.0 * ward,
                "road_density_km_per_sqkm": 5.0 + ward,
                "underpass_count": ward % 3,
            })
    return pd.DataFrame(rows)


class FoldTests(unittest.TestCase):
    def test_ward_grouping_keeps_both_events_in_one_fold(self):
        frame = synthetic_frame()
        folds = make_folds(frame, "quadrant")
        for fold in folds:
            test = frame.iloc[fold["test_idx"]]
            train = frame.iloc[fold["train_idx"]]
            self.assertTrue(set(test["ward_id"]).isdisjoint(train["ward_id"]))
            for ward, group in frame.groupby("ward_id"):
                if ward in set(test["ward_id"]):
                    self.assertTrue(set(group.index).issubset(set(fold["test_idx"])))
                else:
                    self.assertTrue(set(group.index).issubset(set(fold["train_idx"])))

    def test_every_ward_is_held_out_exactly_once(self):
        frame = synthetic_frame()
        folds = make_folds(frame, "quadrant")
        held_out = []
        for fold in folds:
            held_out.extend(fold["test_wards"])
        self.assertEqual(sorted(held_out), sorted(frame["ward_id"].unique().tolist()))

    def test_fold_assignments_are_reproducible(self):
        frame = synthetic_frame()
        first = make_folds(frame, "quadrant")
        second = make_folds(frame, "quadrant")
        self.assertEqual([f["test_wards"] for f in first],
                         [f["test_wards"] for f in second])
        self.assertEqual([f["test_wards"] for f in first],
                         [f["test_wards"] for f in second])


class LabelTests(unittest.TestCase):
    def test_unknown_is_excluded_not_converted_to_negative(self):
        frame = synthetic_frame()
        frame["label_status"] = "non_flooded"
        unknown_index = frame.loc[frame[TARGET].eq(0)].index[:2]
        frame.loc[unknown_index, "label_status"] = "unknown"
        filtered, audit = drop_unknown_rows(frame, "label_status")
        self.assertEqual(audit["unknown_excluded"], 2)
        self.assertEqual(len(filtered), len(frame) - 2)
        self.assertNotIn("unknown", filtered["label_status"].tolist())
        self.assertEqual(int(filtered[TARGET].sum()), int(frame[TARGET].sum()))

    def test_dataset_loader_rejects_missing_feature(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame = synthetic_frame().drop(columns=["underpass_count"])
            path = Path(tmp) / "data.csv"
            frame.to_csv(path, index=False)
            with self.assertRaises(ValueError):
                load_dataset(path)

    def test_dataset_loader_rejects_non_binary_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame = synthetic_frame()
            frame.loc[0, TARGET] = 2
            path = Path(tmp) / "data.csv"
            frame.to_csv(path, index=False)
            with self.assertRaises(ValueError):
                load_dataset(path)

    def test_dataset_loader_rejects_ward_in_two_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame = synthetic_frame()
            frame.loc[frame.index[0], "block"] = "SE"
            path = Path(tmp) / "data.csv"
            frame.to_csv(path, index=False)
            with self.assertRaises(ValueError):
                load_dataset(path)

    def test_unknown_status_column_is_excluded_by_loader(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame = synthetic_frame()
            frame["label_status"] = "non_flooded"
            frame.loc[0, "label_status"] = "unknown"
            path = Path(tmp) / "data.csv"
            frame.to_csv(path, index=False)
            loaded, audit = load_dataset(path, status_column="label_status")
            self.assertEqual(audit["status_audit"]["unknown_excluded"], 1)
            self.assertNotIn("unknown", loaded.get("label_status", pd.Series(dtype=str)).tolist())


class MetricTests(unittest.TestCase):
    def test_precision_recall_and_lift_at_k(self):
        y = [0, 0, 1, 0, 1]
        score = [0.1, 0.9, 0.8, 0.2, 0.7]
        result = precision_recall_metrics(y, score, [1, 2, 3, 4, 5],
                                          ["a"] * 5, k_values=(2,))
        block = result["k"]["2"]
        self.assertEqual(block["true_positives"], 1)
        self.assertAlmostEqual(block["precision"], 0.5)
        self.assertAlmostEqual(block["recall"], 0.5)
        self.assertAlmostEqual(block["lift"], 1.25)
        self.assertAlmostEqual(result["prevalence"], 0.4)

    def test_undefined_fold_reports_null_not_zero(self):
        result = precision_recall_metrics([0, 0, 0], [0.1, 0.2, 0.3],
                                          [1, 2, 3], ["a"] * 3, k_values=(2,))
        self.assertIsNone(result["average_precision"])
        self.assertIsNone(result["pr_auc_trapezoidal"])
        self.assertIsNone(result["k"]["2"]["recall"])
        self.assertEqual(result["k"]["2"]["precision"], 0.0)

    def test_k_is_reduced_when_test_set_is_smaller(self):
        result = precision_recall_metrics([0, 1, 0], [0.4, 0.9, 0.2],
                                          [1, 2, 3], ["a"] * 3, k_values=(10,))
        block = result["k"]["10"]
        self.assertEqual(block["effective_k"], 3)
        self.assertTrue(block["reduced"])
        self.assertAlmostEqual(block["precision"], 1 / 3)

    def test_tie_aware_precision_at_k_uses_expected_positive_fraction(self):
        result = precision_recall_metrics(
            [0, 0, 1, 1], [0.5, 0.5, 0.5, 0.5], [1, 2, 3, 4],
            ["a"] * 4, k_values=(1,))
        block = result["k"]["1"]
        self.assertEqual(block["ties_at_cutoff"], 4)
        self.assertAlmostEqual(block["tie_positive_fraction"], 0.5)
        self.assertAlmostEqual(block["expected_true_positives"], 0.5)
        self.assertAlmostEqual(block["precision"], 0.5)
        self.assertAlmostEqual(block["recall"], 0.25)

    def test_macro_skips_undefined_folds_but_reports_counts(self):
        defined = precision_recall_metrics([1, 0], [0.9, 0.1], [1, 2], ["a", "a"],
                                           k_values=(1,))
        undefined = precision_recall_metrics([0, 0], [0.9, 0.1], [3, 4], ["a", "a"],
                                             k_values=(1,))
        macro = macro_metrics([defined, undefined], k_values=(1,))
        self.assertEqual(macro["average_precision"]["defined_folds"], 1)
        self.assertEqual(macro["average_precision"]["total_folds"], 2)
        self.assertEqual(macro["average_precision"]["mean"], 1.0)

    def test_rank_normalisation_is_within_fold(self):
        frame = pd.DataFrame({
            "fold": ["a", "a", "b", "b"],
            "score": [10.0, 20.0, 100.0, 200.0],
        })
        ranked = add_rank_normalized_score(frame)
        self.assertAlmostEqual(ranked.loc[0, "rank_score"], 0.5)
        self.assertAlmostEqual(ranked.loc[1, "rank_score"], 1.0)
        self.assertAlmostEqual(ranked.loc[2, "rank_score"], 0.5)
        self.assertAlmostEqual(ranked.loc[3, "rank_score"], 1.0)

    def test_block_bootstrap_handles_undefined_replicates(self):
        frame = pd.DataFrame({
            "fold": ["a", "a", "b", "b"],
            TARGET: [1, 0, 0, 0],
            "score": [0.9, 0.1, 0.8, 0.2],
            "rank_score": [1.0, 0.5, 1.0, 0.5],
            "ward_id": [1, 2, 3, 4],
            "event_id": ["x"] * 4,
        })
        result = block_bootstrap(frame, k_values=(1,), n_boot=20, seed=1)
        self.assertEqual(result["n_blocks"], 2)
        self.assertIn("undefined_replicates", result)


class LeakageTests(unittest.TestCase):
    def test_preprocessing_statistics_fit_on_training_rows_only(self):
        train = pd.DataFrame({
            "elevation_mean": [1.0, 2.0, np.nan],
            "slope_mean": [1.0, 1.0, 1.0],
            "impervious_frac": [0.1, 0.1, 0.1],
            "dist_to_water_m": [1.0, 1.0, 1.0],
            "road_density_km_per_sqkm": [1.0, 1.0, 1.0],
            "underpass_count": [0, 0, 0],
            TARGET: [0, 1, 0],
        })
        pipeline = fit_logistic(train, FEATURES, C=1.0)
        imputer = pipeline.named_steps["simpleimputer"]
        scaler = pipeline.named_steps["standardscaler"]
        self.assertAlmostEqual(imputer.statistics_[0], 1.5)
        self.assertAlmostEqual(scaler.mean_[0], 1.5)
        changed_test = pd.DataFrame({
            "elevation_mean": [1000.0],
            "slope_mean": [1.0],
            "impervious_frac": [0.1],
            "dist_to_water_m": [1.0],
            "road_density_km_per_sqkm": [1.0],
            "underpass_count": [0],
        })
        pipeline.predict_proba(changed_test[FEATURES])
        self.assertAlmostEqual(imputer.statistics_[0], 1.5)
        self.assertAlmostEqual(scaler.mean_[0], 1.5)

    def test_inner_tuning_never_sees_held_out_ward(self):
        frame = synthetic_frame(n_wards=10)
        train = frame.loc[frame["block"].eq("NE")].reset_index(drop=True)
        C, info = tune_logistic_c(train, FEATURES, grid=(0.1, 1.0))
        self.assertIn("inner_splits", info)
        self.assertIn(C, (0.1, 1.0))

    def test_folds_preserve_groups_under_tuning(self):
        frame = synthetic_frame(n_wards=12)
        folds = make_folds(frame, "quadrant")
        for fold in folds:
            train = frame.iloc[fold["train_idx"]]
            test = frame.iloc[fold["test_idx"]]
            self.assertTrue(set(train["ward_id"]).isdisjoint(test["ward_id"]))

    def test_model_scores_are_reproducible_with_fixed_seed(self):
        frame = synthetic_frame(n_wards=12)
        train = frame.iloc[::2].reset_index(drop=True)
        test = frame.iloc[1::2].reset_index(drop=True)
        first = fit_logistic(train, FEATURES, C=1.0, seed=7)
        second = fit_logistic(train, FEATURES, C=1.0, seed=7)
        left = first.predict_proba(test[FEATURES])[:, 1]
        right = second.predict_proba(test[FEATURES])[:, 1]
        self.assertTrue(np.allclose(left, right, atol=0.0, rtol=0.0))


class GeometryTests(unittest.TestCase):
    def test_invalid_and_overlapping_polygons_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            wards = gpd.GeoDataFrame({
                "ward_id": [1, 2, 3],
                "ward_number": ["1", "2", "3"],
                "geometry": [
                    Polygon([(0, 0), (2, 0), (2, 2), (0, 2)]),
                    Polygon([(0.5, 0.5), (3, 0.5), (3, 3), (0.5, 3)]),
                    Polygon([(5, 5), (6, 6), (6, 5), (5, 6)]),
                ],
            }, crs="EPSG:32644")
            wards_path = tmp / "wards.geojson"
            wards.to_file(wards_path, driver="GeoJSON")
            crosswalk = pd.DataFrame({
                "ward_id": [1, 2, 3],
                "ward_number": ["1", "2", "3"],
                "zone_number": ["I", "I", "II"],
            })
            crosswalk_path = tmp / "crosswalk.csv"
            crosswalk.to_csv(crosswalk_path, index=False)
            dataset = synthetic_frame(n_wards=3)
            dataset["ward_id"] = [1, 1, 2, 2, 3, 3]
            dataset_path = tmp / "dataset.csv"
            dataset.to_csv(dataset_path, index=False)
            report = audit_geometry(wards_path, crosswalk_path, dataset_path,
                                    tmp / "out")
            self.assertEqual(report["invalid_geometries"], 1)
            self.assertEqual(report["overlap_summary"]["pairs_gt_1m2"], 1)
            self.assertGreater(report["overlap_summary"]["max_overlap_m2"], 1.0)
            self.assertTrue((tmp / "out" / "geometry_audit.json").exists())
            json.loads((tmp / "out" / "geometry_audit.json").read_text())


class RiskEngineCompatibilityTests(unittest.TestCase):
    def test_weighted_index_contract_is_unchanged(self):
        from model.risk_engine import score_ward
        row = pd.Series({
            "elevation_mean": 25.0,
            "slope_mean": 7.5,
            "impervious_frac": 0.5,
            "dist_to_water_m": 2500.0,
            "road_density_km_per_sqkm": 10.0,
            "underpass_count": 1,
        })
        score, risk_level, _depth, _window, _reasons = score_ward(
            row, 200.0, 0.0, duration_hours=3.0)
        self.assertAlmostEqual(score, 0.55)
        self.assertEqual(risk_level.value, "high")


if __name__ == "__main__":
    unittest.main()
