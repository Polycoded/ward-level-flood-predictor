# Ward risk index contract

This is an **uncalibrated risk index**, not a flood probability or a hydrodynamic
forecast. Weights, thresholds and rainfall response are hand-chosen prototype
assumptions. Index categories are ordinal display bins, not validated warning levels.

## Inputs and validation

`score_ward(row, rainfall_mm, builtup_increase=0.0, *, duration_hours=3.0)`
accepts a pandas Series (a mapping with `.get()` also works). Supply original,
unadjusted measurements, never values already modified for the same scenario.

| Required feature | Unit | Accepted values | Component |
| --- | --- | --- | --- |
| elevation_mean | metres, consistent DEM vertical datum | finite; negative elevations allowed | clip(1 - elevation/50, 0, 1) |
| slope_mean | degrees | [0, 90] | clip(1 - slope/15, 0, 1) |
| impervious_frac | fraction, not percent | [0, 1] | effective fraction |
| dist_to_water_m | metres | >= 0 | clip(1 - distance/5000, 0, 1) |
| road_density_km_per_sqkm | km/km² | >= 0 | clip(density/20, 0, 1) |
| underpass_count | count | nonnegative integer, including integer-valued floats | 1 if positive, otherwise 0 |

Rainfall is **total accumulation in mm over duration_hours**, not mm/h:
`rainfall_mm` is finite in [0, 500], `duration_hours` in [1, 24], and
`builtup_increase` is a finite relative percent in [0, 100]. Ranges match the
existing API scenario limits, not a claim of physical validity within those ranges.
Booleans and numeric strings are rejected. Missing keys, None, pandas NA, NaN,
infinities and out-of-range inputs raise field-specific `ValueError`. No scoring
feature is optional and none is replaced by zero. Batch scoring fails rather than
returning partial/silently imputed results. Zero rainfall still requires valid features.

Other columns (including water_frac, vegetation_frac and flood_prone_index) are
unused and not validated or explained. Unknown unused columns do not block scoring.
Zero underpasses is valid only when established by the source, not when coverage
is unknown. The model cannot detect upstream imputation disguised as real data.

## Formula

Let C(x) = min(1, max(0, x)). With original impervious fraction I and relative
built-up increase b, effective impervious fraction is `I_eff = min(I*(1+b/100), 1)`.
This adjustment occurs once per scoring call, without mutating the input.
For example 0.55 with +30% becomes 0.715, not 0.85 and not 0.9295.

```
B = 0.25*C(1-elevation/50) + 0.15*C(1-slope/15)
  + 0.25*I_eff + 0.15*C(1-distance/5000)
  + 0.10*C(road_density/20) + 0.10*(underpass_count > 0)
D = min(1.5, max(0.5, sqrt(3/duration_hours)))
R = min((rainfall_mm/200)*D, 1.5)
index = min(B*R, 1)
```

The duration heuristic makes the same accumulation more influential when concentrated
into fewer hours. The square root dampens intensity sensitivity relative to direct
inverse-duration scaling; bounds limit this unvalidated adjustment to 0.5–1.5x.
Three hours preserves the previous accumulation formula exactly. The final rainfall
factor cap prevents unlimited amplification. These constants are design choices,
not fitted drainage thresholds. Longer duration does not erase the accumulation
term; this simple rule does not represent antecedent saturation or within-storm peaks.
Scores are nondecreasing with accumulation and built-up increase, and nonincreasing
with duration at fixed accumulation, with plateaus due to caps/clipping.

Categories: very_low [0, .2), low [.2, .35), moderate [.35, .55), high [.55, .75),
very_high [.75, 1]. `classify_risk` rejects invalid indices instead of defaulting low.

## Outputs and explanation compatibility

`score_ward` still returns `(float index, RiskLevel, DepthBand, int peak_window, list[str] reasons)`.
Enum values and positional argument order are unchanged. Duration is keyword-only.
`score_wards` accepts the same scenario arguments and returns descending scores with
ward_id, ward_number, ward_name, risk_score, risk_level, depth_band,
peak_window_hours and reasons. Batch rows also require identity columns; ward_id
must be convertible to int. Empty batches return these columns and validate scenario
arguments, but have no feature rows to validate.

Scoring passes its exact validated, scenario-adjusted feature dictionary to the
single explanation implementation in `model/reasons.py`. Explanations describe
component directions and rainfall inputs, not drainage capacity or physical outcomes.
Vegetation explanations were removed because vegetation is not a scoring component;
the old standalone five-reason truncation was removed to retain rainfall/disclaimer text.

Existing `model.reasons.generate_reasons(row, rain, score)` and
`model.risk_engine.generate_reasons(row, rain, score, level, depth)` remain callable.
Both accept keyword-only `builtup_increase` and `duration_hours`. Pass the original
features, matching scenario arguments and matching computed score. The supplied score
is range-validated, not recomputed; the legacy level/depth arguments are ignored.
Prefer the reasons returned by `score_ward` to prevent caller-side mismatches.

```python
result = score_ward(original_row, 150, 30, duration_hours=6)
batch = score_wards(original_features, 150, 30, duration_hours=6)
```

## Legacy depth and timing: unsupported

For compatibility only, depth categories still use `proxy_m = index * 1.5 * R`:
none [0, .01), 0–0.15m [.01, .15), 0.15–0.5m [.15, .5),
0.5–1.0m [.5, 1), 1.0m+ [1, infinity). These labels are **not predicted water depths**.
`peak_window_hours = max(1, int(3*(1+index)))` yields 3–6 and is **not a predicted
peak time**. Duration changes R and therefore these proxies, not their evidential status.
No physical or observational calibration supports either mapping. Do not use these
fields for safety decisions, public depth claims or peak-time alerts.

`model/depth_band.py` separately uses `index * 1.5 * min(rain/100, 2)` metres;
it is inconsistent with this mapping and is not called by score_ward. It is unchanged.
Proposed future coordinated contract: nullable depth/timing with explicit unavailable
status and method/version metadata, only populated after suitable validation. No
return types, API schemas or consumer types were changed in this task.

## Assumptions and integration handoffs

- DEM, slope, distance and density must use consistent units and defensible source
  coverage. Ward means lose local detail; proximity does not establish backflow.
  No tides, sewer/drain capacity, rainfall time series or hydraulic routing are modelled.
- API integration inspected 2026-10-23: compute_risk_score now accepts and forwards
  duration_hours. /scenario passes original feature rows, the built-up percentage once,
  and explicit requested duration; the previous pre-adjustment is gone. /risk now
  explicitly forwards input_data.duration_hours; omitted duration retains the schema's
  3-hour default. /alerts still passes only row/rainfall and AlertRequest has no duration
  field. These routes need separate contract/call-site attention; not every route is fixed.
  RainfallInput describes total accumulation over duration_hours. The model cannot detect
  externally pre-adjusted fractions; all callers must continue supplying original values.
- API owner: handle ValueError as an explicit input/data-quality error. Distinguish
  invalid requests from missing source measurements; never substitute zero.
  Describe risk_score as an uncalibrated index and version the changed model behavior.
- Pipeline owner: build_features.validate_features currently creates missing columns
  as zero and fills coerced nulls with zero. Preserve unknowns and provenance, resolve
  coverage gaps, and regenerate features before trusting any model output.
- Frontend/integration owners: suppress physical depth/peak claims and use the returned
  reasons rather than independent explanation logic. Agree deprecation before changing
  nullable types. Feature displays should distinguish original vs effective scenario values.
- Validation API still reads JSON directly into the legacy numeric ValidationMetrics
  response. Current validation_metrics.json is nonempty and explicitly marked MOCK NUMBERS,
  not evidence of accuracy; the old empty-file JSONDecodeError is not the current artifact
  condition. Migrate unavailable/nullable schema-2.0 handling and suppress mock claims.
  The isolated canonical-file regression dependency has been fixed in tests; no current
  failure is asserted here, and API/runtime tests were not rerun in this documentation task.

Current boundary inputs contain 200 individually valid polygons and a 200-row matching
internal-ID/official-number crosswalk (ID 1 → official ward 168), not the old 15-zone layer.
Individual validity does not certify coverage or a nonoverlapping partition. The pending
readiness diagnostic counts all positive-area overlap pairs (448 in this snapshot);
[chennai_boundary_review.md](chennai_boundary_review.md) counts 291 pairs over 1 m².
Neither predicate is a geographic acceptance standard. Source/vintage/topology review,
missing features.parquet, upstream zero-fill provenance and reviewed historical observations/
rainfall remain blockers. See [chennai_handoff.md](chennai_handoff.md) for current requests.

See [validation.md](validation.md) for evidence requirements. Unit tests demonstrate
mechanical consistency only; they do not validate flood accuracy.

Geographic input production contracts, missing-data policies and pipeline integration
steps are documented in [geographic_modules.md](geographic_modules.md). In particular,
slope_mean must be aggregated from degree slopes on a verified metre DEM grid, and
dist_to_water_m is a projected ward-centroid-to-nearest-water-geometry summary.
