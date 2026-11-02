# Chennai geospatial data reconstruction plan

Status: **investigation and plan only**. No production code, API contract, model or canonical
dataset was changed. No SAR imagery was downloaded. The only downloads were small official
PDFs/KMLs used to verify what exists (gazette PDFs, 2011/2008 KMLs, OpenCity 2022 KML).
All files for this plan live under `research/chennai_reconstruction/`.

## 1. Bottom line

The current 200-ward layer (`data/processed/wards.geojson`) is a repaired version of the
OpenCity "Chennai GCC Ward Map - 2022" KML. That KML is **byte-identical** to the tracked
`data/raw/Chennai GCC Ward Map - 2022.kml` (SHA-256 `BE48...C347E0`). Its licence is
**"License not specified"** (verified through the OpenCity CKAN API). It is a derived map,
not the legal boundary.

The legal boundary evidence found is:

- **2018 gazette** (Tamil Nadu Gazette No. 408, 14 Dec 2018): delimitation of Chennai
  Corporation into **200 wards**, with boundary descriptions. This is the authoritative
  delimitation for 2018 onward.
- **2022 gazette** (Tamil Nadu Gazette No. 46, 17 Jan 2022): reservation of the 200 wards
  for SC/ST/Women. It is **not** a new boundary delimitation.
- **2011 and 2008 KML maps** from OpenCity: provisional 200-ward and 155-ward layers.
  The 2018 gazette supersedes earlier delimitations, so the 2015 event should not be
  labelled on the 2018/2022 geometry.

**Major finding:** the 2022 200-ward KML and the 2011 200-ward KML are materially
different. Best spatial matching gives an IoU median of **0.829**, minimum **0.183**,
with **14 wards below 0.5**. The 2022 KML is a derived map and cannot be assumed to
encode the 2018 legal geometry; the 2022 gazette only reserves the 2018 wards. The
existing 2005/2015 labels
were joined to the 2022 geometry, so they mix boundary vintages. This is a scientific
validity defect independent of model choice.

**Overlap finding:** the 2022 KML has **9 invalid polygons** and **290 pairs > 1 m²**; the
repaired processed layer has **291**. The overlaps are sliver-dominated (median compactness
0.00106; 90th percentile 0.00864), not whole-ward double assignment. **31 overlaps involve
the 9 invalid source polygons** (about 10,120 m²). The 2011 layer has 37 pairs > 1 m²
(202 m²); the 2008 layer has none > 1 m². The overlaps are consistent with digitisation/
topology errors and a version change, not with a deliberate legal overlap. They cannot be
resolved without the authoritative GIS/gazette.

**Sentinel-1 finding:** Sentinel-1 exists for all three event periods, but event-time
coverage is uneven:

- 2015: 7 dates; post-event **2015-12-06** (3 days after the candidate 1–3 Dec
  peak, to be confirmed against IMD/TNSDMA) is usable.
- 2021: 9 dates; **2021-11-04** pre and **2021-11-16** post; no acquisition at the peak.
- 2023: **no Sentinel-1 acquisition between 2023-11-30 and 2024-01-17**. The Michaung
  flood peak (early December 2023) is therefore **not observable by Sentinel-1**; only
  a pre-event scene and a far post-event scene exist.

No ascending GRD-HD scenes were returned over the Chennai bbox; only descending relative
orbit 92. That matters for urban layover/shadow and should be documented in any SAR study.

## 2. Ward geometry investigation

### 2.1 Authoritative source

| Source | What it establishes | Verification |
|---|---|---|
| [GCC Ward Maps / Delimitation](https://chennaicorporation.gov.in/gcc/delimited_ward/) | Official route; page states gazette notification is final | Page inspected |
| [2018 gazette PDF](https://chennaicorporation.gov.in/gcc/delimited_ward/pdf/2018_delimitation.pdf) | Delimitation into **200 wards**; boundary descriptions; dated 2018-12-14 | First pages text-extracted |
| [2022 gazette PDF](https://chennaicorporation.gov.in/gcc/delimited_ward/pdf/46_Ex_VI_2.pdf-for-Author.pdf) | Reservation of 200 wards; dated 2022-01-17 | First pages text-extracted |
| OpenCity 2022 KML | 200-feature derived map; **licence not specified** | CKAN metadata; hash comparison |
| OpenCity 2011 KML | 200 wards (plus zone feature), provisional | Geometry audit |
| OpenCity 2008 KML | 155 wards, provisional | Geometry audit |

The 2018 gazette is the recommended **legal** reference for 2018/2021/2023. The 2022
gazette confirms the ward count/reservation, not a new geometry. The GCC page notes that
the gazette is final in case of discrepancies; it does not provide a downloadable GIS
layer in the inspected page.

**Licensing:** OpenCity explicitly reports `license_id = notspecified`; this is not an
open licence. The gazette PDFs carry no explicit open-data licence on the page. Written
reuse permission or a formal government open-data licence must be obtained before
redistributing derived geometry. OSM (ODbL 1.0) is a possible non-authoritative alternative
for comparison, not a legal replacement.

### 2.2 Current layer and version comparison

| Layer | Features | Valid | Area km² | Pairs > 1 m² | Overlap sum m² | Source |
|---|---:|---:|---:|---:|---:|---|
| 2008 KML | 155 | 155 | 173.532 | 0 | 0.7 (all ≤1 m²) | OpenCity |
| 2011 KML (wards only) | 200 | 200 | 428.605 | 37 | 202.0 | OpenCity |
| 2022 KML raw | 200 | 191 | 431.972 | 290 | 107,089.0 | OpenCity |
| 2022 processed `wards.geojson` | 200 | 200 | 431.972 | 291 | 107,202.3 | repaired local layer |

Current hashes:

- KML (local = OpenCity): `BE48EF7EB4320279E790F59DA1691ECE9EFC92B34459CA73C492957943C347E0`
- Processed wards: `AA89D45F16FA4724F82115D09696AF7C1E6C5F6FF4C1C3AFCEDEE01DDF0C345A`
- Crosswalk: `C889D08ED41F9415310130C602EAADDDF39450FD84BBCA0C5431DB6C53E6F08B`
- 2011 KML: `4EC2D505557DD6B46764D6A834EEDE1CB533C1807E54A2A001437F1819FD6814`
- 2008 KML: `7D94FB8A53EC6E22E39F526131738160CE93C15CE53D47492F3415999D143196`

2022-vs-2011 best-match geometry: median IoU 0.829, min 0.183, 14 wards < 0.5,
21 wards > 0.95. This is not a renumbering-only change. Using 2022 wards for 2015 labels
is a **boundary-version mismatch**, even if the labels were otherwise correct. The
comparison used `make_valid` on copies only for diagnostic intersections; no production
geometry was repaired.

### 2.3 Overlap interpretation

- The 2022 raw KML has invalid wards **39, 42, 65, 69, 91, 115, 129, 161, 183**.
- 31 of the 291 processed substantial overlaps involve those invalid polygons (10,119.6 m²).
- Median overlap compactness is 0.00106; the 90th percentile is 0.00864. Compactness near
  zero indicates a long thin sliver along a shared boundary, not a whole ward.
- The largest overlaps are 7,894.6 m² (official 32/31) and 6,993.3 m² (190/191); these are
  still only 0.32% and 0.23% of the smaller ward's area.
- The 2008 layer has no overlap > 1 m²; the 2011 layer has 37. Topology quality degraded
  in the later derived layer.

**Recommendation:** do not replace the current geometry and do not silently repair it.
Create a versioned boundary registry. Obtain the official 2018 GIS/shapefile (or digitise
from the gazette with control points and review), compare it with the OpenCity 2022 KML,
and publish a versioned crosswalk. For labels, assign boundary-edge-ambiguous area to
`unknown` or test explicit overlap policies; never transfer area arbitrarily.

## 3. Sentinel-1 acquisition inventory

Queries: ASF Search API and Copernicus Data Space catalogue, bbox
`80.10,12.80,80.35,13.25`, product `GRD_HD` unless stated. Only metadata was queried;
no imagery was downloaded. Full rows: `research/chennai_reconstruction/sentinel1_inventory.csv`.

| Event | Unique dates | Platform / track | Polarisation | Event-time assessment |
|---|---|---|---|---|
| 2015 | 2015-11-12, 11-24, **12-06**, 12-18, 12-30; 2016-01-11, 01-23 | S1A, descending orbit 92 | VV+VH | 12-06 is 3 days after the candidate 1-3 Dec peak; Nov 24 is pre-event |
| 2021 | 2021-10-23, **11-04**, **11-16**, 11-28, 12-10, 12-22; 2022-01-03, 01-15, 01-27 | S1A, descending orbit 92 | VV+VH | 11-04 pre, 11-16 post; no peak acquisition; December scenes are later |
| 2023 | 2023-11-06, 11-18, **11-30**; **2024-01-17**, 01-29, 02-10, 02-22 | S1A, descending orbit 92 | VV+VH | No Dec 2023/early Jan acquisition; 11-30 pre, 01-17 far post (about 43 days after the 3–5 Dec peak) |

Notes:

- **No ascending GRD-HD** was returned over the bbox for these windows. The actual Chennai
  coverage is one descending track, not a 6-day multi-track stack. The GEE catalogue's
  nominal 6-day revisit is a constellation capability, not a guarantee for this AOI.
- 2021/2023 rows include adjacent frames on the same date; deduplicate by acquisition date
  and merge frames before processing.
- Each GRD-HD product is about 0.88–1.64 GB; a 2015/2021/2023 stack is tractable but not
  trivial. Do not download until the review approves the AOI/dates.
- Scene coverage per ward must be computed from valid pixels; bbox intersection is not
  proof that every ward is fully observed.
- 2023 has **no Sentinel-1 peak-flood observation**. A Sentinel-1-only 2023 label must be
  `unknown` for peak inundation, or use a far-post/recession change analysis clearly
  labelled as such. Complementary SAR/optical sources must be investigated separately;
  availability is not assumed here.

### 3.1 Access and GEE

- **ASF DAAC** (NASA): free Sentinel-1 archive and metadata API; downloads require an
  Earthdata login. No paid runtime.
- **Copernicus Data Space Ecosystem**: free Sentinel-1 catalogue/access under Copernicus
  terms; account/OAuth and download/processing costs. The catalogue independently confirmed
  the 2023 gap (2023-11-30 and 2024-01-17 only in the Dec–Jan window).
- **Google Earth Engine**: `COPERNICUS/S1_GRD` is available from **2014-10-03**, with
  10/25/40 m products, VV/VH, and a nominal 6-day revisit. GEE is **free for eligible
  noncommercial/research users**; commercial use requires a paid Earth Engine plan.
  GEE does not create missing acquisitions: the 2023 gap remains. Cloud export/storage may
  incur Google Cloud charges. No paid runtime is required for noncommercial research, but
  eligibility and terms must be confirmed before use.

## 4. Label reconstruction design

### 4.1 Schema

The required fields are implemented in the proposed `ward_event_labels` table
(`research/chennai_reconstruction/schema.sql`), with additional evidence/coverage fields:

| Field | Meaning |
|---|---|
| `ward_id` | Stable internal ID within a boundary version |
| `boundary_version` | Boundary vintage (e.g. `gcc_2011`, `gcc_2018`) |
| `event_id` | Event identifier |
| `inundated_area_m2` | Flood-mask area intersecting the ward, permanent water removed |
| `ward_area_m2` | Ward area for that boundary version |
| `inundated_fraction` | `inundated_area_m2 / ward_area_m2` |
| `observed_area_m2` | Ward area with valid SAR pixels in the observation window |
| `inundated_fraction_observed` | `inundated_area_m2 / observed_area_m2` |
| `observation_start`, `observation_end` | Acquisition/observation window, UTC |
| `observation_coverage` | `observed_area_m2 / ward_area_m2` |
| `label` | `positive`, `negative`, `unknown` |
| `confidence` | `high`, `medium`, `low` |
| `source` | Source/protocol/scene identifiers |
| `uncertainty_reason` | Required for `unknown`; optional otherwise |
| `scene_ids` | Pre/post/supporting scene IDs |
| `negative_support_ref` | Required for `negative` |
| `protocol_version` | Frozen labelling rules |
| `review_status`, `reviewer` | Human review trail |

### 4.2 Three-state rules

- **Positive**: supported inundation evidence within the observation window. The flood
  mask must survive permanent-water removal, minimum-patch and minimum-fraction rules; the
  ward must have adequate valid coverage. Confidence depends on scene count, timing,
  independent corroboration and urban-signal clarity.
- **Negative**: **sufficiently observed and independently supported non-inundation**.
  Requires high valid coverage in the post-event scene, a pre-event comparison, no flood
  cluster above the pre-registered threshold, permanent-water exclusion, and at least one
  independent non-inundation evidence item (optical, official report, high-water mark, or
  field observation). A single SAR scene alone is not enough for a negative.
- **Unknown**: everything else, including missing/partial coverage, no post-event scene,
  peak-timing mismatch, ambiguous urban backscatter, boundary-edge overlap, or no
  independent support. **Missing detection is never converted to negative.**

Candidate threshold parameters (to be frozen before labels): minimum flood patch
(e.g. 0.1–0.5 ha), minimum fraction of ward (e.g. 1%), minimum valid coverage (e.g. 90%),
permanent-water mask, speckle filter, and threshold method. These are not adopted here;
they must be reviewed and sensitivity-tested.

### 4.3 Reconstruction workflow

1. Freeze event windows and boundary versions from official sources.
2. Preprocess approved GRD scenes (co-registration, speckle filtering, terrain/incidence
   handling) and build pre/post stacks.
3. Build permanent-water and valid-coverage masks.
4. Detect inundation with dual-pol/change thresholds; use Otsu/region growing and
   threshold sensitivity; remove urban artefacts and permanent water.
5. Intersect the mask with the **event-correct** ward boundary; compute areas and coverage.
6. Assign labels only under the frozen protocol; record evidence and uncertainty.
7. Independent review of a stratified sample and all positives; do not look at model
   rankings while labelling.
8. Save scene IDs, hashes, masks, coverage rasters, protocol version and reviewer trail.

## 5. Feature reconstruction

Existing features: elevation/slope (Copernicus DEM), impervious (WorldCover 2021),
water/roads/underpasses (OSM 2026). The matrix is in
`research/chennai_reconstruction/feature_availability_matrix.csv`.

### 5.1 Recommended for reconstruction

- **Static terrain (all events):** elevation mean and percentiles, slope, HAND, TWI,
  flow accumulation. Physically relevant to ponding, flow concentration and low-lying
  pockets. Derive from a hydrologically conditioned DEM; document DEM accuracy, sink
  filling, drainage network and urban-culvert limitations. HAND/TWI are more defensible
  than flow accumulation alone in flat urban terrain.
- **Impervious fraction (event-matched):** use ESA CCI 300 m / GHSL built-up / WorldCover
  2021 according to event. Do not use 2021 WorldCover as if it were 2005/2015. Document
  classification error and product definitions.
- **Coastline proximity (static):** coarse physical covariate; not a tide/surge model.
- **Distance/density to rivers and drainage channels:** retain only if a reviewed
  historical drainage network is obtained. Current OSM is a proxy, not a historical
  measurement.

### 5.2 Defer or reject

- **Road density and underpass count:** current OSM is not historical; underpass
  completeness is poor. Defer for 2005/2015 (and probably 2021/2023 unless historical
  OSM extracts are reviewed).
- **Soil permeability:** physically relevant but not in the current stack and licensing/
  spatial accuracy unresolved. Defer.
- **Tide/storm surge:** event-specific boundary condition, not a static susceptibility
  feature. Defer until a verified event series exists.
- **Population/building density:** exposure, not hazard. Do not mix into susceptibility
  ranking.
- **Rainfall:** event forcing, not a static predictor. Keep separate from the
  susceptibility model.

## 6. Proposed database

See `research/chennai_reconstruction/schema.sql` for DDL. Core tables:

- `boundary_versions` — legal/source status, effective dates, licence, geometry hash.
- `wards` — versioned ward polygons, official numbers, areas, validity.
- `crosswalk` — explicit version-to-version ward relations; no implicit name matching.
- `flood_events` — event windows, boundary version, metadata, review status.
- `scenes` — SAR/optical acquisition metadata, footprints, licences, hashes, coverage.
- `label_protocols` — frozen positive/negative/unknown rules and thresholds.
- `ward_event_labels` — the required schema fields plus coverage/evidence/confidence.
- `label_evidence` — source-by-source evidence with geometry/time/confidence.
- `feature_catalog`, `ward_event_features` — feature definitions, provenance, coverage.
- `boundary_overlaps` — overlap classification and resolution status.

Key constraints: positive requires area/source; negative requires coverage and
`negative_support_ref`; unknown requires `uncertainty_reason`; unique
`(ward_id, boundary_version, event_id)`; areas/fractions bounded.

## 7. Phased implementation plan

See `research/chennai_reconstruction/implementation_plan.csv`. Estimated **17–25
person-weeks**:

| Phase | Work | Effort |
|---|---|---:|
| 0 | Review/authorization; licences; freeze current | 1–2 wk |
| 1 | Authoritative boundary registry, crosswalks, overlap classification | 3–4 wk |
| 2 | Sentinel-1 acquisition/preprocessing and coverage | 3–4 wk |
| 3 | Ward-event labels, evidence review, negative protocol | 4–6 wk |
| 4 | Feature reconstruction and provenance | 3–4 wk |
| 5 | Locked spatial evaluation and sensitivity | 2–3 wk |
| 6 | Documentation, data card, release | 1–2 wk |

The plan is deliberately front-loaded on boundaries and labels. Model tuning is out of
scope.

## 8. Unresolved risks

See `research/chennai_reconstruction/unresolved_risks.csv`. Highest priority:

1. Official GIS/gazette reuse licence is unresolved; OpenCity is "not specified".
2. Boundary-version mismatch (2011 vs 2018; 2005 vs 2008) and missing crosswalks.
3. 2023 Sentinel-1 gap: no peak-flood observation.
4. Only descending track 92; urban radar layover/shadow.
5. Scarce independent negatives; missing detection is not dryness.
6. Historical land-cover/drainage features are not event-matched.
7. Overlaps and boundary-edge ambiguity can change labels/features.
8. GEE commercial-use terms and compute/storage costs.

## 9. Immediate next actions (before any download)

1. Review this plan; approve or reject the boundary-version strategy.
2. Request the official 2018 GIS/shapefile and 2011/2005 boundary records from GCC;
   request written reuse terms for OpenCity-derived layers.
3. Freeze event windows and the label protocol (positive/negative/unknown thresholds)
   **before** looking at SAR masks.
4. Confirm Sentinel-1 access route (ASF/CDSE vs GEE) and noncommercial eligibility.
5. Approve a small pilot: 2015 post-event (2015-12-06) and 2021 pre/post pair
   (2021-11-04/11-16), with a manual review sample, before citywide processing.

## 10. Supporting files

- `research/chennai_reconstruction/source_register.csv`
- `research/chennai_reconstruction/boundary_version_audit.csv`
- `research/chennai_reconstruction/sentinel1_inventory.csv`
- `research/chennai_reconstruction/feature_availability_matrix.csv`
- `research/chennai_reconstruction/schema.sql`
- `research/chennai_reconstruction/ward_event_labels_template.csv`
- `research/chennai_reconstruction/implementation_plan.csv`
- `research/chennai_reconstruction/unresolved_risks.csv`

### Pilot status (2026-10-30)

A technical Sentinel-1 pilot was implemented under `research/chennai_reconstruction/pilot/`.
It verified **five GRD-HD products across the three approved dates** (2015-12-06; two
adjacent frames on 2021-11-04 and 2021-11-16) against ASF metadata: Sentinel-1A,
descending orbit 92, VV+VH, GRD-HD. Expected raw storage is **4,758.7 MB (~4.65 GiB)**.

The pilot is **BLOCKED before download**:

- ASF product download returned HTTP 403; no Earthdata/CDSE credentials are present.
- No SNAP `gpt`/`snappy`, `pyroSAR` or `sarpy` toolchain is installed.
- Authoritative 2011 GIS (2015) and 2018 GIS (2021) are unavailable; the 2022 KML was
  not substituted.
- Therefore no VV/VH backscatter, valid-pixel masks, change layers or ward-level
  coverage were produced. Only metadata footprint figures exist.

See `research/chennai_reconstruction/pilot/preflight_report.md`,
`sentinel1_inventory.csv` and `research/chennai_reconstruction/pilot/limitations.md`.
This is a stop condition, not a workaround.

## 11. What was verified and what was not


**Verified in this phase:** GCC 2018 gazette text (200 wards, 2018-12-14); GCC 2022 gazette
text (reservation, 200 wards); OpenCity 2022 KML hash equality and "License not specified";
2008/2011/2022 KML feature counts and overlaps; 2011-vs-2022 geometry differences; ASF/CDSE
Sentinel-1 metadata and the 2023 acquisition gap; GEE S1 availability and noncommercial
terms; existing local geometry/feature hashes.

**Not verified:** official 2011/2005 gazette boundary geometry; exact legal applicability
of each KML to each event; per-scene valid-pixel coverage; SAR flood-mask accuracy; 2023
complementary SAR/optical availability; independent non-inundation evidence; historical
land-cover accuracy; reuse permission for GCC/OpenCity data.

No labels, imagery availability, event coverage or data quality were invented.
