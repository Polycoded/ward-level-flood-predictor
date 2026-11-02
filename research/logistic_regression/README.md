# Logistic regression: experimental ward inundation model

A CPU-trained susceptibility prototype, separate from the application's weighted-score
engine. It uses a frozen ward-event table derived from Global Flood Database satellite
inundation proxies for 2005 (event 2758) and 2015 (event 4309).

**This is not verified flood susceptibility and not a forecast.** A detection is a
satellite-mapped inundation proxy. A non-detection is **not** confirmed dryness. The
application remains on its uncalibrated weighted index.

## Prior recorded results (2026-10-28)

| Measure | Result |
|---|---:|
| Precision at 0.5 | 12.50% |
| Recall at 0.5 | 71.43% |
| F1 | 21.28% |
| Balanced accuracy | 80.55% |
| Average precision | 22.65% |
| Accuracy (secondary) | 89.31% |

Confusion matrix `[[304, 35], [2, 5]]`: five detected proxy positives, two missed,
35 flagged proxy non-detections. Predicting non-detection everywhere would achieve
97.98% accuracy while missing all seven positives. This table is retained for
reproduction; it mixes fold-specific score scales and two positive-free folds.

### Bounded sensitivity hypotheses (2026-10-28)

Two post-baseline hypotheses were tested on the same 346-row/186-ward dataset, the
same reused geographic folds and the fixed 0.5 threshold. Neither improves pooled
precision or F1:

| Variant | Confusion | Precision | Recall | F1 | BA | AP |
|---|---:|---:|---:|---:|---:|---:|
| baseline, C=1 raw | `[[304,35],[2,5]]` | .125 | .714 | .213 | .806 | .227 |
| A: C=0.1 raw | `[[286,53],[1,6]]` | .102 | .857 | .182 | .850 | .250 |
| B: C=1 log1p on water distance, road density and underpass count | `[[304,35],[6,1]]` | .028 | .143 | .047 | .520 | .093 |

A trades 18 additional false positives for one extra true positive (a recall/AP
trade-off); B collapses the pooled useful measures. These reused-fold results are
exploratory, not independent validation, and are superseded by the spatially blocked
evaluation below.

## Methodology audit (2026-10-30)

### Code paths

- Fold construction and leakage checks: `spatial_common.make_folds`,
  `make_folds` assertions, `fold_assignments`.
- Fold-local preprocessing and models: `spatial_common.make_logistic_pipeline`,
  `fit_logistic`, `tune_logistic_c`.
- Metrics: `spatial_common.precision_recall_metrics`, `macro_metrics`,
  `add_rank_normalized_score`, `block_bootstrap`.
- Ward-event runner: `evaluate_spatial.run_evaluation`.
- Ward-level runner: `evaluate_ward_level.run`, `aggregate_wards`,
  `graded_metrics`, `block_bootstrap_graded`.
- Overlap audit: `audit_overlap_impact.audit`, using
  `audit_geometry.build_overlap_table`.

### Verified properties

1. **Every ward is held out as a complete group.** A ward maps to one quadrant and one
   zone; all its event rows are on the same side of every split. Tests assert no ward
   appears in both training and test and every ward is held out exactly once.
2. **Adjacent wards can cross the train/test boundary.** No spatial buffer is enforced.
   The primary policy is leave-one-zone-out and the sensitivity is leave-one-quadrant-out.
   The overlap audit found **104 of 291 substantial ward-pair overlaps split across zone
   folds** and 60 split across quadrant folds. The "geographically unseen" claim is
   therefore weaker than the fold names imply. This is documented, not corrected by
   silently dropping wards.
3. **Preprocessing is training-only.** Imputation, scaling and logistic fitting are
   inside each training fold; the inner C search is ward-grouped and uses training rows
   only. The tests include a sentinel-value leakage check.
4. **Fold-local percentile normalization uses held-out rows only.** It is calculated
   from out-of-fold scores within each fold. It cannot repair the fact that separate
   fold models are not on a common scale.
5. **Pooled rank AP is not a single global ranking.** Mapping each fold's held-out
   scores to within-fold percentiles makes cross-fold pooling possible, but it creates
   ties at each fold maximum and is prevalence-weighted. Raw pooled scores are worse:
   they are not comparable across fold-specific models. Pooled rank AP is therefore a
   diagnostic; **per-fold metrics and their macro averages are primary**.
6. **Macro AP can be 1.000 for the wrong reason.** Only three zone folds contain a
   positive (II: 1/6 wards, XIV: 2/10, XV: 3/7). The logistic model ranks every one of
   those positives above every negative in the fold, so each defined fold has AP 1.0.
   Twelve folds have no positive and are undefined, not zero. Small folds plus seven
   positives make this fragile, not a stable accuracy estimate.
7. **Bootstrap intervals have two different estimands.**
   - `bootstrap_all_blocks` resamples all 15 zones (or 4 quadrants) with replacement and
     conditions on the resample containing a positive. No-positive resamples are
     undefined; the reported valid-replicate count makes this explicit.
   - `bootstrap_positive_blocks` resamples only positive-containing blocks. It is closer
     to the per-fold AP values and is near 1.0 for logistic regression, but it cannot
     estimate performance on the 12 positive-free zones.
   Neither interval is a confidence interval for deployment accuracy.
8. **Fold prevalence differs sharply.** Pooled prevalence is 2.02% (7/346), but zone
   prevalence ranges 0–44.4% and quadrant prevalence 0–8.0%. Pooled metrics are
   prevalence-weighted; macro metrics are unweighted over defined folds. Both are
   reported.

### Metric correction: tie-aware precision@k

The original top-k calculation broke ties by ward ID. Pooled percentile ranks create
ties at every fold maximum, making that arbitrary. `precision_recall_metrics` now
computes the expected true positives at the cutoff from the positive fraction of the
tied score group. It records `ties_at_cutoff`, `tie_positive_fraction`,
`expected_true_positives` and `tie_aware`. AP remains the standard tie-aware
`average_precision_score`; AP and trapezoidal PR-AUC are reported separately.

Independent metric tests use hand-calculated values. All 34 research tests pass,
including the tie case; 674 project tests pass.

## Ward-event evaluation

Primary: leave-one-zone-out (15 zones). Sensitivity: leave-one-quadrant-out (4 blocks).
Scores are rankings, not calibrated probabilities. Pooled values use within-fold
percentile ranks; raw pooled values are retained only as diagnostics.

### Zone folds (primary)

| Model | Macro AP (defined) | Pooled rank AP | P@20 | R@20 | AP CI, all blocks | AP CI, positive blocks |
|---|---:|---:|---:|---:|---|---|
| random (analytic) | 0.223 (3/15) | 0.020 | 0.020 | 0.058 | n/a | n/a |
| elevation only | 0.792 (3/15) | 0.146 | 0.100 | 0.286 | 0.024–0.484 | 0.375–1.000 |
| existing weighted index | 0.244 (3/15) | 0.020 | 0.000 | 0.000 | 0.004–0.058 | 0.106–0.464 |
| logistic, current (C=1) | 1.000 (3/15) | 0.203 | 0.100 | 0.286 | 0.053–0.600 | 0.843–1.000 |
| logistic, L2 tuned | 1.000 (3/15) | 0.229 | 0.100 | 0.286 | 0.051–0.669 | 0.843–1.000 |
| ablation: no terrain | 1.000 (3/15) | 0.270 | 0.150 | 0.429 | n/a | n/a |
| ablation: no water | 1.000 (3/15) | 0.229 | 0.100 | 0.286 | n/a | n/a |
| ablation: no terrain/water | 0.983 (3/15) | 0.373 | 0.150 | 0.429 | n/a | n/a |

Per-fold AP where positives exist: logistic current/tuned = 1.000 in II, XIV, XV;
elevation = 1.000 / 0.375 / 1.000; weighted index = 0.143 / 0.125 / 0.464.

### Quadrant folds (sensitivity)

| Model | Macro AP (defined) | Pooled rank AP | P@20 | R@20 | AP CI, all blocks | AP CI, positive blocks |
|---|---:|---:|---:|---:|---|---|
| random (analytic) | 0.043 (2/4) | 0.020 | 0.020 | 0.058 | n/a | n/a |
| elevation only | 0.724 (2/4) | 0.314 | 0.250 | 0.714 | 0.200–0.716 | 0.500–0.948 |
| existing weighted index | 0.037 (2/4) | 0.015 | 0.000 | 0.000 | 0.003–0.048 | 0.007–0.066 |
| logistic, current | 0.707 (2/4) | 0.163 | 0.100 | 0.286 | 0.115–0.750 | 0.325–1.000 |
| logistic, L2 tuned | 0.707 (2/4) | 0.163 | 0.100 | 0.286 | 0.115–0.750 | 0.325–1.000 |

In SW, which holds six of seven positives, elevation AP is 0.948 versus 0.413 for
logistic regression. In NE (one positive), logistic AP is 1.000 versus 0.500 for
elevation. There is no demonstrated superiority. Tuned C ranges from 0.01 to 10 and
falls back to C=1 in SW.

## Ward-level evaluation

One row per ward. Target A (`any_detection`) is supported: 186 wards, 6 positives,
3.23% prevalence; 160 wards have both events (complete) and 26 have one (partial);
14 boundary wards are absent because both events are unknown.

**Target B (`detection_frequency`) is not separable on this dataset.** Every detection
occurs in a ward with only one available event, except ward 16 where both events are
positive. Frequency is therefore 0 or 1 for every ward and is exactly identical to
target A. The complete-coverage population contains only **one** positive (ward 16),
so frequency-based ranking metrics there are not estimable. This is a data limitation,
not a label that was invented or tuned. The outputs mark target B as `binary_only`
(all wards) and `unsupported` (complete coverage).

### Target A, leave-one-zone-out (186 wards)

| Model | Macro AP (defined) | Pooled rank AP | P@20 | R@20 | AP CI, all blocks | AP CI, positive blocks |
|---|---:|---:|---:|---:|---|---|
| random | 0.622 (3/15) | 0.086 | 0.100 | 0.333 | 0.006–0.233 | 0.167–0.867 |
| elevation only | 0.806 (3/15) | 0.105 | 0.100 | 0.333 | 0.027–0.271 | 0.417–1.000 |
| existing weighted index | 0.306 (3/15) | 0.031 | 0.000 | 0.000 | 0.009–0.081 | 0.175–0.467 |
| logistic, current | 1.000 (3/15) | 0.165 | 0.150 | 0.500 | 0.056–0.357 | 0.943–1.000 |
| logistic, L2 tuned | 1.000 (3/15) | 0.165 | 0.150 | 0.500 | 0.056–0.357 | 0.943–1.000 |
| ablation: no terrain | 1.000 (3/15) | 0.165 | 0.150 | 0.500 | n/a | n/a |
| ablation: no water | 1.000 (3/15) | 0.165 | 0.150 | 0.500 | n/a | n/a |
| ablation: no terrain/water | 0.972 (3/15) | 0.160 | 0.150 | 0.500 | n/a | n/a |

Per-fold logistic AP: zone II 1.000 (1/6), XIV 1.000 (2/10), XV 1.000 (3/7). Quadrant
sensitivity: NE 1.000 (1/76), SW 0.498 (5/41); elevation AP is 0.315 with P@20 0.200
versus logistic 0.183 with P@20 0.150. Again, elevation is competitive or better in the
largest positive fold.

The complete-coverage population has one positive; its target-A metrics are retained
as descriptive audit output only and are not used for model comparison.

### Target-definition comparison

| Definition | Unit weight | Observed values | Positives | Supported |
|---|---|---|---:|---|
| A: any detection | ward | 0/1 | 6 of 186 | yes |
| B: detection frequency | event | 0/1 only | 6 of 186; 1 of 160 complete | no (identical to A; complete set underpowered) |

A ignores recurrence and treats a partial-coverage negative as non-detection. B would
preserve recurrence and coverage but cannot be estimated here. Neither is verified
susceptibility.

## Elevation and leakage audit

Univariate associations are diagnostic, not causal. Ward-event Pearson/Spearman:
elevation −0.248/−0.222; slope −0.205/−0.212; impervious −0.330/−0.223;
water distance −0.115/−0.123; road density −0.261/−0.208; underpass −0.014/+0.035.
Ward-level target A: elevation −0.289/−0.271; impervious −0.388/−0.275; road
−0.314/−0.256; slope −0.251/−0.263; water −0.128/−0.134; underpass −0.032/+0.021.

Zone-fold coefficient stability for the current logistic model (15 folds):

| Feature | Mean | Std | Sign consistency |
|---|---:|---:|---|
| elevation | −0.431 | 0.172 | 15/15 negative |
| slope | −1.619 | 0.263 | 15/15 negative |
| impervious | −1.512 | 0.128 | 15/15 negative |
| water distance | −1.276 | 0.137 | 15/15 negative |
| road density | +0.298 | 0.146 | 14 positive / 1 negative |
| underpass | −0.299 | 0.111 | 14 negative / 1 positive |

Impervious fraction and underpass count have the **opposite sign** to the physical
expectation in the full refit. They must not be interpreted as physical relationships.

Ablations with identical folds: removing terrain changes ward-event zone pooled rank
AP from 0.203 to 0.270 (quadrant 0.163 to 0.222); removing terrain and water gives 0.373
(zone) and 0.223 (quadrant). Ward-level target A is almost unchanged (0.165 to 0.165;
no terrain/water 0.160). Terrain removal does **not** prove the model is leakage-free,
and the strong elevation baseline is consistent with terrain-label coupling. It also
does not prove terrain is the only signal.

## Spatial overlap audit

- 200 wards, EPSG:32644, 0 invalid/empty/duplicate geometries.
- 448 positive-area overlap pairs; **291 > 1 m²**, 157 ≤ 1 m² numerical artifacts.
- Sum of pairwise overlaps 107,217.8 m²; area sum − union = 107,205.5 m².
- **104 of 291 substantial pairs split across zone folds; 60 split across quadrant
  folds.** Adjacent/overlapping wards are not fully separated by the current folds.
- 9 **substantial** overlap pairs involve a positive ward; 3 have both wards positive;
  4 split across zone folds and 6 split across quadrant folds. Five further positive
  pairs are ≤1 m² numerical artifacts.
- Wards 27/28 (official 190/191): 6,993.3 m² overlap, 0.23%/0.17% of their areas, both
  positive, same zone and quadrant, 0 underpasses in the overlap.
- Wards 15/28 (official 198/191): 1,200.9 m², split across zone folds (XV/XIV), same
  quadrant. Wards 15/27 (198/190) are also both positive and split across zone folds.
  These are the clearest positive-pair train/test geography concerns.
- 82 overlap pairs contain underpasses; **83 of 706 underpasses** fall inside an overlap
  and can be counted for both wards. DEM/LULC/road zonal statistics were not recomputed.
- No area was transferred between wards. The overlap remains unresolved; a sensitivity
  excluding wards 27 and 28 preserves the conclusions but is not a correction.

## What this establishes and what it does not

It establishes a reproducible spatial-validation harness, fold-local preprocessing,
tie-aware metrics, ward-level outputs, label/geometry/overlap audits and comparable
baselines. On this proxy target it shows:

- the existing weighted index has no demonstrated ranking skill (pooled rank AP 0.020
  ward-event zone; 0.015 quadrant; ward-level 0.031);
- a simple elevation ranking is competitive with, and in the largest positive folds
  better than, the six-feature logistic model;
- no stable tuning or complex-model gain is demonstrated;
- target B is not separable from target A in this dataset;
- positive wards overlap, and 104 substantial overlap pairs cross zone folds.

It does **not** establish real flood occurrence, future forecasting, calibrated
probabilities, operational thresholds, causal feature effects, citywide accuracy,
leakage-free features, or transferability to other events or cities.

## Remaining limitations, prioritized

1. Seven proxy positives from two GFD events; zeros are non-detections, not dry wards.
2. Only 3/15 zones and 2/4 quadrants contain positives; estimates are fragile.
3. Target B is unsupported: frequency is 0/1 and complete coverage has one positive.
4. No spatial buffer is enforced; 104 substantial overlap pairs cross zone folds.
5. Positive wards overlap (especially 27/28); zonal statistics were not recomputed.
6. Labels are 2005/2015 proxies; features are 2021/current.
7. Terrain-label coupling cannot be separated from a real terrain signal.
8. Scores are rankings, not calibrated probabilities; no threshold was selected.
9. OSM/LULC completeness and vintage affect several predictors.
10. No external validation; block bootstrap over 4/15 blocks is coarse and conditional.

## Commands and outputs

Run from the repository root in an environment with the research requirements
(`matplotlib`, `geopandas`):

```bash
python research/logistic_regression/evaluate_spatial.py \
  --output research/logistic_regression/results/spatial_eval --bootstrap 1000

python research/logistic_regression/evaluate_spatial.py \
  --output research/logistic_regression/results/spatial_eval_sensitivity_exclude_27_28 \
  --bootstrap 1000 --exclude-wards 27 28

python research/logistic_regression/evaluate_ward_level.py \
  --output research/logistic_regression/results/ward_level_eval --bootstrap 1000

python research/logistic_regression/audit_overlap_impact.py \
  --output research/logistic_regression/results/overlap_impact

python research/logistic_regression/audit_geometry.py \
  --output research/logistic_regression/results/geometry_audit

python -m unittest discover -s research/logistic_regression -p 'test_*.py'
```

Spatial outputs: `fold_assignments*.csv`, `oof_predictions.csv`, `metrics.json`,
`metrics_per_fold.csv`, `precision_recall_{zone,quadrant}.png`, `geographic_oof.png`,
`geometry_audit.json`, `geometry_overlaps.csv`, `label_audit.json`, `dataset_audit.json`,
`run_manifest.json`.

Ward-level outputs: `ward_level_predictions.csv` (one row per ward),
`ward_level_oof_long.csv`, `ward_level_metrics.json`, `ward_level_metrics_per_fold.csv`,
`ward_level_fold_assignments.csv`, `ward_level_label_audit.json`,
`ward_level_input.csv`, `ward_level_geographic_oof.png`, `run_manifest.json`.

Overlap outputs: `overlap_impact.json`, `overlap_impact_pairs.csv`.

Fold assignments, OOF predictions and metrics are reproducible with the fixed seed. A
second spatial run produced byte-identical `oof_predictions.csv`, `metrics.json` and
`fold_assignments.csv`.

## Dataset and method

`dataset.csv` freezes the existing experimental dataset, joined by internal ward ID.
Seven mapped-inundation candidates are experimental targets of one; 339 protocol
non-detections are zero. Fifty-four unknown examples were excluded; source accepted
labels remain unknown. Frozen reference: quality .90, coverage .90, four-connected
components of at least four native cells, fraction .05, boundary sensitivity 250 m.

Six static predictors: elevation, slope, impervious fraction, distance to water, road
density and underpass count. IDs, block, event, label protocol and target metadata are
excluded from predictors. Median imputation and standard scaling are fitted inside each
training fold. Class-balanced L2 logistic regression uses C=1, liblinear, seed 42 and at
most 2,000 iterations; threshold .5, no search. The tuned variant searches C inside
training only.

Each existing geographic quadrant is held out once, keeping both observations of a ward
together. NE/NW/SE/SW contain 1/0/0/6 test positives respectively. Zone folds are the
15 administrative zones; 12 have no test positive. These already-inspected folds are an
exploratory benchmark, not an untouched final test set.

## Limits and source attribution

This target is algorithmically satellite-mapped inundation, not independently observed
dry/flooded ground or future flood forecasting. Static predictors cannot model
differences in rainfall between events. Seven positives, unbuffered adjacent blocks,
overlapping ward geometries, repeated events, uncertain feature provenance and
post-event land-cover/OSM vintages severely limit interpretation. Outputs are
uncalibrated; no operational threshold, external validation, application integration or
notification readiness is established. Terrain masks in the label generator may couple
to terrain predictors.

Proxy targets derive from Global Flood Database events 2758 (2005) and 4309 (2015),
associated with Tellman et al. (2021), https://doi.org/10.1038/s41586-021-03695-w and
https://developers.google.com/earth-engine/datasets/catalog/GLOBAL_FLOOD_DB_MODIS_EVENTS_V1.
GFD is CC BY-NC 4.0: https://creativecommons.org/licenses/by-nc/4.0/. This derived proxy
dataset must not be treated as unrestricted commercial data. Preserve attribution and
indicate changes: native-cell filtering, permanent-water exclusion, ward aggregation,
uncertainty screening and feature joins. Independent feature/boundary source permissions
remain to be verified; no blanket licensing clearance is claimed.

Archive quality fields do not prove joint cloud/shadow-free observation; exact
release/code correspondence remains unresolved. Non-detection is not actual dryness.
Raw source rasters and local audit environments are intentionally not bundled. The
frozen table supports model reproduction, not independent reconstruction of satellite
labels.

Portable coefficients and preprocessing statistics are exported for reproducible scalar
inference. The original local NumPy environment emitted numerical warnings on optional
full-refit batch inference; scalar calculations were verified against finite reference
outputs. This package avoids that inference backend but does not certify a deployment
environment.

## Run

From the repository root, create a dedicated environment and install
`research/logistic_regression/requirements.txt`. Python 3.9 was used for the original
recorded experiment; the spatial and ward-level audits were run on Python 3.11 with
scikit-learn 1.6.1 (versions are recorded in `run_manifest.json`).

```bash
python research/logistic_regression/train.py --output /tmp/chennai-logistic-results
python -m unittest discover -s research/logistic_regression -p 'test_*.py'
python research/logistic_regression/predict.py --features research/logistic_regression/dataset.csv --output /tmp/chennai-logistic-scores.csv
```

The training destination must not already exist. Prediction uses the saved full-data
refit and Python's standard library; training needs the listed packages. Scores are
uncalibrated proxy scores, not flood probabilities. `results/model_full_refit.json` is a
demonstration refit, not a held-out evaluation model. The four `model_heldout_*.json`
files reproduce held-out predictions. No pickle loading or native BLAS is needed for
prediction.
