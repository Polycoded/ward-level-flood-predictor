# Chennai integration handoff

Original roles remain: John pipeline/API/deployment, Mit geography/model/evidence,
Ronit frontend. Evidence-status API/UI and alert-message integration updated locally
2026-10-23; no scoring, canonical data, readiness or alert-duration changes.

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

Current API wrapper accepts duration_hours and forwards it to the scorer. /scenario
passes original features, the percentage once, and explicit input_data.duration_hours;
the old API pre-adjustment has been removed. /risk now explicitly forwards the requested
duration_hours too; omitting duration retains the schema's 3-hour default.
/alerts also passes only row/rainfall: it uses 3 hours, and AlertRequest has no duration
field. John must coordinate the alert contract if variable duration is needed.
RainfallInput now describes total rainfall accumulation over duration_hours, not intensity.
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

The earlier 15-zone inventory is obsolete. Current files were inspected read-only:
- wards.geojson: **200 nonempty valid polygons**, 200 unique internal ward_id values
  and 200 unique official ward_number values; declared EPSG:32644. ward_crosswalk.csv
  has 200 matching ID/official-number pairs. Internal ID 1 maps to official ward 168,
  not ward 1. Names are generic Ward N; zone labels are not separate ward IDs.
  Crosswalk source label chennai_gcc_kml_2022 is not an independently verified source
  chain/vintage. Counts, names and individual polygon validity do not certify coverage.
- features.parquet: **delivered**, 200 rows × 44 columns; zonal_stats.parquet:
  **delivered**, 200 rows × 39 columns at HEAD 40598b1. Original ward and zone KMLs
  are present under data/raw. CSV/Parquet agreement reported in the delivery review
  establishes serialization consistency, not independently verified measurements.
- validation_metrics.json: nonempty, explicitly says **MOCK NUMBERS** in notes. These
  values are unsuitable for accuracy claims; file existence does not mean validation.
- validation_labels.csv: zero bytes; reviewed observations/rainfall remain pending.

Read-only runtime smoke checks now return HTTP 200 and 200 wards for both /risk and
/scenario using the delivered features. Artifact shapes above were rechecked locally.
Feature availability resolves the earlier missing-artifact blocker, not the outstanding
identity/source/measurement review. The crosswalk supplies a mapping, not certification.
No invented version/identity attestations should be used to pass readiness. Historical readiness is
deliberately never certified by this tool: reviewed observations and supported rainfall
metadata must go through the existing schema-2.0 evaluation workflow separately.

John: original KMLs and the 200-ward feature artifact are now delivered. Complete their
source URLs/hashes/conversion record, confirm legal vintage/crosswalk and review topology
before freezing the layer. Audit original measurements, coverage and missingness rather
than assuming delivered values are verified. pipeline/build_features.py creates missing numeric
columns as zero and coerces invalid/null values via fillna(0). Numeric zeros in a later
file cannot prove these issues were resolved; require upstream audit/provenance.
The remaining API duration omission is /alerts as described above; /risk now forwards
requested duration explicitly. Scenario
double-adjustment and wrapper forwarding are already corrected in current source.

### Overlap review is separate from validity

The pending readiness diagnostic reports **all strictly positive-area intersections**
(no tolerance): current read-only inspection found **448 unordered pairs**. The review
in [chennai_boundary_review.md](chennai_boundary_review.md) reports **291 pairs over
1 m²** in the declared metre CRS. These are different predicates, not conflicting counts.
The 1 m² cutoff is diagnostic, not an acceptance threshold; the readiness diagnostic
itself does not infer units. Touching boundaries have zero intersection area and do
not count. Neither individual validity nor an unchanged structural readiness gate
certifies a nonoverlapping partition or complete coverage. John/Mit must review slivers,
larger overlaps and holes against source/jurisdiction data and document aggregation
treatment, without arbitrary geometry repairs or double-counting.

The /validation boundary now rejects mock, missing, empty, malformed and unsupported
legacy metrics with an explicit unavailable status/reason (no fabricated zeros). Valid
schema-2 evaluator output retains nullable metrics, denominators, coverage, event metadata,
warnings and reproducibility fields. Canonical mock metrics remain untouched. The web
client/store/panel defend against legacy/mock payloads and render evidence status,
observed-sample metrics, null reasons and observation coverage without a hardcoded event.
Ward details, rankings, tooltips and alert previews/messages no longer publish depth or
peak-time proxies; compatibility fields remain. The index is explicitly uncalibrated,
not a validated flood forecast. Tamil alert wording still needs native-speaker review.
Do not portray current polygons as independently certified coverage. Mit: finish reviewed ward observations and a supported
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

Verification chronology: the earlier 15-zone readiness run exited 1; it is dated evidence,
not the present boundary inventory. The canonical-metrics test dependency has since been
fixed: tests/test_validation.py now uses temporary missing/empty/mock files and an isolated
cwd decoy. There is no outstanding failure on that old assumption. The local continuity
handoff records 333 passing model tests before the latest John changes; those suites
were **not rerun in this documentation task**, nor was the API/UI suite. Checks performed
now: source/test inspection, read-only current boundary/crosswalk counts and overlap
comparison, artifact inventory, and git diff --check. No fresh full-suite success is claimed.

Subsequent /risk duration fix checks (2026-10-23): 5 isolated artificial HTTP regressions
passed, comparing explicit 1/3/12-hour scores/reasons against score_ward and verifying
omitted duration remains three hours with matching response metadata. Existing model
suites passed 337 tests. Existing dependency warnings remain; the full API/UI suite was
not run. No real-data scoring or historical validation was performed by these checks.

Evidence-status integration checks (2026-10-23, later local working tree): **337 tests
passed** across validation API, alert evidence, evaluator, risk engine/duration/scenario,
runner, readiness and tests/test_api.py; 2 existing dependency deprecation warnings.
New adapter/test Ruff checks and git diff --check passed. Broader Ruff on model/alerts.py
reported pre-existing annotation/import/blank-line issues; these were not used to weaken
tests or expand the task. Read-only delivered-file smoke checks verified shapes and HTTP
responses noted above. No historical evaluation or measurement verification was performed.
Frontend regressions were added, but npm test, TypeScript checking and production build
could not execute: this checkout lacks web dependencies (vitest/tsc commands not found).
No dependencies installed/upgraded. UI rendering is implemented but not browser/visually
verified; frontend correctness/build remain unverified until the existing toolchain is
available. No screenshots or live-browser acceptance are claimed.

Command below uses **placeholders**, not runnable evidence paths:

```bash
python -m model.evaluation_runner \
  --features /REPLACE/features.csv --labels /REPLACE/reviewed_labels.csv \
  --metadata /REPLACE/event.json --config /REPLACE/completed_config.json \
  --output /REPLACE/new_review_bundle --top-k 20
```

Never publish synthetic demonstrations as historical accuracy or copy them into canonical metrics.
