import unittest

import pandas as pd
from evaluate_ward_level import (
    A_TARGET,
    B_TARGET,
    aggregate_wards,
    graded_metrics,
    ward_label_audit,
    wide_predictions,
)
from spatial_common import TARGET, make_folds


def ward_event_frame():
    rows = []
    specs = {
        1: [(2758, 1), (4309, 0)],
        2: [(2758, 0), (4309, 0)],
        3: [(2758, 1)],
        4: [(2758, 0)],
    }
    for ward, events in specs.items():
        for event, target in events:
            rows.append({
                "event_id": event,
                "ward_id": ward,
                "ward_number": str(100 + ward),
                "block": "NE" if ward <= 2 else "NW",
                TARGET: target,
                "elevation_mean": 20.0 - ward,
                "slope_mean": 1.0 + ward / 10,
                "impervious_frac": 0.1 * ward,
                "dist_to_water_m": 100.0 * ward,
                "road_density_km_per_sqkm": 5.0 + ward,
                "underpass_count": ward % 3,
            })
    return pd.DataFrame(rows)


class AggregateTests(unittest.TestCase):
    def test_unknown_event_is_not_converted_to_negative(self):
        frame = ward_event_frame()
        wards = aggregate_wards(frame)
        ward1 = wards.loc[wards["ward_id"].eq(1)].iloc[0]
        self.assertEqual(int(ward1["n_detections"]), 1)
        self.assertEqual(int(ward1[A_TARGET]), 1)
        self.assertAlmostEqual(float(ward1[B_TARGET]), 0.5)
        self.assertEqual(ward1["coverage_status"], "complete")

    def test_partial_coverage_is_preserved(self):
        frame = ward_event_frame()
        wards = aggregate_wards(frame)
        ward3 = wards.loc[wards["ward_id"].eq(3)].iloc[0]
        self.assertEqual(int(ward3["n_available_events"]), 1)
        self.assertEqual(ward3["coverage_status"], "partial")
        self.assertEqual(int(ward3["n_missing_events"]), 1)
        self.assertEqual(int(ward3[A_TARGET]), 1)

    def test_one_row_per_ward(self):
        wards = aggregate_wards(ward_event_frame())
        self.assertEqual(len(wards), wards["ward_id"].nunique())
        self.assertEqual(sorted(wards["ward_id"].tolist()), [1, 2, 3, 4])

    def test_frequency_equals_any_detection_when_no_graded_values(self):
        wards = aggregate_wards(ward_event_frame())
        audit = ward_label_audit(wards)
        self.assertEqual(audit["frequency_distinct_values_all"], [0.0, 0.5, 1.0])
        # This synthetic set has a 0.5 ward, so B is not identical to A.
        self.assertFalse(audit["B_all_equals_A"])

    def test_fold_groups_keep_all_events_together(self):
        wards = aggregate_wards(ward_event_frame())
        wards["experimental_proxy_target"] = wards[A_TARGET]
        folds = make_folds(wards, "quadrant")
        for fold in folds:
            test = wards.iloc[fold["test_idx"]]
            train = wards.iloc[fold["train_idx"]]
            self.assertTrue(set(test["ward_id"]).isdisjoint(train["ward_id"]))


class GradedMetricTests(unittest.TestCase):
    def test_ndcg_and_spearman_known_order(self):
        relevance = [1.0, 0.5, 0.0]
        perfect = graded_metrics(relevance, [3.0, 2.0, 1.0], [1, 2, 3])
        reversed_order = graded_metrics(relevance, [1.0, 2.0, 3.0], [1, 2, 3])
        self.assertAlmostEqual(perfect["spearman"], 1.0)
        self.assertAlmostEqual(perfect["k"]["10"]["ndcg"], 1.0)
        self.assertLess(reversed_order["k"]["10"]["ndcg"], 1.0)
        self.assertAlmostEqual(reversed_order["spearman"], -1.0)

    def test_ndcg_is_undefined_when_all_relevance_is_zero(self):
        metrics = graded_metrics([0.0, 0.0], [0.9, 0.1], [1, 2])
        self.assertIsNone(metrics["k"]["10"]["ndcg"])
        self.assertIsNone(metrics["spearman"])

    def test_frequency_at_k_and_recall(self):
        metrics = graded_metrics([1.0, 0.5, 0.0], [3.0, 2.0, 1.0], [1, 2, 3],
                                 k_values=(2,))
        block = metrics["k"]["2"]
        self.assertAlmostEqual(block["mean_frequency"], 0.75)
        self.assertAlmostEqual(block["frequency_recall"], 1.0)
        self.assertAlmostEqual(block["lift"], 0.75 / 0.5)


class OutputTests(unittest.TestCase):
    def test_wide_output_contains_each_ward_once(self):
        wards = aggregate_wards(ward_event_frame())
        wards["zone_number"] = ["I", "I", "II", "II"]
        rows = []
        for model in ["elevation", "logistic_current"]:
            for _, ward in wards.iterrows():
                fold = "zone:I" if ward["ward_id"] <= 2 else "zone:II"
                rows.append({
                    "population": "all",
                    "scheme": "zone",
                    "model": model,
                    "fold": fold,
                    "ward_id": ward["ward_id"],
                    "score": float(ward["elevation_mean"]),
                })
        oof = pd.DataFrame(rows)
        wide = wide_predictions(oof, wards, "zone", "all")
        self.assertEqual(len(wide), len(wards))
        self.assertFalse(wide["ward_id"].duplicated().any())
        self.assertIn("elevation", wide.columns)
        self.assertIn("logistic_current", wide.columns)

    def test_wide_output_rejects_duplicate_wards(self):
        wards = aggregate_wards(ward_event_frame())
        wards["zone_number"] = ["I", "I", "II", "II"]
        oof = pd.DataFrame([
            {"population": "all", "scheme": "zone", "model": "elevation",
             "fold": "zone:I", "ward_id": 1, "score": 1.0},
            {"population": "all", "scheme": "zone", "model": "elevation",
             "fold": "zone:I", "ward_id": 1, "score": 2.0},
        ])
        with self.assertRaises(ValueError):
            wide_predictions(oof, wards, "zone", "all")


if __name__ == "__main__":
    unittest.main()
