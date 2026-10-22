# Implemented model assumptions and evidence limits

This document describes the current implementation, not calibrated hydrology. See
model/risk_engine.py, docs/model_logic.md, docs/geographic_modules.md and
docs/historical_evidence.md. No coefficients or evaluator logic changed in this research task.

- Risk is an uncalibrated [0,1] index. Elevation/slope/impervious/proximity/road/underpass
  weights are respectively 0.25/0.15/0.25/0.15/0.10/0.10. Normalization spans are
  0–50 m elevation (inverted), 0–15 degrees slope (inverted), 0–1 impervious,
  0–5000 m water distance (inverted), 0–20 km/km² roads; any positive underpass count
  activates the full underpass component. These are design choices, not estimated effects.
- Original impervious fraction is multiplied once by (1 + relative increase/100), capped
  at one. All callers must pass original measurements. Water/vegetation fractions and
  pipeline flood_prone_index are not scoring inputs. No missing scored input is imputed.
- Rainfall is accumulation, not mm/h. Multiplier is min((mm/200) *
  clip(sqrt(3/duration_hours), 0.5, 1.5), 1.5). Three hours is the compatibility default,
  not an inferred event duration. Input domain is 0–500 mm and 1–24 h. No arbitrary
  truncation of real multiday totals to fit this domain is justified.
- Risk bins use boundaries .2/.35/.55/.75; 1 belongs to very_high. These are ordinal
  display bins, not validated warnings or probabilities. Legacy depth/timing mappings
  remain compatibility proxies, not observed/physical predictions.
- DEM horizontal and vertical units must be metres before slope calculation; slopes are
  degrees. Source scale/offset, datum and coverage require verification. Missing cells
  and affected derivative neighbours remain nodata; ward aggregates need coverage counts.
- Water distance is projected ward-centroid-to-nearest-water-geometry distance, not
  hydraulic connectivity, street accessibility or distance from every resident. Chennai
  default is EPSG:32644; CRS labels alone do not verify source coordinates or projection
  suitability. Missing target coverage yields unavailable distances.
- No tides, drainage capacities, sewer routing, antecedent saturation or storm time
  series are modelled. Ward means hide local detail. Synthetic pipeline fallback data
  must not be presented as real terrain/observations.
- December 2023 news station totals are not spatial ward rainfall. Exact gauge cutoffs,
  applicable interval and station-to-city scenario assumption remain unresolved. No
  rainfall amount/duration has been approved in the draft metadata.
- Internal pipeline ward_id is generated after sorting text ward_number; equality to
  official numbers must never be assumed. Local ward polygons are currently empty;
  John's exact frozen version/crosswalk is required before historical alignment.
- Staged neighbourhood reports are pending, not labels. Any-site flooding would not mean
  the entire ward was submerged. No adopted spatial threshold or confirmed negatives
  exist in this evidence pack. Omission from reporting is unknown.
- Top-k selection occurs on the full prediction universe; observed-sample recall/FPR
  and incomplete precision cannot establish city-wide accuracy. Biased news coverage,
  event timing, satellite detection limits and independent sampling must be disclosed.

## Critical assets and shelters (`pipeline/extract_assets.py`), owner Ronit

- **Source**: OpenStreetMap via Overpass, bounding box 12.8–13.3 N, 80.0–80.35 E. OSM coverage of Chennai is good for hospitals and schools but incomplete for pumping stations and substations, so counts are lower bounds.
- **Ward assignment**: an asset belongs to the ward polygon that contains its point (or its centroid, for buildings). Assets outside every ward are dropped (948 of 2,978 in the October 2026 run, mostly outside GCC limits).
- **Shelter candidates** are *named* schools, colleges, universities, community centres and emergency assembly points. Unnamed ones stay in `assets.parquet` but are not offered as shelters, because a shelter you can't name can't be announced.
- **Capacities are planning estimates, not surveyed numbers**: school 300, college 500, university 800, community centre 200, assembly point 150 people. Replace them with Corporation relief-centre data when available.
- **Walking time** comes from the API (`model/shelters.py`). Until OSRM routing is wired, the route is a straight line and the UI labels it "straight-line estimate".
- The script never falls back to synthetic data. If OSM is unreachable it fails rather than ship invented infrastructure.

## Dashboard (`web/`), owner Ronit

- **Rainfall** is one total for the whole city over the chosen duration (1–24 h, at most 500 mm, the API limits). The live option sums Open-Meteo hourly precipitation at the GCC centroid for the next 6, 12 or 24 h. That matches how IMD issues city-level forecasts, but ignores spatial variation in rainfall.
- **CSV uploads** are treated as hourly totals in mm; the sum is used as the event total.
- **Scenario delta** ("N wards move up a risk level") compares the selected built-up scenario with today's land use at the same rainfall.
- **Mock mode** uses a synthetic 20×10 grid over Chennai, not real wards, and is labelled **Mock data** in the header. It exists for offline demos and automated tests only.
