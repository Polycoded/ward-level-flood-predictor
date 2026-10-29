# Mit implementation plan

## 2026-10-28 authorized fixed XGBoost/five-model extension — scope before edits

Create new files only in ignored data/raw/ml_proxy_experiment_20261028/xgboost_extension/:
preservation baseline including existing experiment environment; separate venv/lock;
fixed configuration, training/read-only verification scripts and small contract tests;
pre-fit fold audit with training-only ND/positive ratios; fold models, OOF predictions,
diagnostics/warnings, metrics, five-model comparison CSV/figure, RESULTS_REVIEW.md and
reproduction evidence. Preserve existing scripts/results/models/canonical inputs/HEAD/index.
Reuse exact 346-row/186-ward dataset, seven proxy positives/339 non-detections, six-feature
allowlist, .5 threshold and original pooled-event geographic folds. Exact user XGBClassifier
settings: binary:logistic/gbtree/hist, 100 rounds, depth2, eta.03, child_weight5, gamma.1,
alpha1/lambda10, full row/column sampling, delta_step1, base_score.5, logloss, seed42,
n_jobs1/validate_parameters=True; scale_pos_weight=training ND/positive only. Fold-fitted
median imputation, no additional weights/scaling/eval_set/early stopping/search. Reuse
prior OOF, identity-check targets/blocks, disclose coverage and use common evaluated rows.
Report pooled/per-block/per-event null-aware metrics and constant/split-tree diagnostics.
Independent metric/model reload/fold imputation/ratio tests; second fresh training output;
preservation and reproducibility checks. No optional full-data refit planned. Separate
environment only; no system-wide runtime installation without authorization. These
already-inspected folds are an exploratory benchmark, not an untouched final test set;
no superiority/calibration/forecast/deployment claims or model selection. This scope/outcome
entry is the sole tracked edit; no app/API/notification/canonical-label/staging/push work.

XGBoost outcomes: fixed 100-round CPU model evaluated on all 346 rows/186 wards with
OOF confusion [[309,30],[6,1]]; detects 1/7 proxy positives and flags 30 non-detections.
Precision .0323/recall .1429/F1 .0526/BA .5272/AP .0387; no improvement over LR primary
metrics, no tuning or winner selection. Fold ND/positive ratios 196/6,252/7,299/7,270/1;
all folds feasible. Each model has 100 split trees/0 constant trees; SW test outputs
are nonetheless constant .06469662487506866; 30 distinct pooled probabilities.
Separate pinned Python3.9.6/XGBoost2.1.4 venv; absent @rpath/libomp resolved only for
the process using new sklearn wheel private runtime, no system installation. No fold
training warnings captured. Initial CSV float32 shortening failed strict reload checks;
outputs preserved as diagnostics; final results_verified/reproduction_verified retain
exact probability decimals with unchanged settings/metrics. Nine tests, independent
all-five pooled/block/event metrics, fresh-process pipeline/native reloads, training-only
medians/weights, scalar-tree probabilities and common-population checks pass. Twenty-three
artifacts reproduce byte-for-byte; runtime durations alone differ as expected. Preservation
verified 17,576 prior regular files/6 symlinks including 17,135 original-venv files,
canonical/prior model outputs, previous plan entries, HEAD/index. Consolidated CSV/figure
and RESULTS_REVIEW.md explicitly label exploratory already-inspected folds, not a final
test/generalization/forecast claim. No app change, notification, label promotion or push.

## 2026-10-28 fixed interpretable tree extension — scope before edits

Create new files only under ignored data/raw/ml_proxy_experiment_20261028/tree_extension/:
training/verification script, preservation snapshot, separate results/models/OOF/metrics,
comparison report and labelled full-data demonstration tree PNG/SVG/text/node counts.
Reuse frozen eligible dataset, six-feature allowlist, reference protocol and existing
fold-audit memberships; import existing metric helper without modifying prior code/results.
DecisionTreeClassifier max_depth=2/min_samples_leaf=10/class_weight=balanced/random_state=42,
fold-fitted median imputation, threshold .5. No search/label tuning/model winner selection.
Compare saved existing majority/LR/RF OOF results on identical rows; save four fold
pipelines and distinctly labelled full-data refit. Verify predictions, fold medians,
metrics/counts/tree node counts/reproducibility and prior/canonical/HEAD/index preservation.
This append/outcome entry is the only tracked edit; no application integration.

Tree extension outcomes: actual four-block OOF tree precision .0556, recall .2857,
F1 .0930, balanced accuracy .5927, AP .0302; confusion [[305,34],[5,2]], 2/7 proxy
positives detected and 34 proxy non-detections flagged. Lower than LR on all primary
metrics; AP much lower than forest despite higher threshold-.5 recall/F1. No winner
selection or forecasting claim. All 346 rows/186 wards evaluated; NW/SE positive-test
metrics remain null. Four saved fold pipelines plus separate 346-row demonstration
refit with feature/threshold/raw-count PNG/SVG, rules and exact node counts. First-run
diagram annotation defect was caught by visual review; its outputs remain untouched
in tree_extension/results/ as diagnostic-only. Corrected deliverables are exclusively
tree_extension/results_verified/; independent reproduction matches all 15 files byte-for-byte.
Verification checks exact model settings, train-only medians, fold identities, scalar
leaf probabilities, independent pooled/fold/event metrics and branch-label/node-count
diagram regression. All 163 frozen prior/canonical files and original 105-file snapshot,
HEAD/index preserved. No source label/app/API changes, notifications, staging or push.

## 2026-10-28 authorized isolated weak-label ML proof of concept — scope before edits

User explicitly authorizes experimental construction/training, superseding earlier stop
only for this experiment. New scripts/data/models/reports/tests/environment live exclusively
in ignored data/raw/ml_proxy_experiment_20261028/. Preserve canonical data and every prior
audit output; snapshot bytes plus HEAD/index before implementation. This scope/outcome
append is the only tracked edit. No application scorer/API/service/dependency changes.
Freeze reference protocol unchanged (.90 quality/.90 coverage/4-connected >=4 cells/.05
fraction/250m boundary). Map only the two known candidate categories to new experimental_proxy_target;
exclude unknowns and leave accepted_label unchanged. Join by internal ward_id with identity
and crosswalk verification, never row order. Fixed six raw predictors: elevation_mean,
slope_mean, impervious_frac, dist_to_water_m, road_density_km_per_sqkm, underpass_count.
No identifiers, coordinates, event/block or target-construction variables as predictors.
CPU seed42; Dummy majority; balanced LogisticRegression C=1/liblinear with median
imputation and scaling; balanced-subsample RandomForest 100 trees/depth3/min_leaf5,
max_features=1.0/n_jobs1 with median imputation. No search or label tuning. Threshold .5.
Pool events, leave one existing geographic block out; preserve ward grouping; preflight
class counts before any fit; infeasible folds retain missing predictions and explicit status.
Save fold pipelines and clearly marked full-eligible refits, OOF predictions, strict-null
metrics/per-fold/per-event confusion counts, results figure/model card/faculty note,
environment and hashes, reproducible command and independent verification. No training
winner selection or operational/dry-ground-truth claims; stop after results for review.

Experiment outcomes: genuine fitted CPU LR/forest pipelines and majority baseline,
346 rows (7 proxy positives/339 non-detections) across 186 wards, 54 unknown rows excluded.
Four pooled geographic held-out folds all have both classes in training; NW/SE tests
have no positives so positive recall/AP and related fold metrics are explicitly null.
Pooled OOF LR precision .125, recall .7143, F1 .2128, balanced accuracy .8055, AP .2265;
forest .0385/.1429/.0606/.5346/.2183; dummy recall/F1=0, balanced accuracy .5/AP .0202.
Not a stable superiority/forecast/calibration claim; no winner selected. Saved fold and
separately named full-eligible refit models, reproducible outputs, model card/faculty note.
Six contract/arithmetic tests and fresh-process fitted-pipeline OOF/metric/preprocessing
checks pass. Local optional full-refit LR inference matmul warnings are recorded; all
probabilities finite and match independent scalar-dot/expit math at 1e-12. Second full
training run reproduces results; canonical/previous audit bytes and HEAD/index preserved.
No application change, notification, staging, commit or push. Stop for review.

## 2026-10-28 reviewer amendment — scope before edits

Continue ignored data/raw/research_audit_20261027/ audit without rewriting prior outputs.
New files only in review_20261028/: source/method snapshots and manifest, predeclared
protocol sensitivity scripts/tables, representative 2015 disagreement maps, terrain
replacement provenance and REVIEW_AMENDMENT.md. This append is the only tracked scope
change; preserve HEAD/index, canonical bytes and existing work. No training or accepted
dataset/labels; target is satellite-mapped inundation under a defined observation protocol,
never an inference that non-detected wards are actually dry. No large raster downloads.

Amendment outcomes: publication tag and previously pinned MODIS method files match;
per-image Terra/Aqua QA uses OR clearance in that code, but downloaded archives lack a
generating-code/scene attestation. Terrain mask code uses GMTED2010 <=5 degree slopes;
SRTMGL1 V003 identified as a source-verifiable replacement proposal, no terrain fetch.
New full-raster pre-ward component sensitivity gives 1296 event-setting rows and 5184
geographic-block rows. Reference 250m band counts A/B/unknown: 2005 5/161/34;
2015 2/178/20, all accepted labels remain unknown; four-block validation gate fails.
Fixed representative 2015 maps show strong disagreement, neither source treated as truth.
REVIEW_AMENDMENT.md retains no-go for accepted construction/training pending review.

## 2026-10-27 isolated supervised-data feasibility audit — scope before edits

Verified clean main at 86967bc8468afd77e18e473f17d7b21852062300; no Git operations
authorized beyond inspection. Local plan: data/raw/research_audit_20261027/AUDIT_PLAN.md.
All downloads, audit scripts, baselines, source manifests, inventories, provisional
intersection tables/maps and FEASIBILITY_REPORT.md/NEXT_STAGE_SCOPE.md remain in that
already ignored folder. This scope entry is the only intended tracked edit. Read-only
canonical/source inspection; no training, scoring changes, labels promotion, dependency
manifest edits, notification services or publication. Verify frozen bytes/HEAD/index at end.

Audit outcome: local ignored report/data diagnostics/intersection maps and source manifest
created; no training or runtime edits. HF Chennai history pinned at 60074d53fc80d5b61e07494d4c52cebafe242198;
extents lack observation coverage. GFD 2758/4309 actual archives provide coverage/water
bands at native ~250m, CC BY-NC 4.0; protocol and historical features remain unapproved.
All provisional ward outcomes remain unknown. NO-GO training now; conditional next-stage
GFD protocol/feature review, requiring separate authorization. See isolated report for
actual counts, source terms, canonical hashes and final verification; stop for Mit review.

## master_dev / main merge resolution (2026-10-23)

Combined-branch verification: 664 Python tests passed (54 existing dependency warnings); 251 frontend tests passed; TypeScript and production build passed. Temporary test environment received already-declared integration dependencies; project manifests/locks were not changed for testing. Historical review bundles retain their original snapshot hashes and are not a current merged-source audit.

Scope: combine main alert-duration support with master_dev Exercise content and atomic SMS packing; preserve full messages and both documentation histories. Keep teammate integrations from the automatic merge. Validate affected alert contracts and the combined suites before pushing master_dev for PR #8.

## Bounded Mit completion pass — scope before edits (2026-10-23)

Remain on mit-dev; preserve all existing tracked/untracked work and teammate interfaces.
Edit only model/alerts.py (atomic GSM extension/UTF-16 character multipart packing,
same text and return fields), model/ward_lookup.py (validate IDs before conversion,
preserve pandas/NumPy integral IDs, unavailable on invalid input), their existing
tests/test_alert_evidence.py and tests/test_ward_lookup.py regressions, and
scripts/review_alert_policy.py (per-scenario candidate/overflow/suppression/release/
escalation counts, clearly synthetic dry cases, hypothetical uniform 230/250 mm over
24 h on existing canonical features, reuse exact-forecast candidate for end-to-end
content/CAP example). Refresh generated files only in data/evidence/mit_alert_policy_review/
through that script. Preserve historical_status.json, rainfall candidates/source notes
and all frozen raw/processed/historical inputs. Update docs/mit_alert_policy_handoff.md,
docs/mit_review_guide.md and this plan with contracts, executable example, read-only
teammate interface mismatches, actual outcomes and external gates. No scorer/threshold
changes, historical metrics, labels, endpoints, dispatch/scheduler/UI/provider work.
Target 15 minutes of bounded implementation then focused/full Python, scoped Ruff,
whitespace, repeatable bundle/hash and HEAD/index/input-preservation checks. Frontend,
browser/device/delivery integration testing is explicitly deferred, not claimed.

Completion-pass results: tests first reproduced 11 failures (atomic GSM/UTF-16 boundary
under-counts, boolean ID acceptance, infinity conversion crashes and NumPy expected-ID
rejection). Fixed only the scoped implementations; affected suite 81 passed, all five
Exercise suites 134 passed; full Python 603 passed with 54 existing dependency warnings.
Scoped Ruff passed (existing config deprecation warning). Existing script now regenerates
22 cases with explicit counts, synthetic controls and canonical-feature hypothetical
230/250 mm/24 h sensitivities (each 2 selected/198 overflow, no release/escalation).
Both synthetic 0/5 mm controls suppress all 200 wards, not observed negatives. Bundle
regeneration is byte-identical, both forecast-based EN/draft Tamil CAPs are official-XSD
valid, and the handoff's Python example was executed successfully. Historical blocked
report unchanged; no metrics calculated. Read-only interface inspection found legacy
API schema/duration/state/approval mismatch, forward-hour frontend forecast behavior,
frontend ceil-based SMS under-counts and canonical Z/holed-geometry limitations; exact
references and external owner gates are in docs/mit_alert_policy_handoff.md. No teammate
interface, scoring coefficient, canonical input or deployment code was edited.

## Mit Exercise alert-policy package — scope before edits (2026-10-23)

User correction authorizes implementation on clean mit-dev; no branch/index/history writes.
Reuse score_ward/effective_inputs, evaluator/runner, geographic validation and SMS semantics.
Add model/alert_rules.py (pure policy/state), model/forecast_input.py (exact UTC interval
adapter), model/ward_lookup.py (metre-based ambiguity/simplification checks), model/cap.py
(approved Exercise-only XML with explicit unsupported geometry results), and a small shared
model/alert_contract.py for time/numeric/JSON validation. Extend model/alerts.py compatibly
with Exercise rendering and SMS metadata; no truncation of essential content. No endpoints,
dispatchers, providers, DB, scheduler or resident UI. Existing API signatures remain valid.
Add focused tests/test_alert_rules.py, test_forecast_input.py, test_ward_lookup.py,
test_cap.py and Exercise-message cases in tests/test_alert_evidence.py; reuse fixture patterns.
Vendor unmodified official CAP-v1.2.xsd under data/fixtures/cap/ with source/hash notice;
use existing /usr/bin/xmllint (no new dependency). Add scripts/review_alert_policy.py to
produce a new data/evidence/mit_alert_policy_review/ bundle: artificial scenarios, example
Exercise content/XML, canonical hash/lookup diagnostic, historical blocked report and source
inspection notes. Add/reference existing local rainfall research without adopting candidates
or modifying incomplete metadata/labels/mock metrics. Add docs/mit_alert_policy_handoff.md
and update docs/mit_review_guide.md and this plan with actual verification/dependencies.
Official sources inspected before interpretation: Open-Meteo hourly precipitation is a
preceding-hour sum, not a forward hour; CAP 1.2 uses WGS84 lat,lon and Exercise status.
Keep legacy web rainfall adapter unchanged; document its incompatible semantics as a
handoff dependency rather than silently adopting it for policy. Full Python and affected
frontend/TypeScript/build checks, both whitespace checks, frozen canonical hash comparison.
No scoring coefficients, canonical datasets, geographic acceptance rules, dependencies,
historical claims or unrelated cleanup. Missing evidence blocks historical evaluation only.
Shared new Exercise fixtures live in tests/conftest.py (named fixtures, no autouse);
they do not substitute real data or alter existing test contracts.
Review discovery before diagnostic extension: canonical polygons contain Z coordinates;
existing 2D geographic validators reject them. Preserve that rejection in bundle; explicitly
derive an in-memory force_2d diagnostic copy for simplification/membership comparisons only.
Do not change canonical files, acceptance rules or claim operational approval of that copy.

Package outcomes (2026-10-23): implemented standalone strict forecast/policy/state,
Exercise English/draft Tamil rendering and full SMS accounting, approved-content CAP 1.2
export and ambiguity-aware lookup/simplification diagnostics. Added 18 deterministic
scenarios and a source/hash/lookup/message/CAP/historical-status bundle outside processed/.
Primary IMD PDF text inspection confirms station candidates only (250/230 mm over 24 h);
no reviewed labels, negatives, rainfall adoption or historical metrics were fabricated.
Both complete offline bundle regenerations are byte-identical. Original canonical Z
geometry is unavailable under the existing validator; explicit diagnostic-only 2D copy has
200 unique representative-point lookups, 15 holed wards, and 10 m simplification exceeds
tolerance (maximum Hausdorff about 13.04 m). This is not boundary acceptance.
Full Python: 564 passed, 54 dependency deprecation warnings. Full frontend: 202 passed
across 12 files; TypeScript and production build passed. Scoped Ruff passed after cleanup
(existing top-level Ruff configuration deprecation warning remains). Both tracked whitespace
checks passed. Frozen audit confirms all 19 canonical/raw/historical-staging input hashes,
HEAD and index unchanged. No staging/commits/pushes/branch changes. Browser/device visual
verification not performed. Handoff and new review guide document remaining forecast issue
time, 2D boundary approval, historical evidence, Tamil, approval/transport and SACHET gates.

## Honest demo presets, road screening and alert duration — before edits (2026-10-23)

Preserve pending completion work on mit-review-completion. Change RainfallControl preset
and RankedList empty-state historical attribution to hypothetical/manual wording. MapView
road popups suppress compatibility depth and closure/diversion recommendations. Add default
3-hour duration_hours to AlertRequest; forward through alert route/scoring/message generation,
web client/mock and AlertPanel, keeping older omitted-duration calls compatible. Messages
state the selected accumulation interval; no new physical forecast. Keep baseline land-use
alert semantics explicit rather than silently adding a built-up contract. Add isolated alert
HTTP/message regressions and frontend request/mock/UI/road/preset regressions; adjust existing
preset selectors, not assertions' strength. Update pitch/demo_script.md and docs/frontend.md
to actual evidence status, preview-only notifications, unverified shelters/latency and duration.
No audit/evidence/provenance/canonical data/coefficient/dependency changes or git write actions.
Run affected/full Python and frontend suites, TypeScript/build and both whitespace checks.

Demo repair results: full Python suite **542 passed** (54 existing dependency warnings);
full frontend **209 passed** across 13 files. TypeScript and production build passed.
New alert integration tests compare direct scorer/map categories at 1/3/12/1.5 hours,
check omission=3, invalid intervals=422 and bilingual fractional interval preservation
before SMS truncation. DOM tests exercise hypothetical preset, road popup/legend suppression,
analyzed-versus-unsubmitted alert interval, client body and mock scoring. One initial new
preset test used an incomplete accessible name; corrected to the actual label including mm,
then full suite passed without weakening behavior assertions. Compatibility response fields,
scoring coefficients and evidence/audit artifacts unchanged. Messages remain baseline land
use; road screening retains its separate default interval. Browser visual verification not
performed; DOM tests mock Leaflet and are not visual acceptance. Exact manual demo steps
are in pitch/demo_script.md. No regeneration/dependencies/staging/commit/push/branch actions.

## Audit acknowledgement correction — scope before edits (2026-10-23)

Edit only scripts/review_chennai_artifacts.py, new tests/test_review_chennai_audit.py,
docs/mit_artifact_audit.json and this plan. Replace hardcoded repair acknowledgement
with null and an explicit unverified status: directory inspection cannot establish the
conversion invocation or caller consent. No caller-attestation option is needed.
Add an isolated artificial-directory regression; refresh only the audit report from
the existing temporary conversion, without re-running conversion or changing canonical
inputs. Run audit/pipeline tests and working-tree/cached whitespace checks. Preserve
pending work and staging on mit-review-completion; do not touch the auxiliary index.
Base source revision: 1bb52ed2adc5c76d199d86727d2460a1d33c9e1c plus pending local changes.

Report refresh invocation (no conversion/dataset regeneration):
```bash
/private/var/folders/xf/gtc75bps4tx93_x6dlwfm01r0000gn/T/opencode/mit-risk-venv/bin/python scripts/review_chennai_artifacts.py --review-dir /private/var/folders/xf/gtc75bps4tx93_x6dlwfm01r0000gn/T/opencode/chennai-kml-review-lgw30l7i > docs/mit_artifact_audit.json
```
Audit script SHA-256 at refresh:
`b4a538d2a781f4bd69dcea0b46a1c4ef5a183ed05f107f5b9d0bbab04c746366`.
Affected audit/pipeline tests: **19 passed**. Report now explicitly records null repair
acknowledgement with status unverified_from_directory. Prior conversion invocation notes
are historical execution notes, not evidence independently established by the audit.

## Review completion — scope before edits (2026-10-23)

Stay mit-review-completion and preserve existing pipeline/build_features.py,
pipeline/extract_wards_from_kml.py and tests/test_pipeline_contracts.py work. Review
compatibility and add targeted regressions/fixes only in those pipeline files/tests.
Run conversion with explicit --repair-invalid acknowledgement only into a new temporary
directory. Add scripts/review_chennai_artifacts.py and docs/mit_artifact_audit.json for
read-only hash/range/missingness/identity/topology/conversion comparison evidence.
Update docs/model_logic.md, docs/chennai_boundary_review.md, docs/historical_evidence.md,
docs/chennai_handoff.md and add docs/mit_review_guide.md; preserve dated findings as history.
Copy supplied rainfall candidate CSV/review into data/evidence/chennai_2023, annotate the
review as imported reference and append source-register entry without inventing provenance
approval. Keep incomplete event metadata/labels untouched. No canonical regeneration,
scoring/product-contract/dependency changes, teammate messages or git write operations.
Run focused/full Python, full frontend, TypeScript/build and whitespace checks; attempt
browser verification only if tooling exists, otherwise explicitly mark it pending.

Review outcome: preserved initial 13-case pipeline work and added five regressions;
18 focused tests pass. Delivered zonal/features tables pass the stricter validator.
Additional defects guarded: int64 overflow in unscored integer columns, duplicate columns,
nonpolygon source layers and implicit zone repair inside GeoPandas overlay. Genuine zeros,
negative elevations and numeric CSV measurement strings remain accepted. Invalid ward/zone
repair now requires acknowledgement; nine raw source wards are invalid. No canonical repair.

Conversion command: existing temporary interpreter, `-m pipeline.extract_wards_from_kml
--output-dir /private/var/folders/xf/gtc75bps4tx93_x6dlwfm01r0000gn/T/opencode/chennai-kml-review-lgw30l7i
--repair-invalid` (invoked via main with these arguments). All 200 internal/official mappings
and zone assignments match canonical wards/crosswalk. 200 exact geometry differences;
largest symmetric difference 7.78921640840568e-05 m². Canonical feature geometries match
wards; zonal stats is tabular without geometry. Audit hashes rechecked unchanged after work.
Six required measurements have zero missing/nonfinite entries; source completeness is NOT
proven. Canonical overlaps remain 448 positive-area pairs, 291 over 1 m². No regeneration.

Upstream/product findings held for review rather than silently expanded: delivered numeric
zeros still cannot establish actual observation coverage; the old auxiliary flood_prone_index
derivation can divide by zero on all-zero maxima and is not the scorer's index. Geometry
attachment assumes the frozen ID mapping and EPSG:32644; this local audit confirms current
alignment, not arbitrary future inputs. Authenticity/legal vintage, missingness provenance,
overlap/hole treatment and historical applicability need human/source review.

Research: imported supplied bulletin-text review and exact two-row rainfall CSV; validated
CSV shape, cm→mm conversion and timezone interval length. IMD03 inspection/date is attributed
to supplied research, not a fresh PDF inspection. Both station candidates remain unadopted;
incomplete metadata/reviewed labels unchanged. No new observations/negative labels/metrics.

Final checks: **517 Python tests passed**, 54 existing dependency warnings; **202 frontend
tests passed** across 12 files; TypeScript and production build passed. Working-tree and
cached whitespace checks passed. Playwright/Puppeteer/@playwright/test unavailable in web;
Python Playwright also absent. No browser live integration or visual verification claimed:
visual acceptance remains pending, not replaced by jsdom tests. No installs, branch changes,
staging/commits/pushes or teammate messages. New audit/review guide and four requested docs
record current status while retaining dated historical findings.


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


## Completion branch — 2026-10-23

Authorized scope: close remaining implementation/review work on mit-review-completion from main. Fix pipeline/build_features.py to reject missing/invalid required measurements and identities without zero imputation or input mutation. Fix pipeline/extract_wards_from_kml.py to produce explicit stable identity columns and crosswalk names, provide configurable input/output paths, and protect existing canonical outputs. Add isolated regressions for both. Do not regenerate canonical data. Create a read-only hashed artifact audit and update current model/geographic/historical/handoff documentation, preserving dated evidence limitations. Stage sourced IMD rainfall candidates and the newly inspected NRSC acquisition report without inventing labels, negatives or historical accuracy. Prepare a review guide and inspect the integrated app in a browser where tooling permits. Run affected/full tests and production build. Source provenance, legal vintage, flood mask coverage and event alignment remain evidence requirements rather than fields to fabricate.


## Logistic-only publication cleanup — 2026-10-28

Authorized: publish an isolated, reproducible logistic-regression experiment on mit-dev; preserve application behavior and canonical data. Add research/logistic_regression with frozen proxy dataset, fold results, portable fitted parameters, training/prediction commands and evidence limitations. Add a short README link. Preserve historical audit notes; archive the superseded multi-model local experiment outside the repository after verification. No other classifier is included in the published research package. Verify metrics, portable predictions, reproducibility and branch ancestry before commit/push.

Cleanup verification: three logistic evidence tests pass; all 346 portable OOF scores match the original saved logistic predictions within 1e-12; a fresh training run produced byte-identical result files; standard-library inference smoke check passes. Other model experiments and original environments preserved outside the checkout at ../ward-level-flood-predictor-local-archive/ml_proxy_experiment_20261028. No application code or canonical data changed. Only logistic regression is included in the new tracked research package.
