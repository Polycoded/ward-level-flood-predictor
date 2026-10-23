# Combined review guide

The Exercise package guide and earlier model review notes below cover different review stages. Their verification counts describe the original runs; see the implementation plan for the combined merge check.

# Mit local review guide

This guide is new on `mit-dev`; no earlier review-guide file was present in this checkout.
Contract details and dependencies: [handoff](mit_alert_policy_handoff.md).

## Offline demo

From the repository root, use the project's Python environment with existing dependencies:

```sh
python -m scripts.review_alert_policy
python -m pytest tests -q --tb=short -p no:cacheprovider
```

Read `data/evidence/mit_alert_policy_review/scenarios.json`: synthetic dry/low suppressions,
same-total duration effects, trigger, dedup, cooldown, escalation, hysteresis,
release/re-entry, expiry, bounded overflow/retry and exact-hour forecast.
Each output is recomputed twice and compared for determinism. Artificial clock/features,
policy and synthetic CAP geometry are labelled; none are historical observations.
`scenario_summary.json` reports candidate/overflow/suppression/release/escalation counts
for all 22 cases. Four runs use the existing 200 canonical feature rows: synthetic 0/5 mm
controls and hypothetical uniform 230/250 mm totals over 24 h. Station totals are not
adopted ward rainfall. Synthetic controls are not observed dry days or negative labels.
The EN/Tamil CAP examples now use the exact-forecast case end-to-end; see the executable
example and read-only integration mismatch table in the handoff.

Read `messages.json` and `artificial_en.xml` / `artificial_ta.xml`: official ward number,
rainfall/duration, Exercise/action/disclaimer, multipart accounting and approval digests.
Both XML files pass the vendored official CAP 1.2 XSD using local xmllint.
Do not distribute these artificial examples as ward-targeted warnings.

`lookup_diagnostic.json` checks canonical representative points and a 10 m simplification;
it records original Z-coordinate rejection separately from an explicitly derived in-memory
2D comparison. No canonical boundary is edited or approved. `manifest.json` freezes all raw/processed/historical staging files
and relevant source/schema hashes. `historical_status.json` explains why evaluation was
not run; `source_inspection.md` and `rainfall_candidates.csv` document primary-source text
inspection without promoting rainfall or labels.

## Frontend regression checks

```sh
cd web
npm test -- --run
npm run typecheck
npm run build
```

No browser/device/manual visual testing is implied by these automated checks. Existing web
forecast/UI remain outside the standalone Exercise package; do not treat frontend passing
tests as proof of integrated policy behavior or correct live-forecast semantics.

## Recorded results (2026-10-23)

Latest bounded completion pass (supersedes counts below): **134 focused tests**, **603 full
Python tests** passed (54 existing dependency warnings); scoped Ruff passed (existing
config deprecation warning). Byte-identical regeneration of the 22-case bundle and
executable forecast→policy→EN/Tamil→approved Exercise CAP example passed. No frontend,
browser/device or delivery testing was run in this pass; earlier results below are history.

Both synthetic 0/5 mm/24 h canonical controls: 0 candidates/overflow/releases/escalations,
200 suppressions each. Both hypothetical 230/250 mm/24 h uniform sensitivity runs:
2 selected candidates, 198 overflow, 0 suppressions/releases/escalations each under the
unchanged prototype policy. These counts are not accuracy or false-alarm measurements.

Previous package verification:

- Full Python: **564 passed**, 54 dependency deprecation warnings.
- Full frontend: **202 passed** (12 files); TypeScript and production build passed.
- Scoped Python Ruff passed; existing config-format deprecation warning remains.
- Two complete bundle regenerations were byte-identical; 18 deterministic scenarios.
- Both example CAP documents passed the official XSD. No transmission was attempted.
- All 19 frozen canonical/raw/historical-staging hashes, HEAD and staging index unchanged.
- Original canonical 3D polygons: unavailable under existing 2D guard. Diagnostic-only
  2D copy: 200 unique representative-point probes; 15 holed wards; 10 m simplification
  exceeds tolerance (maximum Hausdorff approximately 13.04 m). Do not adopt it automatically.
- Same artificial 100 mm total produces score .45 at 1 h, .30 at 3 h and a below-trigger
  result at 24 h. Heavy 300 mm/3 h yields .90; escalation bypasses cooldown. These are
  mechanics of the existing uncalibrated scorer, not probability or predictive validation.
- Historical evaluation is **blocked**, with no metrics reported. No visual/device QA.

# Mit review and honest demo guide

## Implemented contribution

Mit's work provides strict six-feature scoring, shared explanations, metre-based
geographic helpers, evidence-aware top-k evaluation/runner, input-readiness diagnostics,
duration/scenario regressions, evidence-status integration and physical-proxy suppression.
The review-completion work preserves pipeline fixes, adds compatibility/overflow/repair
guards, compares source conversion and stages research. It does not certify teammates'
original measurements, legal boundary vintage or real-world flood accuracy.

## Exact implemented formula

Let C(x)=min(1,max(0,x)), rain be total mm over duration h, and b be relative built-up %:

```
I_eff = min(I*(1+b/100), 1)
B = .25*C(1-elevation/50) + .15*C(1-slope/15) + .25*I_eff
  + .15*C(1-distance/5000) + .10*C(road_density/20) + .10*(underpasses>0)
D = min(1.5,max(.5,sqrt(3/duration)))
R = min((rain/200)*D,1.5)
index = min(B*R,1)
```

Inputs: elevation metres (negative allowed), slope degrees [0,90], impervious [0,1],
distance metres >=0, roads km/km² >=0, integer underpasses >=0. Rain [0,500], duration
[1,24], b [0,100]; all finite, no missing values or boolean measurements. Categories:
very_low [0,.2), low [.2,.35), moderate [.35,.55), high [.55,.75), very_high [.75,1].
Weights and duration heuristic are prototype assumptions, not fitted physical laws.

## Worked artificial example — not a Chennai observation

Elevation 10 m, slope 2°, impervious .55, distance 1000 m, road density 5 km/km²,
underpasses 0; 100 mm over 3 h and +30% built-up. I_eff=.715. Components are
.20+.13+.17875+.12+.025+0, so B=.65375, D=1, R=.5, index=.326875 (low).
Without increase: .30625 (low). At the same +30%, 1 h gives .4903125 (moderate)
and 12 h gives .1634375 (very_low). None is a probability, water depth or peak time.
The adjustment occurs once on original measurements; it does not mutate the feature row.

## Validation semantics

Select top-k by descending score then numeric internal ID BEFORE inspecting labels.
Unobserved/unknown is never negative. Precision@k is null if any selected status is
unknown; observed-selected precision is a separate, coverage-conditioned measure.
Recall and false-positive rate use explicit observed positive/negative denominators.
Zero denominator means null with a reason, not 0%. Partial coverage is not representative
city-wide accuracy. Evaluated status describes mechanical eligibility, not evidence truth.
Event/boundary metadata are caller attestations. Mock/legacy/invalid payloads render
unavailable; arithmetic tolerance is absolute 1e-12, not a way to repair bad metrics.

## Demo sequence

1. Start API/web using existing project instructions; verify live data source, not fallback.
2. Show a manual scenario, internal versus official ward IDs, index/category/shared reasons.
3. Compare 1/3/12 h and zero/nonzero built-up increase; disclose uniform rainfall assumption.
4. Open evaluation evidence: canonical mock numbers must show unavailable, not accuracy.
5. Show header-only reviewed labels and incomplete event metadata. Show 230/250 mm station
   candidates separately; do not adopt either as measured rainfall for every ward.
6. Show audit hashes, 200 matching mappings/zones, tiny conversion geometry differences and
   unresolved overlaps. Explain what source and measurement review still needs to establish.

## Likely reviewer questions

- **Why these weights?** Hand-chosen transparent prototype; not empirically calibrated.
- **Does high mean flooding is likely?** Only an ordinal index bin, not a validated warning.
- **Where are depth and timing?** Unsupported compatibility proxies, suppressed in product claims.
- **Why no historical accuracy?** Reviewed ward-aligned labels/negatives and aligned event
  metadata are absent; station candidates alone are insufficient.
- **Are boundaries official?** Supplied GCC-labelled KML conversion is structurally checked;
  authentic source chain, legal vintage and historical applicability remain unapproved.
- **Are missing values zero?** New assembly rejects missing measurements. Earlier delivered
  outputs still need a source/nodata audit; genuine zeros cannot prove coverage by themselves.
- **Do geographic checks validate coverage?** No. Valid polygons can overlap or contain holes.
  Current 448 positive-area pairs / 291 over 1 m² need source review, not automatic repair.
- **What remains outside this index?** Local drainage capacity, tides, antecedent saturation,
  spatial rainfall variation and hydraulics. Ward averages also hide local hotspots.

## Verification and evidence

See [mit_implementation_plan.md](mit_implementation_plan.md) for actual latest checks and
[mit_artifact_audit.json](mit_artifact_audit.json) for the read-only artifact snapshot.
Automated DOM tests/build are not live-browser acceptance. Visual verification remains
pending when browser tooling is unavailable. No public-safety or historical-accuracy claim.
