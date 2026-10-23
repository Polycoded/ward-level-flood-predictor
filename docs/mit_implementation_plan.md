# Mit implementation plan

## ValidationPanel artificial fixture follow-up — scope before edits (2026-10-23)

Edit only web/src/components/ValidationPanel.test.tsx and this plan. Add rainfall_mm:100
and duration_hours:3 to shared artificial event metadata, retaining every assertion.
Add an explicit missing-measurement rendering regression requiring unavailable and no
accuracy values. Do not change parser/production code, dependencies or canonical data.
Preserve all staging/pending work on mit-dev. Run panel/parser tests, full frontend tests,
TypeScript, production build and working-tree/cached whitespace checks. No staging,
commits, pushes or branch operations; record actual outcomes below.

Results: panel/parser tests **65 passed**; full frontend suite **164 passed** across
11 files. TypeScript checking and production build passed. All original assertions
retained; missing duration now has an explicit unavailable/no-percentage rendering test.
No production/parser/dependency/canonical changes. Visual verification not performed.

## Validation boundary arithmetic/selection repair — scope before edits (2026-10-23)

Confirmed bounded follow-up; preserve all staged/unstaged work on mit-dev. Edit only:
- api/validation_status.py: adapter-only finite numeric rainfall [0,500]/duration [1,24]
  checks rejecting booleans; all metric/coverage numerators <= denominators; available
  fractions match numerator/denominator with absolute tolerance 1e-12 (no relative
  tolerance); selected IDs unique, count matches actual_selected_size; positive top-k
  and actual size equals min(top-k,prediction_count). Reject, never repair, invalid output.
- tests/test_validation_api.py: isolated independent mutations for each invariant,
  genuine evaluator round trips including fractional and zero-denominator/null metrics.
- web/src/lib/validation.ts: equivalent metric arithmetic and optional evaluator metadata
  measurement guards, preserving minimal unavailable envelopes and valid null metrics.
- web/src/lib/validation.test.ts: dedicated artificial parser regressions, independent
  malformed fields, fractional/zero-denominator/null/tolerance cases and valid states.
- This plan: record actual outcomes/blockers. No schema/routes/UI/store/model/alert/data/
  manifest/lockfile edits; no dependency installation/upgrades or git staging operations.
Run affected Python then existing Python suite; dedicated parser then existing frontend
tests; TypeScript and production build; both working-tree/cached diff checks. Compare
final file hashes and index against initial snapshot. Visual verification not performed.

Boundary repair results: regressions first reproduced 20 failures before adapter fixes.
Final affected API suite: **64 passed**; complete Python tests directory: **470 passed**
(54 existing dependency deprecation warnings). Dedicated parser suite: **56 passed**.
Full frontend suite executed: **160 passed, 3 failed** in the existing, out-of-scope
web/src/components/ValidationPanel.test.tsx. Its shared fixture supplies event name/date
but omits rainfall_mm/duration_hours; the required stricter metadata guard now correctly
rejects it as unavailable. Did not edit that fixture or weaken the parser to make it pass.
Initial type errors in the new parser test were repaired within the allowed test file;
final npm run typecheck and npm run build both passed. New adapter/API-test Ruff passed.
No dependency reinstall/upgrade or permission denial occurred. Genuine evaluator
unavailable/partial/evaluated results (including fractional metrics, unknown selection,
zero denominators and empty prediction universe) round-trip unchanged. Arithmetic uses
absolute 1e-12 tolerance on both boundaries and never changes accepted payload values.
Minimal unavailable frontend envelopes remain valid; malformed/cyclic stored objects
return unavailable rather than throwing. Working-tree/cached diff checks passed; snapshot
audit confirmed only the five allowed paths changed and the staging index is unchanged.
Still on mit-dev. No visual/browser verification performed. The three
component-test fixture failures remain the only failed verification checks in this task;
fixing that excluded file requires a separate authorized follow-up.

## Evidence-status demo integration — scope before implementation (2026-10-23)

Preserve staged and unstaged work on mit-dev. User authorized all phases without
intermediate stops. API: add api/validation_status.py to parse persisted metrics strictly
and validate the existing evaluator's schema-2 contract without rewriting the evaluator;
replace legacy ValidationMetrics in api/schemas.py with evidence-status models retaining
nullable metrics, denominators, coverage, metadata, warnings and extra evaluator fields;
route /validation through that adapter in api/routes/main.py. Invalid/missing/empty/mock/
legacy input returns unavailable with a reason, never fabricated zeros. Canonical files stay intact.
Frontend: web/src/types/index.ts, new lib/validation.ts, api/client.ts, api/mock.ts,
lib/store.ts and components/ValidationPanel.tsx coordinate parsing, fallback and rendering
of unavailable/partial/evaluated evidence, null reasons and observed coverage. Guard legacy
and mock payloads at fetch/store/render boundaries. Use supplied event metadata only.
Physical claims: edit WardDetailPanel.tsx, RankedList.tsx, AlertPanel.tsx, lib/tooltip.ts,
model/alerts.py and mock alert generation to remove proxy claims and disclose an uncalibrated
index while retaining scoring, compatibility fields, category and shared reasons.
Tests: new tests/test_validation_api.py and tests/test_alert_evidence.py, frontend
validation/component/display regressions using isolated data; update affected existing
assertions only where the intended evidence contract changed. Update docs/chennai_handoff.md
for delivered Parquet/KML files and remaining provenance/historical limitations.
Run relevant Python/frontend tests, TypeScript, production build, scoped lint and diff check.
Report visual UI verification separately. No dataset generation, evaluator/scoring/readiness/
alert-duration changes, dependencies, git staging/commit/push/branch operations.

Evidence integration outcome: API boundary preserves complete evaluator schema-2 results
(including null values) in isolated round-trip tests; mock/missing/empty/malformed/legacy
payloads return unavailable without accuracy defaults. Frontend types, parser, fetch/store,
panel and defensive regressions updated together. Removed physical claims from the four
affected displays and both live/mock alert generators; compatibility fields/arguments remain.
Added web/src/components/ValidationPanel.test.tsx and evidence-displays.test.tsx, plus
validation fetch tests in api/client.test.ts and negative proxy assertions in tooltip.test.ts.
337 Python tests passed including existing tests/test_api.py, validation, runner/readiness,
risk engine/duration/scenario and new validation/alert evidence tests (2 existing warnings).
Read-only runtime smoke: delivered features 200x44, zonal stats 200x39; /risk and /scenario
HTTP 200 with 200 wards, /validation HTTP 200 unavailable due to canonical mock notes.
New Python adapter/test Ruff passed. Existing model/alerts.py Ruff issues remain (typing
annotations/import order and whitespace); no unrelated cleanup made. npm test -- --run,
npm run typecheck and npm run build attempted but blocked by missing vitest/tsc commands;
no dependency changes. UI/browser visual checks not performed. Frontend checks remain
unverified, not passed. Final diff/preservation audit follows; no canonical writes or git
staging/commit/push/branch changes. Historical observations/provenance remain unresolved.

## /scenario isolated integration verification (before edits, 2026-10-23)

Read LOCAL_CHAT_HANDOFF.md and current status; stay mit-dev, preserving all pending
/risk duration, overlap/review and documentation edits. Inspected scenario/risk callers,
schemas, scorer and test_risk_duration.py. Add only tests/test_scenario_integration.py
and this plan: monkeypatch loading of shared artificial multi-ward GeoDataFrame; check
zero-increase parity, direct-model agreement at 1/3/12 h with unsaturated increments,
default duration, impervious cap, identity/order, repeatability/nonmutation and 422 bounds.
Production code changes only if these regressions reveal a specific bug. No canonical
inputs/external calls, schema/model/alert/pipeline/UI/dependency edits. Run new tests plus
risk duration/engine tests, scoped Ruff and diff check. No git branch/commit/push actions.

Scenario verification outcome: all 18 new artificial HTTP cases passed on existing
production code; no integration bug exposed and no production fix made. New scenario
tests + risk duration (5) + risk engine (97): **120 passed**, 2 existing FastAPI/Starlette/
Pydantic deprecation warnings. Scoped Ruff passed (existing config deprecation warning)
and git diff --check passed. Used existing temporary interpreter; no dependencies added
or upgraded. Full API suite not run. These tests establish integration mechanics only,
not real feature readiness or flood accuracy. Only new scenario test and this plan changed
in this task; all pre-existing pending edits preserved.

## /risk duration forwarding fix (scope before edits, 2026-10-23)

Read LOCAL_CHAT_HANDOFF.md, status and current callers/schema/tests. Stay mit-dev and
preserve pending documentation/overlap review/diagnostic changes. Change only get_risk
call to forward duration_hours explicitly and RainfallInput rainfall description to total
accumulation over duration_hours. Add isolated HTTP regression tests with patched loading
of artificial valid GeoDataFrame features; compare unsaturated direct scorer outputs for
1/3/12 hours, omitted default 3 and echoed scenario. Update duration statements in handoff
and model docs. No alert/scenario/formula/proxy/type/pipeline/UI/metrics changes. Run new
tests and existing model tests in available environment (no dependency installs), plus
diff check; do not claim the full API suite ran.

Duration fix verification: new tests initially reproduced 3 failures/2 passes before
the production edit; after forwarding, all 5 passed (2 existing API dependency warnings).
Existing risk/geographic/validation/runner/readiness suites: 337 passed, 52 existing
Rasterio/affine warnings. Scoped Ruff on the new test and git diff --check passed.
Used existing temporary Python environment; no installs/upgrades or environment blockers.
Full tests/test_api.py and UI suites were not executed. Preserved all pending overlap/
review/documentation changes. Alerts still default to three hours; real feature/evidence
blockers remain. Changed only the two API lines, new isolated test and three scoped docs.

## Integration documentation reconciliation (before edits, 2026-10-23)

Read ignored LOCAL_CHAT_HANDOFF.md first, git status, current API/scorer, boundary review,
crosswalk/GeoJSON and isolated validation tests. Preserve pending overlap diagnostic,
its tests/review and all prior plan notes. Edit only this plan, chennai_handoff.md and
model_logic.md: replace stale zone inventory with verified 200-ward snapshot and identity
distinction; separate fixed scenario/wrapper duration from remaining /risk and alert
omissions; remove outstanding canonical-file test-failure claim; retain absent features,
upstream zero-fill/mock/evidence blockers; explain >0 versus >1 m² overlap counts and
reference boundary review. Preserve exact formula/proxy caveats. No tests/code/data edits,
network or branch operations. Check source/CSV/geometry read-only and git diff --check;
do not portray dated test evidence as a new suite run.

Reconciliation results: current files confirm 200 valid/nonempty polygons, 200 unique
internal IDs and official numbers, and matching 200-row crosswalk (internal 1 → official
168). Read-only pairwise comparison found 448 positive-area pairs versus 291 over 1 m²,
consistent with the diagnostic/review's distinct predicates. features.parquet absent,
labels zero bytes and metrics explicitly mock. Wrapper/scenario duration forwarding and
single adjustment verified; /risk and /alerts still use default 3 hours. Temporary-fixture
validation regression fix verified in test source. Updated only three allowed docs;
formula unchanged. git diff --check passed; no test suites executed in this docs-only task.
Pre-existing input_readiness.py/test changes and untracked boundary review preserved.

## Boundary overlap diagnostic (scope before implementation)

Add a read-only positive-area overlap diagnostic to input_readiness.py, artificial
overlap/touching tests and a review-document note. Use source coordinate units only
for the intersection predicate; report row pairs and IDs, not unverified metric areas.
Skip topology when geometry is defective. Treat findings as review warnings, without
automatic repair or changing existing readiness gates. Source review remains separate.
Run focused tests and the actual read-only CLI. Preserve existing pending documents.


## 200-ward review scope (2026-10-23, before edits)

User authorized beginning Mit work after repository verification. Keep mit-dev at
6210aba; preserve pipeline/API/UI/canonical data. Perform read-only topology, identity,
source-traceability and local feature inventory review. Add docs/chennai_boundary_review.md
with measured findings and explicit source-access limits. Do not auto-repair boundaries,
attest historical readiness, generate scores, or reuse old zone aggregates. No commits/pushes.
This entry is recorded before creating the review document. Older plan entries are dated
history, not the current input inventory. Current review supersedes the older 15-zone
readiness inventory; the canonical mock-metrics regression was already fixed.


## Chennai input-readiness check (scope before edits, 2026-10-23)

Confirmed mit-dev, clean initial status (prior work is present in this branch); do not
change branches or commit. Read handoff/runner contracts, scorer validation, pipeline
zero-fill logic and API call sites. Add only input_readiness.py, focused tests and updated
handoff. Inspect GeoJSON and optional CSV/Parquet, report structural identity/geometry/
measurement issues without mutations, require version/crosswalk attestations, distinguish
structural scoring from historical readiness, flag explicit mock metrics. New explicit
JSON output only, never canonical data. Run actual local check and model regressions.
No pipeline/API/UI fixes, network access, evidence generation or evaluator replacement.

Implemented input_readiness.py, 13 focused artificial tests and refreshed Chennai handoff.
Actual CLI run exited 1: 15 explicit zone names, 15 blank official numbers, declared
EPSG:32644, no detected geometry/ID defects, absent features.parquet, no version/crosswalk
attestations and explicit MOCK metrics. Historical readiness remains unassessed/pending
reviewed observations/rainfall. Output only at temporary chennai-readiness-20261023-v3.json.
Initial actual check exposed that pandas checks its Parquet engine before path existence;
added an existence check so absent artifacts now receive the correct blocker diagnostic.
Focused tests: 13 passed. Combined first run: 329 passed, 1 failed (11 focused cases at
that point plus existing regressions). The existing validation test assumes an empty
canonical metrics artifact; the actual mock payload now causes KeyError(status).
Existing regressions therefore total 318 passed/1 failed; do not change the mock artifact
or hide that stale fixture dependency. Scoped Ruff and git diff --check passed; existing
dependency warnings remain. No teammate implementation or canonical input edited; no git
branch operations, commits, pushes or network operations performed. Branch stays mit-dev.

## Chennai provenance correction (before edits)

Require per-feature source/version/units/evidence type/coverage/notes/processing attestations
and explicit synthetic_demonstration versus historical_evaluation purpose. Validate before
scoring; historical runs reject synthetic/unknown origins. Label every JSON output with
purpose and coverage limitations. Update artificial fixtures/template/docs and add Chennai
handoff. Preserve coefficients, pipeline/API/UI and evidence. Local processed files checked:
all three remain zero bytes. Run runner tests, regression suites once, Ruff and diff check.

Completed: structured attestations/purpose gate, synthetic notices in both JSON artifacts,
coverage disclosure and Chennai handoff. Runner tests: 43 passed. Risk/geographic/validation
regressions run once: 276 passed (52 existing Rasterio/affine warnings). Scoped Ruff and
git diff --check passed. Real inputs remain pending; no historical accuracy established.

## Location-neutral runner scope (before implementation)

Read risk scorer, geographic and evaluation contracts and current pending changes; no
repository AGENTS.md found. Preserve all prior work and Chennai-specific evidence.
Add one model runner, artificial tests, an unfilled JSON config template and runner docs.
Require explicit feature/label/event/config paths and a new output directory. Config
identifies location/unit/boundary/model and reviewed projected metre CRS; inline ID map
or explicitly referenced identity assertion is checked against feature official_number.
Use unchanged six-feature scorer/validation rules with explicit rain/duration and zero
built-up increase. Validate inputs/evidence before scoring; report unused columns and
record hashes/runtime/scenario/invocation. Export only evaluator prediction columns,
evaluation JSON and manifest. Refuse existing outputs, input collisions and canonical
processed output paths. Test reusable artificial locations, identities, invalid rows,
metadata consistency, duration, hashes and evaluator integration; run existing suites.
No geographic processing/refactors, weights, Kerala evidence or teammate-owned code edits.

Runner implementation/checks: added model/evaluation_runner.py, 33 artificial cases in
tests/test_evaluation_runner.py, data/fixtures/evaluation_config_TEMPLATE.json and
docs/evaluation_runner.md. Uses existing scorer/evaluator validation rather than new
feature bounds; rejects unsupported config keys and exports index-only predictions.
Existing code/contracts/evidence remain unchanged. Combined runner + validation + risk +
geographic command passed **309 tests**, with 52 existing Rasterio/affine warnings.
Scoped Ruff passed (existing top-level config deprecation warning); git diff --check
passed. Same temporary Python 3.11 venv; no dependency changes. Real-data run is pending
location requirements and John's reviewed inputs. API tests not rerun. No commits/pushes.

## December 2023 evidence preparation scope (before changes)

Inspect current data and teammate changes first; preserve all pending edits. Research
and open rainfall, observed flood extent/location and official ward-boundary sources.
Create small source register, pending observation staging and incomplete metadata draft
under data/evidence/, plus historical_evidence.md and implemented-model assumptions.
Promote labels only with exact reviewed boundary/internal-ID alignment; otherwise retain
header-only labels. No raw satellite processing, large downloads, canonical data changes,
model/evaluator/API/UI/pipeline edits or performance claims. Record access failures and
exact John dependencies. Initial inventory: processed wards.geojson, validation_labels.csv
and validation_metrics.json are still zero-byte files; no features/predictions/boundary
crosswalk delivered locally. Git status shows prior Mit edits only, no API/pipeline changes.

Evidence task outcome: added eight source-register entries (inspection status explicit),
four pending location candidates, a zero-row evaluator label CSV and deliberately incomplete
event metadata under data/evidence/chennai_2023/. Added historical_evidence.md with source
links, observation-rule proposal, exact John blockers and tomorrow's honest demonstration;
filled assumptions.md from implemented model/geographic/evaluation contracts.
Opened official GCC/IMD pages and inspected TOI/India Today article bodies. No primary
station table or dated satellite extent could be inspected; IMD PDF read was stopped at
an 8 MB cap and discarded. pypdf was installed only in the existing temporary venv for
that attempted inspection; repository dependencies unchanged. Access failures are documented.
No candidate was mapped to an internal ID; no negatives or historical metrics invented.
CSV structural checks passed: register 8x12, candidates 4x14, reviewed labels 0x5;
incomplete JSON parses and retains template status/null rainfall. Rechecked canonical
processed files remain zero bytes; git diff --check passed. No code changes, pipeline
runs, raw satellite processing, commits or pushes. Tests were not rerun for docs/data-only
work; prior test results are historical check records, not new accuracy evidence.

## Validation CLI numeric-metadata correction (planned before editing)

Read the CLI parsing path: labels are all strings, while predictions infer types for
most optional metadata. Normalize both CSV boundaries: read text without NA inference,
then explicitly parse risk_score (predictions) and optional rainfall_mm/duration_hours
with field-specific finite/range validation. Preserve every other column as text.
Do not relax the direct evaluator's numeric-only contract. Add focused CLI tests for
matching/conflicting metadata, invalid numeric cells and identifier preservation;
run validation and prior risk/geographic suites. No API/UI/pipeline edits.

Correction implemented in model/validation.py with shared explicit CSV numeric parsing;
tests/test_validation.py adds matching/conflicting/invalid optional-metadata CLI cases,
canonical-hash checks for preserved identifier text and direct-Python strictness.
docs/validation.md clarifies the boundary. Combined suites: **276 passed**, with 52
existing Rasterio/affine deprecation warnings. Prior uncommitted work preserved.

## Scope and inspection (before implementation)

No AGENTS.md, CLAUDE.md or CONTRIBUTING instructions were found in the repository;
no AGENTS.md was found along its parent path. Working tree was clean.
Inspected risk_engine.py, reasons.py, depth_band.py, validation.py, rainfall.py,
API routes/schemas/callers, pipeline/build_features.py, existing API tests and README.
Model documentation files were empty.

## Proposed changes

1. Require all six scored features to be finite numeric measurements; reject missing,
   boolean, nonnumeric and physically invalid inputs with field-specific ValueError.
   Do not impute. Ignore unused optional features rather than explaining unscored data.
2. Fix category intervals, explicitly including 1.0 in very_high.
3. Add optional keyword-only duration_hours=3.0 to scoring and explanation functions,
   keeping existing positional arguments. Use a bounded square-root intensity modifier
   relative to three hours, multiplying the existing accumulation factor. This is an
   uncalibrated sensitivity heuristic, not a drainage or probability model.
4. Apply the relative built-up percentage once to original impervious fraction, capped
   at one. Share validated effective features between scoring and explanations; keep
   both existing explanation entry points as compatibility wrappers.
5. Keep the five-element score_ward tuple, enum strings and integer timing output.
   Existing depth is risk_score * 1.5 * rainfall_factor metres; timing is
   max(1, int(3 * (1 + score))). Neither has physical validation. Preserve these
   legacy mappings, mark them unsupported, and do not use them in explanations.
   Proposed future contract: nullable depth/timing plus explicit availability/model
   metadata, coordinated with API/frontend/alerts before changing types. The separate
   depth_band.py estimator uses a different rainfall formula; do not unify it here.
6. Add deterministic model tests using explicitly artificial fixtures for boundaries,
   invalid/missing values, rainfall/duration sensitivity, scenarios, batch operation,
   compatibility and explanation consistency. Run model tests, existing suite and
   scoped lint checks, reporting any environment blockers honestly.
7. Write model contract/formula and integration handoffs; remove unsupported model
   and historical-validation claims from README. Do not produce historical metrics.

## Teammate handoffs discovered

- API routes/main.py ignores duration_hours in compute_risk_score and all calls.
- Scenario route pre-adjusts impervious_frac then passes builtup_increase again.
  Remove pre-adjustment; send original features and forward duration by keyword.
- Pipeline validate_features creates missing columns as zero and coerces missing/bad
  values to zero. Preserve unknowns/provenance and repair data upstream; the model
  cannot distinguish a fabricated zero from a measured zero.
- API must catch model ValueError and surface data-quality failures, not silently
  substitute values or return an unexplained 500.
- API/frontend/alerts expose depth and timing without support; coordinate suppression
  or deprecation. No API, pipeline, frontend, integration or deployment edits planned.

## Implementation and checks

Implemented the scoped plan in risk_engine.py, reasons.py, tests/test_risk_engine.py,
docs/model_logic.md, docs/validation.md and README.md. Preserved tuple/enum/output
types, existing positional calls and three-hour numerical behavior for valid inputs.
Missing inputs now deliberately fail instead of receiving invented defaults.

Checks used Python 3.11.16 in an isolated temporary venv at
`/private/var/folders/xf/gtc75bps4tx93_x6dlwfm01r0000gn/T/opencode/mit-risk-venv`.
The shell had no python, uv, pytest or ruff executables; installed testing/runtime
dependencies there without modifying repository dependency manifests or lockfiles.
This was not a complete locked-environment sync. Relevant installed versions:
pandas 3.1.0, numpy 2.4.6, pytest 9.1.1, ruff 0.17.1, FastAPI 0.159.1.

- `python -m pytest tests/test_risk_engine.py -q`: model mechanics suite (97 cases).
- `python -m pytest -q --tb=short`: 105 passed, 1 failed. The remaining existing
  API test is test_validation_endpoint: empty validation_metrics.json raises a JSON
  decoding error; api/main.py's error handler then fails to serialize Timestamp.
  This path does not call the changed model. Recorded as an API handoff, not repaired
  or hidden by fabricated validation metrics. Two existing dependency deprecation warnings.
- `ruff check model/risk_engine.py model/reasons.py tests/test_risk_engine.py`: passed.
  Ruff warns about the repository's old top-level lint configuration. Kept existing
  str/Enum classes rather than changing enum string semantics to satisfy UP042.
- `git diff --check`: passed.

No geographic data, historical observations, validation metrics, API/pipeline code,
frontend, integrations or deployment files changed. No commit or push performed.
Historical evaluation, upstream unknown-value preservation, API duration forwarding,
double-adjustment removal and coordinated depth/timing deprecation remain pending.

## Geographic task: inspection and proposed changes (before code edits)

Re-read this plan, model_logic.md, model/slope.py, model/distance.py and callers in
pipeline/download_dem.py, zonal_stats.py and build_features.py. No repository or
parent AGENTS.md found. Preserve all existing uncommitted risk-engine work.

1. Slope: require single-band, north-up, unrotated, finite/invertible affine rasters
   with projected metre horizontal axes and metre elevations. Reject geographic slope
   inputs with instructions to reproject first. Validate dimensions, scale/offset and
   declared band units. Read masks and nodata; finite differences require a valid centre
   and valid stencil neighbours (one-sided differences at outer edges). Write float32
   degrees with -9999 nodata, original grid/CRS and explicit degree units.
2. Reprojection helper: accept geographic degree or projected metre single-band DEMs;
   validate grid and vertical units; use actual source bounds by default. Define optional
   bounds explicitly as destination-CRS extent, round coverage outward to whole pixels.
   Use bilinear elevation resampling plus conservative validity resampling, explicit
   NaN source/-9999 destination nodata and float output; preserve metre band units.
   This is in-memory resampling, not vertical datum conversion or missing-data filling.
3. Distances: retain function names and positional calls; add optional metric_crs
   default EPSG:32644. Validate input CRS/units; transform both datasets before taking
   centroids. Return float pandas Series with original indices. Null/empty wards yield
   NaN. Empty or partly missing target sets yield all NaN (coverage unknown); invalid
   or nonfinite geometries raise actionable ValueError, with no automatic repair.
   Consolidate duplicated distance loops. Raw Shapely point helper assumes caller's
   metre coordinates, with optional explicit CRS validation.
4. Add artificial raster/geometry tests for analytical slopes, spacing, masks, missing
   stencil neighbours, grids/CRSs/units, reprojection bounds/nodata, metric distances,
   differing CRSs, index alignment and unavailable geometry policies. Run focused and
   existing model tests plus scoped lint/diff checks; do not run pipeline or download data.
5. Write geographic contracts and exact John integration examples/handoffs. No API,
   pipeline implementation, frontend, deployment or historical-validation changes.

Caller findings: download_dem.create_slope_raster duplicates the model; merge_and_clip_dem
passes UTM bounds/resolution to rasterio.merge on unverified source CRS then merely labels
output EPSG:32644. Reproject actual coordinates before metric merging. zonal_stats's
compute_distance_to_water duplicates distance logic and references unary_union without
an import. Replace with the model function. build_features zero-fills unknowns; preserve
NaNs. Zonal aggregation must respect raster masks/nodata and report coverage, not imply
that a mean over remaining cells represents complete coverage.

## Geographic task: implementation and verification

Changed model/slope.py, model/distance.py, tests/test_geographic_modules.py,
docs/geographic_modules.md, this plan and the geographic link in docs/model_logic.md.
All prior risk-engine code/tests and other pending files were preserved. Pipeline
implementations remain unchanged and do not yet call these modules.

Rasterio's explicit mask precedence can hide a declared nodata sentinel, so the read
path combines both policies explicitly. Added a regression with a masked cell plus
a different declared-nodata cell. Bilinear resampling tests also verify a shifted
analytical plane and exclusion of interpolation influenced by a known masked hole.
An initial singular-transform test expected only a transform error; GDAL dropped CRS
metadata for that artificial file, so the assertion now permits either explicit CRS
or transform rejection. No invalid grid is accepted.

Verification used the same temporary Python 3.11 venv as the risk task, adding
rasterio 1.4.4 (and its dependencies, including affine 3.0.1) outside the repository.
GeoPandas 1.2.0, Shapely 2.2.0 and pyproj 3.7.2 were already installed there.
No dependency manifests/lockfiles changed; this is not a locked-environment sync.

- `python -m pytest tests/test_geographic_modules.py tests/test_risk_engine.py -q --tb=short`:
  **171 passed** (74 geographic cases plus 97 existing risk-engine cases).
  52 dependency PendingDeprecationWarnings from Rasterio's affine multiplication,
  not geometry/CRS or nodata warnings. Tests execute entirely on small artificial fixtures.
- `ruff check model/slope.py model/distance.py tests/test_geographic_modules.py model/risk_engine.py model/reasons.py tests/test_risk_engine.py`:
  **passed**, with the pre-existing top-level Ruff config deprecation warning.
- `git diff --check`: **passed**.
- The API suite was not rerun in this geographic task; the earlier unrelated validation
  endpoint failure remains a recorded handoff, not a claimed passing integration check.

Limitations: whole-raster memory use, no automatic vertical conversion/datum verification,
no rotation/shear support, caller-selected local distance projection suitability, conservative
all-unavailable distance output for partly missing target coverage, and no real geographic
accuracy/coverage verification. John must replace duplicate pipeline implementations,
correct actual DEM reprojection before metric merging, regenerate stale artifacts and
preserve unavailable values through aggregation/feature building. See geographic_modules.md
for exact examples. No dataset downloads, pipeline runs, commits or pushes performed.

## Historical-validation task: proposed changes (before implementation)

Re-read repository instructions (no AGENTS.md in repository or parent paths), validation.py,
risk_engine.py, docs/validation.md, this plan, API schema/validation route, frontend types
and ValidationPanel.tsx. Preserve every prior uncommitted risk/geographic change.
No repository callers invoke validate_against_historical; API reads JSON directly rather
than using load_validation_metrics. API requires non-null legacy numbers; UI hardcodes
Dec 2023 and denominator 20. A versioned result contract requires teammate migration.

1. Add evaluate_predictions(predictions, labels, event_metadata, top_k=20): require
   canonical positive integer ward IDs, unique records, finite [0,1] scores, per-row
   event_id/boundary_version alignment and explicit flooded/non_flooded/unknown labels.
   Known labels require source_ref. Require event identity/date/name, boundary reference,
   observation protocol/sampling notes, model identity/version and rainfall amount/duration.
   Validate structure/consistency, not truth of caller-supplied evidence claims.
2. Sort full universe by descending score then ascending numeric ward ID; select before
   looking at observations. Report requested/actual k, selected IDs, observed-only confusion
   counts, unknown counts, coverage, exclusions for out-of-universe labels and metric
   numerator/denominator/reason records. Unknown selected wards make full precision null;
   name observed-selected precision, observed-positive recall and observed-negative FPR
   distinctly. No high-risk-category evaluation or city-wide accuracy claims.
3. Retain legacy positive-only function name/positional shape, but require explicit metadata
   and per-positive source refs; attach caller-attested event/boundary to legacy prediction
   rows if absent. All unlisted wards remain unknown. Do not invent old precision_at_20,
   recall or false_positive_rate compatibility fields.
4. Make default metrics path repository-anchored, allow explicit paths, load missing/empty
   files as unavailable; diagnose malformed nonempty or non-strict JSON. Serialize strict
   JSON before atomic replacement. CLI output path required; prohibit direct CLI writing
   to the canonical processed metrics artifact. Never write artificial results there.
5. Add python -m model.validation CLI taking prediction CSV, label CSV, metadata JSON,
   --top-k and --output. Include raw file hashes, canonical data hashes, evaluator source
   hash/runtime versions and caller-supplied model identifier. No frameworks/dependencies.
   Add header-only labels and unfilled event-metadata templates, no observations.
6. Test artificial fixtures covering selection, evidence validation, unknowns, exclusions,
   undefined denominators, positive-only semantics, metadata mismatch, file I/O/atomic strict
   JSON and CLI hashes. Run all prior risk/geographic tests and scoped lint/diff checks.
7. Rewrite docs/validation.md with exact schemas/definitions, commands, limitations and
   API/UI handoffs (nullable metrics/reasons, coverage, dynamic event/k titles, unavailable
   status). No API/UI/pipeline implementation or evidence acquisition in this task.

## Historical-validation task: implementation and verification

Implemented schema 2.0 evaluation and `python -m model.validation` CLI in
model/validation.py, artificial tests in tests/test_validation.py, revised
docs/validation.md, and two explicitly named templates in data/fixtures/. Existing
risk/geographic code and tests were not modified. API/UI/pipeline are unchanged.

Evaluator rejects invalid/duplicate/misaligned evidence, retains unknowns, reports
out-of-universe exclusions, sorts deterministically before label coverage, and
returns null/reasons for unavailable metrics. Legacy positive-only adapter now requires
event metadata and per-positive sources and returns the honest versioned contract.
Missing/empty metrics files load unavailable; nonempty bad JSON is diagnosed. Saves
use strict JSON plus atomic sibling-file replacement. CLI requires a separate output
artifact and records exact input-byte hashes, with a test guarding the canonical file.

Checks used the existing temporary Python 3.11 venv recorded above; no dependencies,
manifests or lockfiles were added/changed for this task.

- `python -m pytest tests/test_validation.py tests/test_risk_engine.py tests/test_geographic_modules.py -q --tb=short`:
  **255 passed** (84 validation + 97 risk + 74 geographic cases). The 52 prior
  Rasterio/affine dependency PendingDeprecationWarnings remain.
- Scoped Ruff check of all three model test suites and validation/risk/reasons/slope/
  distance modules: **passed**, with the pre-existing lint-config deprecation warning.
- `git diff --check`: **passed**.
- CLI subprocess integration test runs from another working directory using artificial
  temporary CSV/JSON files, verifies raw SHA-256 hashes, and confirms the canonical
  validation_metrics.json is byte-for-byte unchanged. Tests also cover atomic failure
  cleanup and duplicate CSV headers before pandas can mangle them.
- API suite not rerun: its direct JSON route and old non-null schema are unchanged;
  the earlier empty-artifact/error-serialization failure remains a teammate handoff.

Remaining limitations: references/metadata/boundary membership are caller-attested,
not independently verified; no real label set or representative sampling established;
no historical evaluation performed. John must adopt the versioned loader/schema and
unavailable state, Ronit must render nullable metrics/coverage and dynamic event/k
labels, and evidence collectors must establish reviewed ward IDs, observation windows,
both flooded/non-flooded provenance and sampling bias. Exact contracts/examples are
in docs/validation.md. No real artifacts downloaded, no processed metrics overwritten,
and no commits or pushes performed; all work remains local for review.


## PR #5 integration with Ronit's main branch — 2026-10-23

Scope: resolve the ten merge conflicts in API routes/schemas, API client, AlertPanel, RankedList, ValidationPanel, WardDetailPanel, tooltip, and validation parser/tests. Preserve main's endpoint hardening, map-route ordering, response guards, duration-aware explanations and application flow. Preserve mit-dev's schema-2 evidence contract and suppression of unsupported physical outputs. Adapt web/src/api/validate.ts and its tests to delegate validation to the strict schema-2 parser; update stale integrated comments/caveats in App and WardDetailPanel. Verify combined Python/frontend suites, typecheck, build and whitespace before pushing mit-dev.

Integration follow-up scope: Header and App.test.tsx must use the schema-2 unavailable label instead of the retired placeholder helper. tests/test_api_abuse.py needs isolated shelter fixtures plus an empty-source regression because canonical shelters are absent. No shelter fallback or canonical dataset is added.

Integration verification: 499 Python tests passed (54 dependency deprecation warnings); 202 frontend tests passed; TypeScript and production build passed; git diff --check passed. All ten conflicts resolved while retaining main's safeguards and mit-dev's evidence presentation. Visual browser verification not performed. Historical observations, source/provenance review, and canonical shelter availability remain unresolved.
