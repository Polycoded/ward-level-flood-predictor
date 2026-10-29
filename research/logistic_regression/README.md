# Logistic regression: experimental ward inundation model

A CPU-trained logistic regression prototype, developed on 28 October 2026 after the hackathon. It is separate from the application’s weighted-score engine.

## Results

Geographic out-of-fold evaluation covers 346 ward-event examples from 186 wards, including seven satellite-proxy positives (six distinct wards).

| Measure | Result |
|---|---:|
| Precision | 12.50% |
| Recall | 71.43% |
| F1 | 21.28% |
| Balanced accuracy | 80.55% |
| Average precision | 22.65% |
| Accuracy (secondary) | 89.31% |

Confusion matrix `[[304, 35], [2, 5]]`: five detected proxy positives, two missed, 35 flagged proxy non-detections. Predicting non-detection everywhere would achieve 97.98% accuracy while missing all seven positives.

## Run

From the repository root, create a dedicated environment and install `research/logistic_regression/requirements.txt`. Python 3.9 was used for the recorded experiment.

```bash
python research/logistic_regression/train.py --output /tmp/chennai-logistic-results
python -m unittest discover -s research/logistic_regression -p 'test_*.py'
python research/logistic_regression/predict.py --features research/logistic_regression/dataset.csv --output /tmp/chennai-logistic-scores.csv
```

The training destination must not already exist. Prediction uses the saved full-data refit and Python’s standard library; training needs the listed packages. Scores are uncalibrated proxy scores, not flood probabilities. `results/model_full_refit.json` is a demonstration refit, not a held-out evaluation model. The four `model_heldout_*.json` files reproduce held-out predictions. No pickle loading or native BLAS is needed for prediction.

## Dataset and method

`dataset.csv` freezes the existing experimental dataset, joined by internal ward ID. Seven mapped-inundation candidates are experimental targets of one; 339 protocol non-detections are zero. Fifty-four unknown examples were excluded; source accepted labels remain unknown. Frozen reference: quality .90, coverage .90, four-connected components of at least four native cells, fraction .05, boundary sensitivity 250 m.

Six static predictors: elevation, slope, impervious fraction, distance to water, road density and underpass count. IDs, block, event, label protocol and target metadata are excluded from predictors. Median imputation and standard scaling are fitted inside each training fold. Class-balanced L2 logistic regression uses C=1, liblinear, seed 42 and at most 2,000 iterations; threshold .5, no search.

Each existing geographic quadrant is held out once, keeping both observations of a ward together. NE/NW/SE/SW contain 1/0/0/6 test positives respectively; training outside SW contains only one positive. Missing positive classes make several per-fold metrics undefined; nulls are retained. These already-inspected folds are an exploratory benchmark, not an untouched final test set.

## Limits and source attribution

This target is algorithmically satellite-mapped inundation, not independently observed dry/flooded ground or future flood forecasting. Static predictors cannot model differences in rainfall between events. Seven positives, unbuffered adjacent blocks, overlapping ward geometries, repeated events, uncertain feature provenance and post-event land-cover/OSM vintages severely limit interpretation. Outputs are uncalibrated; no operational threshold, external validation, application integration or notification readiness is established. Terrain masks in the label generator may couple to terrain predictors.

Proxy targets derive from Global Flood Database events 2758 (2005) and 4309 (2015), associated with Tellman et al. (2021), https://doi.org/10.1038/s41586-021-03695-w and https://developers.google.com/earth-engine/datasets/catalog/GLOBAL_FLOOD_DB_MODIS_EVENTS_V1. GFD is CC BY-NC 4.0: https://creativecommons.org/licenses/by-nc/4.0/. This derived proxy dataset must not be treated as unrestricted commercial data. Preserve attribution and indicate changes: native-cell filtering, permanent-water exclusion, ward aggregation, uncertainty screening and feature joins. Independent feature/boundary source permissions remain to be verified; no blanket licensing clearance is claimed.

Archive quality fields do not prove joint cloud/shadow-free observation; exact release/code correspondence remains unresolved. Non-detection is not actual dryness. Raw source rasters and local audit environments are intentionally not bundled. The frozen table supports model reproduction, not independent reconstruction of satellite labels.

Portable coefficients and preprocessing statistics are exported for reproducible scalar inference. The original local NumPy environment emitted numerical warnings on optional full-refit batch inference; scalar calculations were verified against finite reference outputs. This package avoids that inference backend but does not certify a deployment environment.
