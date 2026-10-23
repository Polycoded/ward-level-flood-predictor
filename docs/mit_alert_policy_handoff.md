# Mit Exercise policy handoff

## Delivered boundary

Pure Python, JSON-compatible candidate/content/export contracts. **No new API routes,
database, approval authentication, scheduler, dispatch, provider or resident UI.** Existing
scorer/evaluator coefficients and signatures are unchanged. No operational warning claim.

- `evaluate_alerts(wards, rainfall, policy, prior_state, *, now)` in
  `model/alert_rules.py`: returns `candidates`, full `overflow`, suppressions, lifecycle
  events and `proposed_state`. State is a proposal for pending creation, never delivery.
  Rows need internal `ward_id`, official string `ward_number`, name and the existing six
  scorer features. Explicit offset timestamps and policy/model versions are mandatory.
- `aggregate_forecast(records, *, interval_start, interval_end, issued_at, retrieved_at,
  valid_from, valid_until, now, source, max_age_seconds, max_retrieval_age_seconds)` in
  `model/forecast_input.py`: records contain `interval_end` and `precipitation_mm`.
  Returns normalized UTC total, duration, exact interval, hourly series and provenance.
  `validate_forecast(value, *, now)` repeats envelope/series/freshness checks at decision time.
- `exercise_message(candidate, *, exercise_id, language='en', shelter=None)` in
  `model/alerts.py`: returns full text/instruction, content/candidate binding, SMS units
  and multipart counts. Tamil is draft and requires native-speaker review. Optional shelter
  information must be caller-supplied with name, source reference and HTTPS URL;
  availability/routes remain explicitly unverified. No shortening removes essential text.
- `generate_cap(candidate, content, approval, wards, *, sender, sent, now)` in
  `model/cap.py`: returns `exported` XML only after local official-XSD validation;
  otherwise `unsupported` geometry or `unavailable` validation. Invalid approvals raise.
- `lookup_ward(wards, point, *, point_crs, expected_identities, uncertainty_m=0,
  boundary_tolerance_m=1, metric_crs='EPSG:32644')` in `model/ward_lookup.py`:
  `unique`, `ambiguous`, `outside` or `unavailable`, never first-match resolution.
  `compare_simplification(full, simplified, *, expected_identities, tolerance_m,
  metric_crs='EPSG:32644')` measures Hausdorff/symmetric difference, not legal acceptance.

## Policy and lifecycle integration

Caller supplies the clock, complete ward snapshot and previous state. Prototype thresholds
in the review fixtures are **assumptions**, not calibrated warning levels: trigger .25,
release .2, escalation .6, min rainfall 10 mm, cooldown 3600 s, expiry 7200 s, batch 2.
Below-trigger active state holds until release/expiry; active escalation is latched.
Identical forcing is deduplicated until release/expiry; changed forcing obeys cooldown;
escalation bypasses cooldown. Expired state re-enters only at/above trigger. Forecast expiry
is capped by supplied forecast validity. Manual/historical inputs are explicitly typed;
their timestamps do not turn them into forecasts.

Overflow is returned completely and **does not advance state**. Sort is escalation first,
then descending score, then internal ID. Persist selected pending candidates and state
atomically with optimistic version checks; retry the identical request/clock idempotently.
Use candidate ID as pending-creation idempotency key. Do not blindly overwrite concurrent
state or treat overflow as sent. Policy/model changes require explicit state migration/reset.

Approval is a separate caller-attested object: `status='approved'`, `cancelled=false`,
`candidate_id`, `content_digest=digest(content)`, `approved_by`, `approved_at`.
Content carries `candidate_digest`; any subsequent candidate/content change invalidates
the binding. Authentication, durable approval/audit history, cancellation and transport
authorization remain the orchestrator's responsibility. Process `released`/`expired`
lifecycle events by invalidating pending approvals/content. Release is not an all-clear.
Recheck cancellation/expiry immediately before any future export/send transaction.

CAP ID binds candidate, exact content, sender and sent time: retry with the same sent
timestamp for identical XML/ID. A changed sent timestamp is a new CAP identifier.
Transport idempotency and CAP Update/Cancel references are **not implemented**.

## Forecast contract and migration dependency

Open-Meteo Hourly Parameter Definition (https://open-meteo.com/en/docs) defines
precipitation at `t` as the preceding-hour sum `[t-1h,t)`. Complete matching UTC hours
only; no partial-hour splitting, missing-to-zero substitution or permissive clamping.
Missing/duplicate/nonfinite values, totals outside scorer domain [0,500] mm, durations
outside [1,24] h, stale metadata and already-started forecast windows are rejected.
Timezone-less provider strings must be deliberately normalized by a source-aware adapter.
The strict adapter is offline and requires a trustworthy supplied model issue time:
`generationtime_ms` is processing latency, not an issue timestamp.

**Do not connect `web/src/lib/rainfall.ts` directly to this policy.** That unchanged legacy
adapter uses a different hourly interpretation/missing-value behavior. Its source adapter
and issue-time contract must be migrated before integration. No live forecast was claimed.

## CAP and geography constraints

CAP 1.2 official XSD source/hash lives in `data/fixtures/cap/README.md`; `/usr/bin/xmllint`
with `--nonet` is required. Exercise/Restricted/Alert, Unknown urgency/severity/certainty;
no unsupported flood onset. UTC numeric offset is `-00:00`; XML is escaped by ElementTree.
Multipart exteriors are separate polygons, transformed to WGS84 **latitude,longitude**.
Polygons with holes return unsupported: dropping holes broadens targeting and is forbidden.
XSD validity does not establish SACHET acceptance, sender authority or geographic truth.

Internal ID 1 maps to official ward 168, not official ward 1. Full supplied geometry is
the reference; overlaps, boundary proximity and positional uncertainty require confirmation.
Hole interiors may be outside; hole edges are ambiguous. Missing/invalid geometry, CRS or
identity universe yields unavailable. Simplification within tolerance is not a guarantee of
unchanged membership; canonical geometry is never repaired by this package.
Canonical polygons currently contain Z coordinates and are rejected by the reused 2D
validator. The bundle preserves this original-input rejection. Its separate in-memory
`force_2d`/metric-projection comparison is diagnostic only, not an approved production
boundary conversion; adoption of a reviewed 2D boundary remains an integration dependency.

## Evidence and priority dependencies

`data/evidence/mit_alert_policy_review/` contains 22 repeatable scenarios (synthetic mechanics
and explicitly hypothetical uniform-rainfall sensitivity runs on existing canonical features),
full outputs/messages, synthetic-rectangle CAP examples, canonical lookup diagnostics,
source/model/boundary/crosswalk hashes and a historical blocked report. Examples demonstrate
mechanics, not accuracy. The review script runs offline; it does not rewrite canonical data.

1. Adopt reviewed event-aligned ward labels/explicit negatives, observation window,
   boundary/crosswalk provenance and spatial rainfall before existing historical evaluator runs.
2. Agree source-aware forecast issue-time/UTC adapter and orchestrator state persistence,
   approval/cancellation/idempotency contracts before wiring policy into API workflows.
3. Native-speaker Tamil review and authorized issuer/CAP/SACHET acceptance review before
   any exercise distribution. No real recipients or teammate messages were contacted.

IMD primary PDF text confirms Chennai (AP) 250 mm and Chennai (N) 230 mm over December
3–4 08:30 IST (24 h); these remain station candidates, not adopted uniform ward rainfall.
Historical metrics are null/blocked, not mock percentages or fabricated negatives.

## Bounded completion: counts, SMS and ID validation

`scenario_summary.json` gives candidate, overflow, suppression, release and escalation
counts for every case, including synthetic dry/low controls and wet scenarios. Escalation
count means selected **plus overflow** at the latched escalation policy level; a separate
transition count identifies active-state escalation bypassing cooldown. Neither is a
validated flood severity level. The 230/250 mm over 24 h cases apply each station candidate
uniformly to all 200 canonical feature rows **only as hypothetical sensitivity runs** at
the fixed artificial clock. No ward rainfall is adopted, no thresholds tuned, no observed
dry days/negatives inferred, and no historical or false-alarm metrics calculated.
The blocked report `historical_status.json` is retained unchanged: reviewed mapped flood
observations, explicit negatives, adopted event window, approved boundary/crosswalk
provenance and spatial rainfall input are still missing.

`sms_info(message: str) -> dict` retains `encoding`, `units`, `segments`, `singleLimit`.
For multipart messages it packs complete characters in order: GSM extension characters
use an indivisible two-septet escape sequence, supplementary Unicode characters an
indivisible UTF-16 surrogate pair. Thus 153 `^` characters require **3**, not 2 segments.
No message text or content field is truncated. This is packing accounting, not a provider
delivery/billing guarantee; Unicode encoding label `UCS-2` is retained for compatibility.
Ward lookup now validates IDs before integer conversion: booleans, nonfinite/fractional,
nonpositive and nonnumeric IDs are unavailable. Python/pandas/NumPy integers remain valid
in both feature frames and expected identities. Finite positive integral-valued real IDs
retain existing compatibility. No geometric acceptance guard was relaxed.

## One reproducible complete pipeline

Run from repository root with existing dependencies and local xmllint:

```sh
python -m scripts.review_alert_policy
```

This now creates both language CAP examples from `cases.exact_forecast`, not the manual
trigger fixture. Exact callable sequence (imports/constants are from the existing script):

```python
import geopandas as gpd
from shapely.geometry import box
from model.alert_contract import digest
from model.alert_rules import evaluate_alerts
from model.alerts import exercise_message
from model.cap import generate_cap
from model.forecast_input import aggregate_forecast
from scripts.review_alert_policy import NOW, POLICY, ROW

forecast = aggregate_forecast(
    [{"interval_end": f"2000-01-01T0{i}:00:00Z", "precipitation_mm": 40}
     for i in (1, 2, 3)],
    interval_start=NOW, interval_end="2000-01-01T03:00:00Z",
    issued_at=NOW, retrieved_at=NOW, valid_from=NOW,
    valid_until="2000-01-01T03:00:00Z", now=NOW,
    source="artificial:preceding-hour", max_age_seconds=3600,
    max_retrieval_age_seconds=1800)
result = evaluate_alerts([ROW], forecast, POLICY, {}, now=NOW)
candidate = result["candidates"][0]
pending_state = result["proposed_state"]  # proposal only; no persistence/dispatch
geometry = gpd.GeoDataFrame({"ward_id": [1], "ward_number": ["168"]},
    geometry=[box(400000, 1450000, 400100, 1450100)], crs=32644)
for language in ("en", "ta"):
    content = exercise_message(candidate, exercise_id="ARTIFICIAL-REVIEW", language=language)
    approval = {"status": "approved", "cancelled": False,
        "candidate_id": candidate["candidate_id"], "content_digest": digest(content),
        "approved_by": "ARTIFICIAL reviewer fixture", "approved_at": NOW}
    exported = generate_cap(candidate, content, approval, geometry,
        sender="exercise.invalid", sent=NOW, now=NOW)
    assert exported["status"] == "exported"
```

Expected: preceding-hour `[00:00,03:00)` total 120 mm/3 h; one pending Exercise candidate
(fixture index .36), one proposed state entry; independent EN/Tamil content digests and
XSD-valid Exercise/Restricted CAP documents. The rectangle and approval are **synthetic**;
Tamil remains pending native-speaker review. A digest-bound approval attests supplied
content, not authenticity of geometry or sender authority. Orchestration must separately
bind/review the boundary snapshot and resolve ambiguity before using real targeting.
No delivery, Tamil approval, boundary acceptance or SACHET acceptance is implied.

## Existing teammate interfaces — inspected read-only, not implemented here

| Interface | Concrete mismatch / next owner action |
|---|---|
| `api/schemas.py:101–128` (`AlertRequest`, `AlertMessage`, `AlertResponse`) | Request has rainfall total but no duration/exact interval, clock, policy, prior state or approval. Response has legacy message/deeplink and `sent_at`, not pending candidates/overflow/lifecycle/SMS metadata. Do not equate `sent_at` with delivery. |
| `api/routes/main.py:258–296` (`generate_alerts`) | Calls legacy scoring/message generator, not `evaluate_alerts`/`exercise_message`/`generate_cap`; defaults scoring duration and reads wall clock. No approval/state/export contract. Keep unchanged until orchestrator/API owner adopts a compatible adapter. |
| `web/src/lib/rainfall.ts:93–126` | Forward-hour selection, partial slices and missing/invalid-to-zero clamping differ from strict preceding-hour coverage. No model issue-time/validity/freshness contract. Must not feed policy unchanged. |
| `web/src/lib/sms.ts:17–26` | Uses ceiling(total units/capacity), not atomic packing; still undercounts `^` ×153 and surrogate-pair boundary cases. Backend `sms_info` now fixes this; frontend owner must port parity before displaying delivery/cost claims. |
| `web/src/components/AlertPanel.tsx:39–45` | Sends only ward IDs, rainfall total, language/channels to legacy API; no exact window/policy/state/approval; locally imports the old SMS helper at line 6. Not a policy-integration or delivery test. |
| `data/processed/wards.geojson` / `model/distance.py:33–39` | Canonical Z geometry is rejected by existing 2D guard; 15 diagnostic holed wards cannot use exterior-only CAP. Reviewed boundary conversion/ambiguity resolution needed, not implicit repair. |

No scheduler/dispatcher/provider approval-persistence contract is exposed by the inspected
API files. Required future owner decisions: transactional pending/state writes, cancellation
and expiry rechecks, concurrency/versioning, transport idempotency, authenticated approvers,
reviewed geography and trusted forecast issue-time metadata. Frontend/browser/device and
actual delivery testing are a **separate final integration step**.
