# Sentinel-1 Chennai pilot — preflight report

Date: 2026-10-30. Scope: 2015-12-06 and the 2021-11-04/11-16 pair.
This report was produced **before** any approved SAR download.

## Approved dates and products

| Event date | Role | Scene | Platform / orbit | Direction | Polarisation | Size MB |
|---|---|---|---|---|---|---:|
| 2015-12-06 | single | `S1A_IW_GRDH_1SDV_20151206T003120_20151206T003149_008914_00CC1F_BEF9` | Sentinel-1A / 92 | DESCENDING | VV+VH | 1097.2 |

| 2021-11-04 | north | `S1A_IW_GRDH_1SDV_20211104T003147_20211104T003212_040414_04CA78_AD56` | Sentinel-1A / 92 | DESCENDING | VV+VH | 905.2 |

| 2021-11-04 | south | `S1A_IW_GRDH_1SDV_20211104T003212_20211104T003237_040414_04CA78_20F6` | Sentinel-1A / 92 | DESCENDING | VV+VH | 926.5 |

| 2021-11-16 | north | `S1A_IW_GRDH_1SDV_20211116T003147_20211116T003212_040589_04D094_DB41` | Sentinel-1A / 92 | DESCENDING | VV+VH | 906.6 |

| 2021-11-16 | south | `S1A_IW_GRDH_1SDV_20211116T003212_20211116T003237_040589_04D094_B07B` | Sentinel-1A / 92 | DESCENDING | VV+VH | 923.2 |

Approved products: **5** (3 acquisition dates; the 2021 dates require two adjacent frames to cover the bbox).
Expected raw storage if all approved products are downloaded: **4758.7 MB (~4.65 GiB)**.

## Metadata verification

All approved scene IDs were queried from the public ASF search API and matched against the expected platform, direction, relative orbit, polarisation and product type. Full metadata is in `scene_metadata.csv`.

| Check | Result |
|---|---|
| Scene IDs returned by ASF | PASS |
| Platform / direction / orbit / polarisation / product type | PASS |
| Footprints intersect the pilot bbox | PASS |
| 2015 full-bbox footprint | PASS |
| 2021 two-frame coverage (north + south) | PARTIAL (99.98% metadata; not valid pixels) |

## Access and toolchain

- ASF search API: public; working. A product download HEAD request returned HTTP 403; no Earthdata credentials are present in this environment.
- ASF product download: **BLOCKED** in this environment. A HEAD request to the approved 2015 product returned HTTP 403; no Earthdata credentials are present.
- Toolchain: **BLOCKED**. gpt=None, esa_snappy=False, snappy=False, pyroSAR=False, sarpy=False.

## Boundary geometry

| Event | Required boundary | Status |
|---|---|---|
| 2015 | 2011 GCC boundary | **BLOCKED** — no authoritative 2011 GIS; OpenCity 2011 KML is provisional and licence-unspecified |
| 2021 | 2018 GCC boundary (2018 gazette) | **BLOCKED** — gazette PDF only; no authoritative GIS under confirmed terms |

The 2022 KML was **not** substituted for 2015 or 2021 ward calculations.

## Decision

Do not download the approved products yet. The pilot can verify acquisition metadata and bbox footprint coverage, but cannot produce backscatter, quality masks, temporal change layers or ward-level coverage without access and authoritative boundaries. This is a stop condition, not a workaround.

## Status

| Item | Status |
|---|---|
| Scene metadata verification | PASS |
| Bbox footprint coverage | PASS |
| Product download | BLOCKED |
| SAR preprocessing | BLOCKED |
| Valid-pixel quality assessment | BLOCKED |
| 2021 temporal comparison | BLOCKED |
| Ward-level coverage / labels | BLOCKED |
| VV/VH figures | BLOCKED (not produced) |
