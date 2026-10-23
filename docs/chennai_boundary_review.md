# Chennai 200-ward boundary review

Reviewed 2026-10-23 at local mit-dev 6210aba. Read-only input review; no geometry,
crosswalk, model, pipeline, API, UI or metrics changed. This is a conditional input
review, not geographic certification or historical validation.

## Verified snapshot

- 200 nonempty valid ward polygons in declared EPSG:32644; 200 unique internal IDs
  and official numbers. Official numbers cover exactly 1–200. Projected coordinates
  transform to approximately 80.1341–80.3315 E, 12.8521–13.2350 N; this is a plausibility
  check, not independent CRS verification.
- CSV has 200 matching internal-ID/official-number pairs. Internal ID 1 is official
  ward 168. Never join observations using equality between those two fields.
- Crosswalk zone labels match GeoJSON ZONE values in current row order. There are
  15 distinct zone labels (including nonuniform label `ZONE - IV`), not the 16 zones
  described in the commit message. Ward names are generic `Ward N` identifiers.
- Stored area_sqkm exactly matches geometry area / 1e6 in the local environment.
- Ward SHA-256: `475e65d9c9f7844fee387429f6f891c1a9be4f22a70cd3a0b964c075a68171ab`.
- Crosswalk SHA-256: `d28caa4ed0c609ee4cfdcffc63684d7fa32724b72f91c28a7fb9b2b1cfacdd22`.

## Topology requiring review

Individual validity does not establish a nonoverlapping ward partition. Pairwise
intersections in the declared metre CRS found 291 unordered ward pairs with area
strictly greater than 1 m2. The 1 m2 cutoff is diagnostic, not an acceptance standard.
Sum of polygon areas is 431.972356 km2; union area is 431.865151 km2. Their difference
is 107,205.54 m2 (excess summed area; not necessarily unique overlap footprint).

Largest intersections, using OFFICIAL ward numbers:

| Wards | Intersection m2 |
|---|---:|
| 32 / 31 | 7,894.628 |
| 190 / 191 | 6,993.276 |
| 117 / 133 | 3,886.456 |
| 94 / 83 | 3,884.690 |
| 5 / 4 | 3,041.801 |

The union is one polygon containing 2,041 interior rings, totaling 6.016903 km2;
the largest is 5.917260 km2. These are geometric holes, not proven missing wards:
water exclusions, administrative exclusions and digitization gaps must be distinguished
against the original source and an independent jurisdiction boundary. No repairs,
area-based rejection threshold or arbitrary ownership of overlapping cells is justified yet.
Point assignment in overlaps and independent ward clipping can create ambiguous IDs or
double-counting; pipeline processing must document its treatment.

## Source evidence and limits

The crosswalk's `chennai_gcc_kml_2022` value is a source label, not a traceable
conversion record. No KML/KMZ was found by the repository file inventory. The tracked
pipeline/download_wards.py uses Overpass, so it does not reproduce this KML conversion.

Live search located the OpenCity catalogue resource named Chennai GCC Ward Map - 2022:
https://data.opencity.in/dataset/gcc-ward-information/resource/e90176d4-319a-45bd-918e-ecce4f048c4d
Search metadata attributes the source to Chennai Corporation, credits Vaidyanathan R,
and lists November 25, 2025 as the resource update date. Direct page opening returned
403; the KML bytes were not downloaded or compared. The title year alone does not
establish applicability to December 2023 or an official publication chain.

Official GCC page inspected:
https://chennaicorporation.gov.in/gcc/delimited_ward/
It provides ward/gazette routes and states gazette notification is final where there
are discrepancies. No ward-by-ward gazette comparison was completed in this review.
Keep source authenticity, conversion fidelity and historical applicability pending.

## Local feature inventory and readiness

features.parquet and zonal_stats.parquet are absent from data/processed. No TIFF,
Parquet or KML/KMZ was returned by the repository file inventory (not a whole-disk scan).
Existing projected vector layers are readable: roads 123,721 records, water 2,083,
underpasses 706; all declare EPSG:32644. Their extents span the ward extent, but this
does not prove complete or contemporaneous coverage or correct feature semantics.
No spatial completeness/source audit of these layers was performed.

pipeline/build_features.py still creates missing numeric columns as zeros and coerces
invalid/null measurements with fillna(0). Current outputs cannot be accepted solely
because they contain finite numbers. Reviewed upstream missingness is required.

Existing readiness CLI exited 1: boundary records 200, features unavailable, reviewed
boundary version/identity attestation absent, historical evidence unassessed, explicit
mock metrics unsuitable for accuracy claims. Do not add invented attestations to get
an exit 0. No model changes were made; model/API tests were not rerun for this review.

## Next delivery needed from John

1. Original ward and zone KML files, exact download URLs, retrieval dates, source hashes,
   conversion command/script and explanation of any repairs; confirm historical vintage.
2. Compare the largest overlaps and largest interior hole to those sources. Preserve
   canonical polygons until source review determines whether any correction is warranted.
3. Supply original 200-ward features.parquet plus CSV export tied to the boundary hash
   and official-number crosswalk. Regenerate if they are still 15-zone aggregates.
4. For each of the six scored measurements, provide source/version/date, units, CRS,
   extraction/aggregation method, nodata/coverage audit and treatment of overlap areas.
   Preserve unavailable values; do not fabricate zero measurements.

Mit can then review the six-feature artifact and establish a frozen input snapshot.
Historical rainfall and ward-aligned observations remain a separate pending review.
Do not run or publish historical accuracy from current placeholders.

## Reusable diagnostic

input_readiness now reports all positive-area overlap pairs with zero-based row positions
and internal ward IDs. It applies no area tolerance and reports no area units. Boundary
touching is allowed. Invalid/missing/empty geometry skips overlap assessment. Findings
are review warnings; existing readiness gates are unchanged. Use the original source
to interpret slivers; this diagnostic cannot certify a ward partition or detect gaps.
