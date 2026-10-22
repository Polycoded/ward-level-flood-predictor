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

## Current local readiness (rechecked 2026-10-23)

The earlier zero-byte boundary/metrics inventory is obsolete. The read-only check found:
- wards.geojson: **15 polygons with explicit Zone names**, all 15 ward_number values
  blank; declared CRS EPSG:32644. IDs have no missing/duplicates and polygons pass
  validity checks, but neither names/counts nor valid polygons verify administrative
  boundaries. The explicit zone names signal a mismatch with the requested ward unit.
- features.parquet: **absent**. feature_schema.yaml exists but is not a feature table.
- validation_metrics.json: nonempty, explicitly says **MOCK NUMBERS** in notes. These
  values are unsuitable for accuracy claims; file existence does not mean validation.
- validation_labels.csv: zero bytes; reviewed observations/rainfall remain pending.

Identity readiness, structural scoring readiness and historical readiness are all false.
No reviewed version or crosswalk was supplied to the check. Historical readiness is
deliberately never certified by this tool: reviewed observations and supported rainfall
metadata must go through the existing schema-2.0 evaluation workflow separately.

John: supply actual frozen ward polygons (not zones), legal vintage/source/hash and stable
ID/official-number crosswalk; generate the feature artifact with explicit provenance and
missingness preserved. pipeline/build_features.py currently creates missing numeric
columns as zero and coerces invalid/null values via fillna(0). Numeric zeros in a later
file cannot prove these issues were resolved; require upstream audit/provenance.
api/routes/main.py compute_risk_score still omits duration, and /scenario pre-multiplies
impervious_frac before passing the increase again to the model. Remove that double
adjustment and forward duration. These are verified code findings, not changes made here.

Ronit: visibly distinguish unavailable structural inputs, synthetic demos and historical
evaluation; suppress mock accuracy cards and unsupported physical depth/timing claims.
Do not display zone polygons as reviewed ward boundaries. Adopt the nullable schema-2.0
coverage/status contract with John. Mit: finish reviewed ward observations and a supported
rainfall interval once John's exact boundary/identity version is available.

### Read-only readiness command

```bash
python -m model.input_readiness \
  --boundary data/processed/wards.geojson \
  --features data/processed/features.parquet \
  --metrics data/processed/validation_metrics.json
```

Optional --output must name a new JSON file outside canonical data/processed; existing
paths/inputs cannot be overwritten. Add --boundary-version and --identity-reference only
with real reviewed references, not invented values. --administrative-unit defaults to ward.
CSV uses ward_id plus official_number (ward_number also accepted); Parquet requires a
supported pandas engine. Reports include row positions (zero-based), identity/geometry
defects, missing columns/measurements and ID/official-number mismatches. GeoJSON declared
CRS and feature CRS attributes are reported, not certified. CSV contains no inherent CRS.
Numeric validation reuses the scorer without scoring, dropping or changing records.

Exit 0 means structural scoring checks and identity attestations passed, **not geographic
coverage or accuracy verified**; exit 1 means not ready; exit 2 is a CLI/output error.
Historical readiness remains separate and unassessed, even on exit 0. The reviewed runner
still requires its full provenance configuration. No pipeline extraction/evaluation occurs.

Actual check exited 1. JSON review output was written only to a new temporary path,
not canonical data. Focused tests are artificial. Existing regression test
test_loading_missing_empty_and_round_trip still assumes canonical metrics are empty;
it now fails on the actual mock payload. Do not restore an empty artifact to satisfy it:
follow up by isolating that test from mutable pipeline data.

Command below uses **placeholders**, not runnable evidence paths:

```bash
python -m model.evaluation_runner \
  --features /REPLACE/features.csv --labels /REPLACE/reviewed_labels.csv \
  --metadata /REPLACE/event.json --config /REPLACE/completed_config.json \
  --output /REPLACE/new_review_bundle --top-k 20
```

Never publish synthetic demonstrations as historical accuracy or copy them into canonical metrics.
