# Reusable baseline scoring and evaluation runner

Chennai is the confirmed target; see [chennai_handoff.md](chennai_handoff.md).
Configuration now requires run_purpose: synthetic_demonstration or historical_evaluation.
Every feature_provenance entry requires source_ref, dataset_version_or_date, units,
evidence_type (observed/derived/synthetic/unknown), coverage_status (complete/partial/unknown),
coverage_notes and processing_ref. Exact unit tokens are in the configuration template.
Blank references or mismatched units fail before scoring. Historical runs reject synthetic
or unknown origins. These declarations are caller attestations, not verified provenance.
Both JSON outputs explicitly disclose purpose, synthetic-demo limitations and features
without complete attested coverage; label coverage metrics do not measure feature coverage.
Finite numbers/zeros do not prove coverage. Config declarations remain hashed and exported.

No real-data run has been completed. Chennai remains the target; no Kerala
features, labels, hydrological assumptions or coefficients were added. The Chennai
research pack under data/evidence/chennai_2023 remains location-specific and unchanged.

## Command

From the repository root in the project's Python environment:

```bash
python -m model.evaluation_runner \
  --features /absolute/path/features.csv \
  --labels /absolute/path/labels.csv \
  --metadata /absolute/path/event.json \
  --config /absolute/path/config.json \
  --output /absolute/path/new-review-bundle \
  --top-k 20
```

All five paths are required. From another cwd, install/import the repository or set
PYTHONPATH to its root. Relative arguments are resolved against invocation cwd. Output
must be a **new directory**, not an input/ancestor or anything under canonical
data/processed. Existing bundles are not replaced. Validation completes before any
output is created; a private sibling staging directory holds the complete bundle
before publication. This is a single-writer review tool, not a concurrent publication
service. Strict JSON reports use the evaluator's atomic file writer. Failure exits 2
with a diagnostic. No canonical metrics are published by the runner.

Outputs:
- predictions.csv: only ward_id, risk_score, event_id, boundary_version, sorted by
  descending score then numeric ID; compatible with model.validation.
- evaluation.json: evaluator schema 2.0 plus runner_manifest. Coverage, exclusions,
  null metrics/reasons and warnings retain the evaluator's meaning.
- manifest.json: config, input byte SHA-256 hashes/paths, prediction byte hash, source
  hashes (runner, risk engine, reasons, evaluator), Python/pandas/NumPy/pyproj versions,
  explicit scenario, invocation arguments/cwd/output/k and unused feature columns.

No depth_band, peak_window_hours, physical depth/timing estimates or reasons containing
those proxy descriptions are exported. The scorer's compatibility tuple is unchanged;
the runner extracts only the index. It does not interpret risk categories as top-k labels.

## Configuration and identity

Copy data/fixtures/evaluation_config_TEMPLATE.json, complete nulls and set is_template
false or remove it. Required text fields: location, administrative_unit_type,
boundary_version, model_id, model_version, projected_crs, projection_review_ref and
identity_reference. model_id must be **six_feature_uncalibrated_baseline**. model_version
is the caller's frozen revision identifier, recorded alongside actual source hashes;
it is not automatically authenticated. Unknown config keys (including weights) fail.
Historical baseline builtup_increase must be zero; event metadata must not contradict it.

Identity modes:
- explicit_mapping: id_mapping is an inline object from canonical internal ID strings
  to official administrative-number strings. It must cover exactly the feature IDs.
- same_as_official: explicitly attest equality with identity_reference; no mapping object
  may be populated. Every row's official_number must equal its canonical internal ID.

Both modes require feature official_number, preserve its text (including leading zeros),
and reject duplicate official numbers/mismatches. identity_reference should identify
the reviewed boundary crosswalk/document, not a neighbourhood name. This runner checks
internal consistency, **not** the legal correctness of that assertion or polygon membership.
Labels must already use the reviewed internal ward_id namespace; no name-based conversion
or implicit official-number lookup occurs. The retained field name ward_id is an
evaluator compatibility key for any administrative unit, not a requirement to use wards.

projected_crs has **no city default**. It must describe two projected metre axes and
projection_review_ref must document local review. Structural CRS validation does not
verify area of use, distortion, coordinate truth, terrain accuracy or catchment suitability.
The runner processes no geometries/rasters: it consumes precomputed aggregate features.
Use the existing geographic functions with explicit metric_crs upstream when appropriate;
their names and implementations have not been changed.

## Shared feature and event contracts

The single reusable specification for the six feature names, units, ranges, missing-data
rules and formula is **[model_logic.md — Inputs and validation](model_logic.md#inputs-and-validation)**.
The runner's name list selects those columns, but it delegates range/count/finite
validation to risk_engine.effective_inputs; it defines no new normalizers or coefficients.
The historical scenario always forwards metadata.rainfall_mm and duration_hours explicitly
to score_ward with builtup_increase=0. It never pre-adjusts original feature measurements.

Feature CSV needs the six measurements plus ward_id, official_number, event_id and
boundary_version. CSV cells are read as text with no NA guessing; the six measurements
are explicitly converted to numbers and scorer-validated. No invalid row is dropped or
filled. Measurement/mapping failures include CSV row number and ID; structural/duplicate
identity or event errors stop with an explicit diagnostic. No scoring occurs until all
feature records and label evidence pass preflight. Empty features fail as pending, not a
successful real-data run. Header-only labels are permitted and yield unavailable evaluation.

Other columns are allowed and listed in unused_feature_columns: they receive **no weight**.
Optional event metadata columns are still consistency-checked using the evaluator contract
(numeric rainfall/duration fields parsed explicitly). Additional measurements, text metrics,
geometry blobs or newly named indices do not silently join the model. Their meaning must
be reviewed before a future model revision; ignored columns are hashed as raw file bytes.

Event metadata/label schemas remain those in [validation.md](validation.md). This runner
additionally requires event location and administrative_unit_type to match configuration;
boundary_version, model_id and model_version must also match exactly. Every feature and
label event_id/boundary_version is validated before scoring. Labels outside the supplied
prediction universe remain explicit evaluator exclusions, not fabricated negatives.

## Cross-location reuse versus local review

Reusable mechanics: finite input validation, six-feature index implementation, explicit
scenario forwarding, deterministic top-k evaluation, unknown-label accounting, provenance
hashes and review-bundle generation. **Portability of code is not transferability of accuracy.**

Local review is mandatory for:
- boundary vintage/extent, official numbers and internal-ID crosswalk;
- projected CRS suitability and correct horizontal/vertical units;
- feature source provenance, observation coverage and aggregation validity;
- rainfall station/grid provenance, accumulation interval, spatial forcing assumptions;
- independent flooded/non-flooded evidence, timing, unknown coverage and sampling bias;
- relevance of each feature, fixed weights/normalization/category thresholds;
- dominant flood mechanism (urban runoff, river overflow, backwater/tides or others).

No feature relevance, weights or thresholds are automatically learned or validated by
this runner. The baseline is named and explicitly uncalibrated; it may be inappropriate
for a new location. Do not fill missing measurements with zeros to make a run succeed.

## Teammate handoff and pending real run

John: deliver a frozen feature CSV, boundary version and reviewed internal/official ID
map, model revision, and provenance; preserve missing-data failures and forward actual
rainfall duration. Supply the reviewed CRS reference and location/unit metadata. The
runner does not replace pipeline extraction or evidence review. Mit will review local
feature relevance and labels once new requirements arrive; the Chennai pack must not be
relabeled as Kerala evidence. Real execution remains pending these inputs and requirements.

API/UI owners: consume review results only after schema 2.0/nullable coverage/status
migration described in validation.md. Do not infer published accuracy from test bundles
or copy the runner output into canonical metrics without evidence review. Deployment
and API integrations are intentionally unchanged.
