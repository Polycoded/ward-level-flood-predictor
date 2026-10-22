# Evidence-aware top-k evaluation

**No historical performance is established by this implementation.** The canonical
`data/processed/validation_metrics.json` remains empty. No real observations, geographic
evidence, rainfall records or validation metrics were generated. All test fixtures are
artificial. The risk model is an uncalibrated index, not a flood probability.

## What is evaluated

`model.validation.evaluate_predictions(predictions, labels, event_metadata, top_k=20)`
accepts pandas DataFrames and a metadata dictionary. It ranks the **full supplied
prediction universe**, sorts descending by risk_score and then ascending by **numeric
ward_id**, selects top-k, and only then checks observation coverage. It never replaces
an unknown selected ward with a lower-ranked observed ward. This is top-k retrieval,
**not** evaluation of the model's high/very_high categories or a calibrated classifier.

top_k must be a positive integer (not bool or float). Actual selected size is
`k = min(requested_top_k, prediction_count)`; both sizes and ordered selected ward IDs
are returned. Empty predictions are allowed but produce unavailable metrics.

## Evidence schema and alignment

Prediction CSV required columns:

```
ward_id,risk_score,event_id,boundary_version
```

- ward_id: canonical positive administrative integer ID; Python integers or decimal
  strings without leading zeros. Reject floats, booleans, nulls, names and whitespace.
  No fixed ward count or maximum ID is assumed. `ward_number` is not implicitly an ID.
- risk_score: finite numeric [0,1], including endpoints. CSV parsing produces numeric
  values; direct DataFrame calls reject numeric strings/booleans.
- event_id and boundary_version: nonempty identifiers exactly matching metadata.

Observation CSV required columns (also in the **header-only**
`data/fixtures/validation_labels_TEMPLATE.csv`):

```
ward_id,label,source_ref,event_id,boundary_version
```

label must be exactly `flooded`, `non_flooded` or `unknown`. Missing **records** mean
unknown; a present record with a blank/invalid label is rejected so uncertainty is
explicit. Flooded and non_flooded records require a nonempty source_ref that a reviewer
can trace (URL, archived document/page, evidence file/record identifier). Unknown records
may leave source_ref blank/null. A neighbourhood name or news mention alone does not
establish an administrative ward ID or prove that an entire ward was non-flooded.

Both datasets require unique IDs; identical duplicates and conflicting duplicates are
rejected rather than merged. Resolve multiple observations upstream into one reviewed
ward/event status, retaining underlying evidence references. No fuzzy name matching,
implicit boundary crosswalk or automatic deduplication occurs. Duplicate columns are
also rejected (including CSV headers before pandas can silently rename them).

All label records must match the requested event/boundary, including out-of-universe
records. Matching labels outside the prediction universe are **explicit exclusions**
with ward IDs, status and reason, and are excluded from every denominator; review these
before interpreting results. They do not count as model false negatives. The evaluator
does not possess a boundary registry: matching version strings are an attestation,
not independent proof that an ID/geometry/crosswalk is correct.

### Required event metadata JSON

Copy `data/fixtures/validation_event_TEMPLATE.json` to your own evidence directory,
complete every null field, and remove `is_template` or set it to false. The unfilled
template is deliberately rejected. It contains no example historical observations.

| Field | Contract |
| --- | --- |
| event_id | Stable caller-supplied event identifier |
| event_name | Display title, not hardcoded to a particular disaster |
| event_date | Caller-supplied ISO YYYY-MM-DD event reference date |
| boundary_version | Exact administrative boundary snapshot identifier |
| boundary_source_ref | Traceable boundary source/version reference |
| observation_protocol | Flood/non-flood definitions, observation window and adjudication method |
| sampling_notes | Coverage, collection method, biases and limitations; nonempty |
| model_id, model_version | Exact caller-supplied model identifier/revision used to generate predictions |
| rainfall_mm | Finite accumulation [0,500] mm, consistent with the scoring model contract |
| duration_hours | Finite [1,24] h corresponding to that accumulation |

Strings must be nonempty and have no surrounding whitespace. Numeric strings and
booleans are rejected as numeric metadata. Extra JSON metadata is retained and must
be strict-JSON serializable. Recommended extras include rainfall_source_ref,
observation_start/end, boundary hash/CRS, feature artifact hashes, prediction-generation
command, feature provenance, land-use scenario and collection/reviewer identifiers.
The event reference date is not a substitute for an explicit observation window.

At the CLI CSV boundary, both files are read as text without automatic NA conversion.
Optional rainfall_mm/duration_hours columns and prediction risk_score are explicitly
parsed as numbers and checked for finite values and the ranges above. Blank, malformed,
non-finite and out-of-range cells fail; no coercion to missing/zero occurs. All other
columns retain text identifiers (including leading zeros in version/source references).
Direct Python evaluator calls still require numeric values, not numeric strings.

If additional metadata fields listed in the table appear as prediction/label columns,
they must also match event metadata; they are never silently accepted when conflicting.
Other extra DataFrame columns are ignored by evaluation and canonical data hashes.

**Verified by evaluator:** schema/value validity, uniqueness, declared identifier
consistency, selection ordering, counts/arithmetic and hashes of supplied inputs.
**Not verified:** truth or accessibility of references, actual boundary membership,
sampling representativeness, model execution/version truth, rainfall measurements or
event observation truth. `metadata_verification` explicitly records this distinction.

## Exact metrics and denominators

Let U be all predicted wards, S the selected top-k set, P explicitly observed flooded
wards in U and N explicitly observed non_flooded wards in U. Unknown includes missing
labels and explicit unknown records. Counts:

- TP = |S ∩ P| = selected_flooded
- FP = |S ∩ N| = selected_non_flooded
- FN = |P − S|, TN = |N − S|
- selected_unknown = k − TP − FP
- total_observed_flooded = |P|, total_observed_non_flooded = |N|
- total_unknown = |U| − |P| − |N|, with missing_label_count and explicit_unknown_count

TP/FP/FN/TN describe **selection versus observed labels only**. Unknowns are neither
FP nor TN (nor FN). They must not be displayed as an exhaustive full-city confusion matrix.

Every metric is an object with `value`, `numerator`, `denominator` and
`unavailable_reason`. Undefined values use JSON null with an explanatory reason, not 0.
Defined zero fractions remain 0. Unrounded ratios are returned; UI may round for display.

| Metric key | Numerator / denominator | Availability |
| --- | --- | --- |
| metrics.precision_at_k | TP / k | null if k=0 **or any selected ward is unknown** |
| metrics.precision_among_observed_selected | TP / (TP+FP) | null if no selected known observations; **not full top-k precision** |
| metrics.recall_among_observed_flooded | TP / |P| | null if no observed flooded wards; never complete city-wide recall |
| metrics.false_positive_rate_among_observed_non_flooded | FP / |N| | null if no explicitly observed negatives |
| coverage.prediction_universe | (|P|+|N|) / |U| | null if no predictions |
| coverage.selected | (TP+FP) / k | null if no selected wards |

`status` is `unavailable` when U is empty or has no known observations; `partial` when
there are unknown wards in U or excluded labels; otherwise `evaluated`. `evaluated`
means arithmetic was performed with full supplied-universe coverage, **not** that
historical accuracy is validated or representative. Individual metrics can remain
null even for evaluated results (e.g. no observed negatives). Always display warnings,
coverage and denominators beside fractions. No numeric legacy fields are fabricated.

## Result and reproducibility contract (schema_version 2.0)

The result contains status/status_reason, evaluation_type, event_metadata,
metadata_verification, requested_top_k, actual_selected_size, prediction_count,
selected_ward_ids, counts, coverage, metrics, exclusions, warnings and reproducibility.
Permanent warnings flag unverified evidence, convenience-sample bias and the distinction
between top-k selection and model risk categories. Incomplete coverage/exclusions add warnings.

Canonical SHA-256 hashes cover validated predictions in ranking order, observations
sorted by ward ID, and event metadata, serialized as sorted-key strict JSON by this
evaluator. Thus row-order changes alone do not alter canonical hashes. Unknown source
blanks normalize to null and IDs normalize to integers. These are **not** original file
hashes. Reproducibility also records evaluator source SHA-256, Python/pandas versions
and tie/selection rule. No changing wall-clock timestamp is inserted.

The CLI additionally records SHA-256 of the exact bytes parsed for all three input
files, with resolved input paths. Retain these files, the report, source revision and
environment. A model identifier is caller-supplied; hashing the evaluator does not
verify the model that produced the prediction CSV. No model is retrained or run here.

## Reproducible CLI and Python usage

From the repository root, using the project's Python environment:

```bash
python -m model.validation \
  --predictions /absolute/path/to/evidence/predictions.csv \
  --labels /absolute/path/to/evidence/ward_labels.csv \
  --metadata /absolute/path/to/evidence/event.json \
  --top-k 20 \
  --output /absolute/path/to/review/evaluation.json
```

For another working directory, install the project/module or set PYTHONPATH to the
repository root, then use the same command and absolute file paths. No datasets are
downloaded. Header-only labels produce an unavailable report, not invented negatives.
Malformed inputs exit 2 with a diagnostic. `--output` is required, cannot overwrite an
input, and cannot point directly at data/processed/validation_metrics.json. This prevents
accidental publication of exploratory/artificial reports; review separately before publishing.

```python
from model.validation import evaluate_predictions, save_validation_metrics

report = evaluate_predictions(predictions_df, labels_df, event_metadata, top_k=20)
save_validation_metrics(report, "/absolute/path/to/review/evaluation.json")
```

`validate_against_historical(predictions, actual_flooded_wards, top_k=20, *,
event_metadata=..., source_refs={ward_id: reference, ...})` retains its name/positional
shape as a **positive-only adapter**. Metadata and per-positive references are now
mandatory. Missing prediction event/boundary columns are filled from the caller's
explicit metadata attestation; present columns must match. All unlisted wards are
unknown. There are no observed negatives/FPR; recall is only among provided positives.
Return shape intentionally changes to schema 2.0; the old list cannot justify numeric
legacy precision/recall/FPR fields. No repository code calls this adapter currently.

### Persistence

`load_validation_metrics(path=VALIDATION_PATH)` and `save_validation_metrics(report,
path=VALIDATION_PATH)` keep their public names and optional default paths. The default
is anchored to the repository location, **not current working directory**. Explicit
relative paths are interpreted relative to the caller's cwd; use absolute paths for
repeatable automation. Never save artificial reports to the canonical processed path.

Missing, whitespace-empty files or `{}` load as an unavailable status/reason dictionary.
Nonempty malformed JSON, non-object roots, duplicate JSON keys, NaN/Infinity and numeric
overflow produce a ValueError naming the path. Nonempty valid objects are returned as
stored: loading does **not** certify their report schema or evidence quality. Consumers
must require schema_version 2.0 rather than interpreting old payloads as new evidence.
Saving serializes with allow_nan=False **before** touching the existing file, writes
UTF-8 to a temporary sibling, flushes/fsyncs and replaces atomically. Failed writes leave
the previous artifact intact and clean up the temporary file. This is not a multiwriter
locking or directory-fsync durability protocol.

## API and frontend handoffs (not implemented in this task)

**John / API:** api/routes/main.py currently loads JSON directly with a cwd-relative
path and applies the old `ValidationMetrics` schema. Switch to the model loader or an
equivalent repository-anchored loader; handle unavailable status explicitly. Migrate
api/schemas.py to the versioned report, nullable metric values/reasons, coverage,
counts, exclusions and reproducibility. Accept unavailable envelopes with absent report
fields. Do not coerce null metrics into zero or synthesize precision_at_20/recall/FPR.
Malformed published data should generate a clear operational error, not fake metrics.
The existing error handler's pandas Timestamp serialization issue still needs repair.
Readiness must not equate file existence with available evidence. The empty canonical
file is deliberately unchanged, so the old API validation test failure is not fixed here.

**Ronit / frontend:** migrate web/src/types/index.ts ValidationMetrics and
ValidationPanel.tsx together. Show a visible unavailable state; render null as “unavailable”
with its reason (never multiply null by 100). Replace “Dec 2023 Validation” with
event_metadata.event_name/date; replace Precision@20 and hardcoded `/20` with actual
k/requested k and metric denominators. Label observed recall/FPR explicitly, show
unknown-selected and coverage, warnings/exclusions, and title counts as observed-only
top-k outcomes. Do not imply complete city-wide flooded totals or representative accuracy.

**Pipeline / evidence collectors:** export prediction event_id/boundary_version and
verified model/rainfall scenario metadata with the prediction CSV, preserving original
administrative IDs. Collect independent flooded **and explicitly observed non-flooded**
evidence with source records, review observation windows and definitions, and separate
unobserved wards. Resolve ward-version crosswalks manually with traceable boundary maps;
do not infer IDs from neighbourhood names. Preserve raw artifacts and hashes, document
sampling bias, and choose top-k/protocol before inspecting held-out outcomes. A small
convenience sample cannot establish representative accuracy. Depth/timing validation
is a separate task requiring its own observations; no claim about either is made here.

## Verification boundaries

tests/test_validation.py exercises artificial selection/coverage examples, deterministic
ties, invalid inputs/evidence, metadata alignment, positive-only semantics, null
denominators, persistence and CLI byte hashes. Prior risk/geographic mechanics tests
are regression checks only. None of these tests is historical validation or evidence
of forecast accuracy. No actual historical evaluation has been performed.
