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
