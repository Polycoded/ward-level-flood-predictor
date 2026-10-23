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
