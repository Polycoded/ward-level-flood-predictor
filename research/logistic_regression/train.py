"""Reproduce fixed logistic-only exploratory geographic evaluation."""
import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, average_precision_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from predict import score

HERE = Path(__file__).resolve().parent
FEATURES = ['elevation_mean', 'slope_mean', 'impervious_frac', 'dist_to_water_m',
            'road_density_km_per_sqkm', 'underpass_count']
TARGET = 'experimental_proxy_target'


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n')


def fit(data):
    pipe = make_pipeline(SimpleImputer(strategy='median', keep_empty_features=True),
                         StandardScaler(), LogisticRegression(C=1, solver='liblinear',
                         class_weight='balanced', max_iter=2000, random_state=42))
    pipe.fit(data[FEATURES], data[TARGET])
    impute, scale, clf = pipe.steps[0][1], pipe.steps[1][1], pipe.steps[2][1]
    if np.any(clf.n_iter_ >= 2000):
        raise RuntimeError('Logistic regression did not converge')
    return dict(features=FEATURES, medians=impute.statistics_.tolist(),
                means=scale.mean_.tolist(), scales=scale.scale_.tolist(),
                coefficients=clf.coef_[0].tolist(), intercept=float(clf.intercept_[0]),
                target='satellite-mapped inundation proxy; uncalibrated', threshold=.5)


def metrics(y, probabilities):
    y = np.asarray(y); p = np.asarray(probabilities)
    tn, fp, fn, tp = map(int, confusion_matrix(y, p >= .5, labels=[0, 1]).ravel())
    positives, negatives = tp+fn, tn+fp
    return dict(rows=len(y), positives=positives, confusion_matrix=[[tn, fp], [fn, tp]],
                precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/positives if positives else None,
                f1=2*tp/(2*tp+fp+fn) if positives else None,
                balanced_accuracy=(tp/positives+tn/negatives)/2 if positives and negatives else None,
                average_precision=float(average_precision_score(y, p)) if positives and negatives else None,
                accuracy_secondary=(tn+tp)/len(y))


def run(output):
    data = pd.read_csv(HERE/'dataset.csv')
    assert len(data) == 346 and data.ward_id.nunique() == 186 and data[TARGET].sum() == 7
    assert not data.duplicated(['event_id', 'ward_id']).any()
    assert data.groupby('ward_id').block.nunique().eq(1).all()
    assert data.accepted_label.eq('unknown').all()
    output.mkdir(parents=True, exist_ok=False)
    parts, folds = [], []
    for block in ['NE', 'NW', 'SE', 'SW']:
        train, test = data[data.block != block], data[data.block == block]
        assert set(train.ward_id).isdisjoint(test.ward_id) and train[TARGET].nunique() == 2
        model = fit(train)
        model['fit_scope'] = 'heldout_'+block
        model['training_ward_ids'] = sorted(train.ward_id.unique().tolist())
        write(output/f'model_heldout_{block}.json', model)
        result = test[['event_id', 'ward_id', 'ward_number', 'block', TARGET]].copy()
        result['proxy_score'] = [score(model, row) for row in test.to_dict('records')]
        result['proxy_flag_at_0_5'] = (result.proxy_score >= .5).astype(int)
        parts.append(result)
        folds.append(dict(block=block, train_rows=len(train), train_positives=int(train[TARGET].sum()),
                          test_ward_ids=sorted(test.ward_id.unique().tolist()),
                          metrics=metrics(test[TARGET], result.proxy_score)))
    oof = pd.concat(parts, ignore_index=True)
    oof.to_csv(output/'oof_predictions.csv', index=False)
    write(output/'metrics.json', dict(pooled=metrics(oof[TARGET], oof.proxy_score), folds=folds,
          per_event={str(e): metrics(g[TARGET], g.proxy_score) for e, g in oof.groupby('event_id')}))
    final = fit(data); final['fit_scope'] = 'full_eligible_refit_NOT_OOF'
    write(output/'model_full_refit.json', final)
    write(output/'manifest.json', dict(dataset_sha256=hashlib.sha256((HERE/'dataset.csv').read_bytes()).hexdigest(),
          python=platform.python_version(), sklearn=sklearn.__version__, numpy=np.__version__, pandas=pd.__version__,
          C=1, solver='liblinear', class_weight='balanced', max_iter=2000, seed=42, threshold=.5))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
