# December 2023 Chennai evidence preparation

## Current status — review completion, 2026-10-23

Ward/zone KMLs, 200-ward crosswalk and features are now delivered. See the
[artifact audit](mit_artifact_audit.json), not the historical missing/empty inventory below.
No reviewed flood labels, explicit negatives, approved metadata or historical metrics exist.
The evidence-status API/UI suppress canonical mock metrics rather than claiming accuracy.

User-supplied research is incorporated as
[rainfall_review.md](../data/evidence/chennai_2023/rainfall_review.md) and
[rainfall_candidates.csv](../data/evidence/chennai_2023/rainfall_candidates.csv).
It reports text inspection of a separate IMD bulletin (IMD03), page 2: Chennai (N)
23 cm / 230 mm and Chennai (AP) 25 cm / 250 mm, both 24 hours ending 4 December 2023
08:30 IST. Both are station candidates, not ward measurements or adopted historical
forcing. No source PDF bytes/hash or visual page verification is claimed in this phase.
Earlier IMD02 access failures below refer to a different report and remain history.
event_metadata_INCOMPLETE.json stays incomplete. Spatial representativeness, observation
window, ward alignment and provenance still require review before evaluation.

## Archived research inventory and findings (2026-10-22)

Research checked 2026-10-22. **No evaluator-ready historical labels or accuracy metrics.**
This is a traceable research staging pack, not a completed evaluation. Source IDs resolve
to URLs and inspection notes in `data/evidence/chennai_2023/source_register.csv`.
Publication dates absent from inspected pages remain blank, not inferred from titles.

## Local inventory and teammate changes

Rechecked actual files, not earlier assumptions: data/processed/wards.geojson,
validation_labels.csv and validation_metrics.json are each zero bytes. No local feature
table, prediction CSV, boundary version or John-approved ward crosswalk was found.
Git status shows the existing Mit changes; no new API/pipeline edits. Latest commit is
a3699ff (John's portion); its existence does not mean processed evidence was delivered.
No repository or parent AGENTS.md found. Prior work preserved.

pipeline/download_wards.py lines 73–82 explicitly keeps ward_number as text, sorts it,
then assigns ward_id = index + 1. Lexical ordering, missing numbers and source filtering
can change those IDs. They are NOT official ward numbers. No neighbourhood-to-ID lookup
or ward_id=ward_number substitution is defensible here.

## Inspected findings

- **GCC01:** official [Ward Maps / Delimitation](https://chennaicorporation.gov.in/gcc/delimited_ward/)
  page lists zones, a 2018 delimitation PDF and a Reservation–2022 tab. It says gazette
  notification is final in case of discrepancies. This identifies the authoritative
  verification route, not a verified 2023 GIS snapshot. GCC02 PDF contents were not read.
- **IMD01:** official [monsoon-report index](https://mausam.imd.gov.in/chennai/monsoon.php)
  links Northeast Monsoon 2023. IMD02 PDF could not be inspected: web tool cannot extract
  it and a bounded in-memory read exceeded an 8 MB cap. Partial bytes discarded; no
  primary rainfall totals or page citations claimed. Obtain a small station-table excerpt
  or review the original report manually before accepting a rainfall scenario.
- **RAIN01:** [TOI article](https://timesofindia.indiatimes.com/city/chennai/michaung-dumped-more-rain-than-2015-cyclone/articleshow/105767336.cms),
  updated 6 December 2023 09:44 IST, opening paragraph reports Nungambakkam 53 cm and
  Meenambakkam 52 cm between December 2 and 4. These are **reported station totals**
  (530 and 520 mm by unit conversion), not ward observations or a city spatial mean.
  Exact gauge cutoffs are absent. Do not use the article's loosely specified “Chennai”
  aggregate as a defined spatial statistic. These multiday station totals also exceed
  the model's 500 mm / 24 h input domain: do not clamp, split arbitrarily or call them
  a three-hour scenario. Need a supported matching interval from IMD.
- **FLOOD01:** [India Today report](https://www.indiatoday.in/cities/chennai/story/cyclone-michaung-chennai-floods-power-cut-waterlogging-tamil-nadu-2472731-2023-12-06),
  published 6 December 2023 17:41 IST / updated 19:07 IST, names Velachery and Tambaram
  inundation, Kolathur shop-owner testimony and relief boat deployment to Perumbakkam
  and Varadarajapuram. Staging records distinguish direct reporting, attributed testimony
  and indirect relief evidence. Exact locations, onset times and ward mappings are missing.
  Power cuts, camp attendance or food distribution alone do not establish a flood label.
- **SAT01:** [NRSC Bhuvan Disaster Services](https://bhuvan-app1.nrsc.gov.in/disaster/disaster.php?id=flood)
  interface opened. No December 2023 product/acquisition footprint was exposed in fetched
  content. A generic Tamil Nadu flood-recession legend is NOT proof of a 2023 product.
  Existing documented product discovery remains blocked; no extent was downloaded or
  intersected and no raw Sentinel-1 processing started.

Access limitations: all four web searches returned no results. RSMC New Delhi homepage
returned 403, Reuters' linked 4 December article returned 401, UNOSAT catalogue and an
attempted ReliefWeb event page returned no inspectable body; ReliefWeb API query returned
410. These failures are not evidence of absence of products. Wikipedia's Michaung page
was used only to discover news links; no labels/rainfall facts were accepted from it.
IMD Chennai's live page and previous-day archive were inspected: they expose current
weather and Day 1–4 links, not verified December 2023 observations. ISRO's current home
page was inspected without finding an event product. No guessed product URL is cited as evidence.

## Promotion rule (proposal, not yet an approved labelling protocol)

`candidate_observations.csv` is NOT evaluator input. Blank mapping fields deliberately
mean unresolved. `labels_reviewed.csv` has the evaluator header and **zero data rows**.
`event_metadata_INCOMPLETE.json` is deliberately rejected by the evaluator as a template.

Proposed event definition: “at least one credibly observed flooded site inside this
verified ward during the agreed observation window.” This is **any observed local
flooding**, not “whole ward inundated,” and it is biased toward reported locations.
Before promoting a point: obtain exact address/coordinates with positional uncertainty,
verify inside John's frozen polygon (not just a locality centroid), confirm time and
source, resolve boundary-edge ambiguity, record official number → internal ID crosswalk
and reviewer approval. An uncertainty footprint crossing wards stays pending.

No spatial area threshold has been adopted and no intersections were computed. For a
future documented flood mask, agree an area-based rule *before* inspecting rankings:
specify permanent-water removal, valid observation footprint, minimum mapped patch,
intersection area/ward-area denominator and threshold, image time/resolution/error and
sensitivity checks. Never silently substitute any nonzero sliver as the threshold.
Do not mix any-site news labels with area-threshold labels without recording separate
protocols. Not detected by SAR is not automatically non_flooded (urban radar limitations,
timing and occlusion matter). Confirmed non_flooded requires explicit observed coverage
and non-flooding under the chosen protocol/window. All other wards remain unknown.

## Exact handoff / blocked inputs

John must supply:
1. Frozen nonempty boundary file actually used by predictions, SHA-256, CRS, source,
   extraction date, legal vintage and justification of applicability in December 2023.
2. Reviewed crosswalk containing internal ward_id, official ward_number, boundary version,
   source relation/feature ID and polygon identity; resolve duplicates/missing numbers.
   Do not regenerate internal IDs between feature building and evaluation.
3. Feature artifact/version/provenance and prediction CSV for the full intended universe,
   model identifier/revision, original-feature scenario settings, generation command and
   matching event_id/boundary_version. Confirm duration actually reaches the scorer.
4. Review choice of rainfall interval and spatial scenario: obtain station IDs, station
   coordinates, accumulation start/end and time zone, observed totals and IMD provenance.
   A uniform station-based forcing is an explicitly hypothetical scenario, not measured
   rainfall for every ward; record that limitation in metadata.

Evidence collection still needs exact sites and independent corroboration for staged
locations, a reviewed official boundary vintage, dated satellite-derived extent plus
quality/coverage metadata or official location reports, and explicitly observed negatives.
These are evidence-review tasks, not a request to silently synthesize data upstream.

## What can honestly be demonstrated tomorrow

- Explain the model formula, input validation, metre-based geography and scenario behavior
  using clearly marked artificial fixtures; show the previously verified test results.
- Open the linked official boundary/report routes and the two inspected news sources;
  show why candidate flooding locations do not yet map to administrative prediction IDs.
- Show header-only reviewed labels and incomplete metadata as an explicit **unavailable
  historical evaluation**, not as zero accuracy or successful validation.
- Once John delivers frozen boundaries/predictions, demonstrate the review workflow and
  deterministic top-k/unknown-coverage handling. Do not promise completion of historical
  evaluation, representative accuracy, depth prediction or peak-time validation tomorrow.
