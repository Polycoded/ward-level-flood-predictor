# 2021 temporal comparison — feasibility report

## Nominal compatibility

| Property | 2021-11-04 | 2021-11-16 | Compatible? |
|---|---|---|---|
| Platform | Sentinel-1A | Sentinel-1A | yes |
| Product | GRD_HD | GRD_HD | yes |
| Direction | DESCENDING | DESCENDING | yes |
| Relative orbit | 92 | 92 | yes |
| Polarisation | VV+VH | VV+VH | yes |
| Separation | — | 12 days | same track, but not a same-day pair |

Each 2021 date needs two adjacent frames to cover the pilot bbox. Metadata footprint union coverage for the 11-04 pair is **0.9998** of the bbox. The same two-frame structure exists for 11-16.

## What could not be done

- No products were downloaded (ASF HTTP 403; no Earthdata/CDSE credentials).
- No SNAP/pyroSAR toolchain is installed.
- Therefore no common grid, no VV/VH differences, no valid-common-observation mask, and no change-detection layers were produced.

## Confounders that must be assessed when data are available

- Acquisition geometry and incidence-angle differences.
- Urban double-bounce, layover, shadow and metal roofs.
- Vegetation and surface moisture changes.
- Speckle and co-registration error.
- Permanent water versus temporary inundation.
- Timing relative to the actual rainfall/flood peak.

No binary flood mask or ward-level label should be created from this pilot.
