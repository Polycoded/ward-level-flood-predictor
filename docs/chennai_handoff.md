# Chennai integration handoff

Original roles remain: John pipeline/API/deployment, Mit geography/model/evidence,
Ronit frontend. No pipeline/API/UI implementation changes in this task.

## Six original measurements

| Feature | Unit | Accepted values |
|---|---|---|
| elevation_mean | m | finite; negative elevations allowed |
| slope_mean | degree | 0–90 |
| impervious_frac | fraction | 0–1 |
| dist_to_water_m | m | finite >=0 |
| road_density_km_per_sqkm | km/km2 | finite >=0 |
| underpass_count | count | nonnegative integer |

No missing measurements are replaced with zeros. Use original unadjusted values.
The authoritative formula/normalizers are in [model_logic.md](model_logic.md).

```python
from model.risk_engine import score_ward
index, level, _, _, reasons = score_ward(original_row, 100, 0, duration_hours=6)
# Numeric rain/duration above are illustrative only, NOT historical Chennai evidence.
```

John: forward actual accumulation/duration through API wrappers. Remove scenario route's
impervious pre-multiplication: pass original features plus the percentage exactly once.
Historical runner always uses zero increase. Suppress unsupported depth/peak-time claims;
legacy tuple proxies are not physical predictions. See [geographic integration](geographic_modules.md)
and [schema-2.0 evaluation/API/UI migration](validation.md).

Runner requires CSV, not Parquet: explicitly export a reviewed feature artifact to CSV
with ward_id, official_number (text), event_id, boundary_version and the six columns.
Preserve identity text/leading zeros; export without a DataFrame index. Labels must already
use reviewed internal IDs. Do not assume internal ward_id equals official ward_number.
Config requires provenance for every feature and an explicit run purpose; see
[runner instructions](evaluation_runner.md). All declarations remain caller attestations.

John must deliver frozen boundary polygons/version/hash/CRS, stable-ID/official-number
crosswalk, original feature artifact with source/version/units/coverage/processing provenance,
and frozen model revision/scenario metadata. Mit still needs a supported rainfall interval
and reviewed ward-aligned observations (including explicit negatives, not news omissions).

Local inventory checked in this task: data/processed/wards.geojson,
validation_labels.csv and validation_metrics.json are zero bytes, not usable datasets.
No feature artifact is present in data/processed. Chennai research candidates remain pending;
no real historical evaluation is ready.

Command below uses **placeholders**, not runnable evidence paths:

```bash
python -m model.evaluation_runner \
  --features /REPLACE/features.csv --labels /REPLACE/reviewed_labels.csv \
  --metadata /REPLACE/event.json --config /REPLACE/completed_config.json \
  --output /REPLACE/new_review_bundle --top-k 20
```

Never publish synthetic demonstrations as historical accuracy or copy them into canonical metrics.
