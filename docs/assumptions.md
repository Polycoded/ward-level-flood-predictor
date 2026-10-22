# Assumptions

Each owner documents the assumptions behind their part. Model and validation assumptions: Mit. Pipeline: John.

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
