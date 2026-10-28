import csv
import json
import unittest
from pathlib import Path
from predict import score

HERE = Path(__file__).resolve().parent


class LogisticEvidenceTests(unittest.TestCase):
    def test_heldout_predictions_and_identity(self):
        rows = list(csv.DictReader((HERE/'dataset.csv').read_text().splitlines()))
        keys = {(r['event_id'], r['ward_id']): r for r in rows}
        predictions = list(csv.DictReader((HERE/'results/oof_predictions.csv').read_text().splitlines()))
        self.assertEqual(len(predictions), len(keys))
        self.assertEqual(len({(r['event_id'], r['ward_id']) for r in predictions}), len(keys))
        counts = [0, 0, 0, 0]
        for p in predictions:
            row = keys[p['event_id'], p['ward_id']]
            model = json.loads((HERE/f"results/model_heldout_{p['block']}.json").read_text())
            self.assertNotIn(int(row['ward_id']), model['training_ward_ids'])
            self.assertAlmostEqual(score(model, row), float(p['proxy_score']), places=12)
            target, pred = int(row['experimental_proxy_target']), int(p['proxy_flag_at_0_5'])
            self.assertEqual(pred, int(score(model, row) >= .5))
            counts[target*2+pred] += 1
        self.assertEqual(counts, [304, 35, 2, 5])

    def test_preprocessing_is_training_only(self):
        import pandas as pd
        data = pd.read_csv(HERE/'dataset.csv')
        for block in ['NE', 'NW', 'SE', 'SW']:
            m = json.loads((HERE/f'results/model_heldout_{block}.json').read_text())
            train = data[data.block != block][m['features']]
            self.assertEqual(train.median().tolist(), m['medians'])
            for a, b in zip(train.fillna(train.median()).mean(), m['means']):
                self.assertAlmostEqual(a, b, places=10)

    def test_finite_scores_and_missing_value_imputation(self):
        import math
        m = json.loads((HERE/'results/model_full_refit.json').read_text())
        self.assertTrue(math.isfinite(score(m, {})))
        for row in csv.DictReader((HERE/'dataset.csv').read_text().splitlines()):
            self.assertTrue(0 <= score(m, row) <= 1)
