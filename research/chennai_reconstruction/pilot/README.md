# Chennai Sentinel-1 technical pilot (2015 and 2021)

Status: **BLOCKED before download**. Metadata verified; no SAR products downloaded; no
processing executed; no flood labels generated.

## Approved products (5 products across 3 dates)

| Date | Role | Scene |
|---|---|---|
| 2015-12-06 | single | `S1A_IW_GRDH_1SDV_20151206T003120_20151206T003149_008914_00CC1F_BEF9` |
| 2021-11-04 | north | `S1A_IW_GRDH_1SDV_20211104T003147_20211104T003212_040414_04CA78_AD56` |
| 2021-11-04 | south | `S1A_IW_GRDH_1SDV_20211104T003212_20211104T003237_040414_04CA78_20F6` |
| 2021-11-16 | north | `S1A_IW_GRDH_1SDV_20211116T003147_20211116T003212_040589_04D094_DB41` |
| 2021-11-16 | south | `S1A_IW_GRDH_1SDV_20211116T003212_20211116T003237_040589_04D094_B07B` |

All are Sentinel-1A, descending relative orbit 92, VV+VH, GRD-HD. The two 2021 frames
are required to cover the pilot bbox. Expected raw storage is 4,758.7 MB (~4.65 GiB).

## Why blocked

- ASF product download returns HTTP 403 without an approved Earthdata login.
- No SNAP `gpt`/`snappy`, `pyroSAR` or `sarpy` toolchain is installed.
- Authoritative 2011/2018 GIS is unavailable; the 2022 KML was not substituted.

## Run

```bash
.venv\Scripts\python.exe research/chennai_reconstruction/pilot/run_pilot.py preflight \
  --config research/chennai_reconstruction/pilot/processing_parameters.yaml
```

This writes metadata/quality/coverage reports, the preflight report, and metadata
footprint figures. Download is gated by `--approve-download` and requires credentials;
processing fails loudly until a reviewed toolchain/parameters exist.

See `preflight_report.md`, `limitations.md`, `reproducibility.md`, and `figures/README.md`.
