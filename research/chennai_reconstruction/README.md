# Chennai geospatial reconstruction pack

Investigation and planning artifacts for rebuilding a defensible ward-level historical
flood-susceptibility dataset. No production code, API contract or model was changed; no
SAR imagery was downloaded.

**Read the full report:** [`docs/geospatial_reconstruction_plan.md`](../../docs/geospatial_reconstruction_plan.md)

## Contents

| File | Purpose |
|---|---|
| `source_register.csv` | Source-by-source access, coverage, licence status and verification |
| `boundary_version_audit.csv` | 2008/2011/2022 KML audit, hashes, overlaps and version comparison |
| `sentinel1_inventory.csv` | ASF Sentinel-1 GRD-HD metadata for 2015/2021/2023 search windows |
| `feature_availability_matrix.csv` | Feature-by-event availability and reconstruction recommendation |
| `schema.sql` | Proposed PostGIS/relational schema for boundaries, scenes, labels, features |
| `ward_event_labels_template.csv` | Header-only ward-event label dataframe template |
| `implementation_plan.csv` | Phased plan with effort estimates and dependencies |
| `unresolved_risks.csv` | Prioritised risks and mitigations |
| `pilot/` | Sentinel-1 technical pilot (metadata verified; download/processing blocked) |

## Key findings

- The local 2022 KML is byte-identical to the OpenCity 2022 KML; OpenCity reports
  **License not specified**. It is not the legal boundary.
- The authoritative legal evidence found is the **2018 gazette** (200 wards, 14 Dec 2018).
  The 2022 gazette is a **reservation**, not a new delimitation.
- The 2022 200-ward KML and the 2011 200-ward KML are materially different (best-match
  IoU median 0.829; 14 wards < 0.5). Existing 2005/2015 labels are joined to 2022
  geometry, mixing boundary vintages.
- The 2022 KML has 9 invalid polygons and 290 pairs > 1 m²; the repaired layer has 291.
  Overlaps are sliver-dominated; 31 involve invalid source polygons. Do not repair or
  reassign area without the official GIS/gazette.
- Sentinel-1 coverage:
  - 2015: post-event **2015-12-06**.
  - 2021: pre **2021-11-04**, post **2021-11-16**; no peak acquisition.
  - 2023: last pre **2023-11-30**, next **2024-01-17**; **no December 2023 acquisition**,
    so Sentinel-1 cannot map the Michaung peak.
- Only descending orbit 92 (VV+VH) was returned; no ascending GRD-HD over the bbox.
- GEE has Sentinel-1 from 2014-10-03 and is free for eligible noncommercial research;
  commercial use requires a paid plan. GEE does not fill the 2023 acquisition gap.

## Next gate

Review the plan, approve the boundary-version strategy and label protocol, and obtain
official 2018/2011/2005 boundary records plus written reuse terms **before** downloading
SAR or generating labels.
