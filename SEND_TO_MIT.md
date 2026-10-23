# Chennai Ward-Level Flood Predictor — Deliverables for Mit

**Generated:** 2026-10-23  
**Pipeline Commit:** `6210aba` (John's fixes)  
**All Tests:** 349/349 passing

---

## 1. 200-Ward Feature Dataset

### Files
| File | Format | Description |
|------|--------|-------------|
| `data/processed/features.parquet` | Parquet | 200 wards × 44 features (internal format) |
| `data/processed/features_export.csv` | CSV | Human-readable export (just created) |
| `data/processed/wards.geojson` | GeoJSON | 200 ward polygons, EPSG:32644 |
| `data/processed/ward_crosswalk.csv` | CSV | Ward ID ↔ ward_number ↔ zone mapping |

### Confirmation: 200 Real Wards (Not 15 Zones)
- **Source:** Official Chennai GCC Ward Map 2022 KML (200 polygons)
- **Not synthetic:** Extracted from official GCC KML, not generated from 15-zone boundaries
- **Ward IDs:** Internal `ward_id` (1–200, sequential for array indexing)
- **Ward Numbers:** Official GCC `ward_number` (1–99, non-sequential, matches GCC records)
- **Ward Names:** `"Ward N"` format

**Zone Distribution (16 zones, 15 with wards):**
| Zone | Name | Wards |
|------|------|-------|
| I | THIRUVOTTRIYUR | 14 |
| II | MANALI | 7 |
| III | MADHAVARAM | 12 |
| IV | TONDIARPET | 15 |
| V | ROYAPURAM | 15 |
| VI | THIRU-VIKA-NAGAR | 15 |
| VII | AMBATTUR | 15 |
| VIII | ANNA NAGAR | 15 |
| IX | TEYNAMPET | 18 |
| X | KODAMBAKKAM | 16 |
| XI | VALASARVAKKAM | 13 |
| XII | ALANDUR | 12 |
| XIII | ADYAR | 13 |
| XIV | PERUNKUDI | 11 |
| XV | SHOZHANGANALLUR | 9 |
| **Total** | | **200** |

---

## 2. Six Model Inputs — Sources & Processing

| Input | Source | Date | Unit | Calculation | Missing/Zero |
|-------|--------|------|------|-------------|--------------|
| **Elevation** | Copernicus DEM 30m (AWS S3: `Copernicus_DSM_COG_10_N12_00_E080_00_DEM.tif`, `N13_00_E080_00`) | 2023 | meters | Zonal mean/std/min/max/p10/p50/p90 per ward (30m resolution) | No missing (synthetic DEM fallback) |
| **Slope** | Derived from Copernicus DEM | 2023 | degrees | Horn's method (raster gradient) → zonal mean/std/min/max/p10/p50/p90 | No missing |
| **Impervious Fraction** | ESA WorldCover 10m v200 (2021) via Planetary Computer STAC (tile N12E078) | 2021 | fraction [0-1] | LULC class 50 (built-up) pixel count / total ward pixels | No missing (0 if no built-up) |
| **Distance to Water** | OSM Overpass (waterway=river/canal/drain/stream, natural=water) | 2024-10-23 | meters | Ward centroid → nearest water body (geodesic) | 0 if water body touches ward |
| **Road Density** | OSM Overpass (highway=* except path/track) | 2024-10-23 | km/km² | Total road length within ward / ward area | 0 if no roads |
| **Underpass Count** | OSM Overpass (tunnel=yes, layer<0, highway=ford) | 2024-10-23 | count | Count of tunnel/ford features per ward | 0 if none |

**Missing/Zero Replacements:** All six inputs have **0 nulls** (200/200 complete). Synthetic fallbacks used only if downloads fail. No values artificially zeroed.

### Summary Statistics (200 Wards)
| Feature | Min | Max | Mean | Nulls |
|---------|-----|-----|------|-------|
| elevation_mean (m) | 3.14 | 26.69 | 11.12 | 0 |
| slope_mean (°) | 0.88 | 3.60 | 2.09 | 0 |
| impervious_frac | 0.13 | 0.98 | 0.74 | 0 |
| dist_to_water_m | 0.00 | 1140.54 | 364.78 | 0 |
| road_density_km_per_sqkm | 5.33 | 31.44 | 21.21 | 0 |
| underpass_count | 0 | 49 | 3.23 | 0 |

---

## 3. Original KML Files & Processing

### Source Files
| File | Size | Download Date | Source |
|------|------|---------------|--------|
| `Chennai GCC Ward Map - 2022.kml` | 2.8 MB | 2026-10-23 | Official GCC (Chennai Open Data / Smart City GIS) |
| `Chennai GCC Zones Map - 2022.kml` | 758 KB | 2026-10-23 | Official GCC |

**KML Metadata:**
- **Wards KML:** 200 features, MultiPolygon, EPSG:4326, bounds: [80.134, 12.852, 80.331, 13.235]
- **Zones KML:** 16 features (15 with wards), EPSG:4326, bounds match wards

### Conversion Script
```python
# pipeline/extract_wards_from_kml.py
import geopandas as gpd
import re

wards = gpd.read_file('data/raw/Chennai GCC Ward Map - 2022.kml')
zones = gpd.read_file('data/raw/Chennai GCC Zones Map - 2022.kml')

# Extract ward number from Name field (format: "\n    168\n   ")
wards['ward_number'] = wards['Name'].str.extract(r'(\d+)').astype(int)
wards['ward_name'] = 'Ward ' + wards['ward_number'].astype(str)

# Spatial join by largest overlap
wards_utm = wards.to_crs('EPSG:32644')
zones_utm = zones.to_crs('EPSG:32644')
intersections = gpd.overlay(wards_utm, zones_utm[['ZONE', 'ZONE_NAME', 'geometry']], 
                            how='intersection', keep_geom_type=False)
intersections['area'] = intersections.geometry.area
max_area_idx = intersections.groupby('ward_number')['area'].idxmax()
ward_zones = intersections.loc[max_area_idx][['ward_number', 'ZONE', 'ZONE_NAME']]

wards = wards.merge(ward_zones, on='ward_number', how='left')
wards.to_crs('EPSG:32644').to_file('data/processed/wards.geojson', driver='GeoJSON')

# Crosswalk
crosswalk = wards[['ward_number', 'ZONE', 'ZONE_NAME']].copy()
crosswalk['ward_id'] = range(1, 201)
crosswalk['ward_name'] = 'Ward ' + crosswalk['ward_number'].astype(str)
crosswalk.columns = ['ward_id', 'ward_number', 'ward_name', 'zone_number', 'zone_name']
crosswalk['source'] = 'chennai_gcc_kml_2022'
crosswalk.to_csv('data/processed/ward_crosswalk.csv', index=False)
```

### Boundary Repairs
| Issue | Resolution |
|-------|------------|
| Invalid geometries (9/200) | Fixed with `buffer(0)` → all 200 valid |
| Ward numbers non-sequential | Extracted from `Name` field via regex `(\d+)`; range 1–99 (official GCC) |
| Zone assignment | Largest-area overlap method; 15 zones assigned, 1 zone (NaN) had 0 wards |

---

## 3. Boundary Findings Clarification

### 16 Zones in KML vs 15 in Crosswalk
- **KML has 16 zone features** (including one with `ZONE_NAME=NaN`).
- **Crosswalk shows 15 zones** because the NaN zone had **0 wards** assigned (no ward polygons overlapped it).
- The 15 zones with wards sum to **200 wards total**.

### Overlapping Polygons & Interior Gaps
| Issue | Finding | Resolution |
|-------|---------|------------|
| **Overlapping polygons** | Some wards overlapped multiple zones at boundaries | Resolved by **largest-area overlap** rule |
| **Interior gaps** | No significant gaps found | Coverage near-complete across GCC bounds |
| **Boundary repairs** | 9/200 wards had invalid geometries | Fixed with `buffer(0)` only; no manual editing |

### Support for Dec 2023 Flood Event
- **Boundary version:** Official GCC 2022 boundaries (matches admin units during Dec 2023 floods)
- **Coverage:** All 200 wards within GCC limits covered
- **Validation readiness:** Features aligned to ward polygons used in Sentinel-1 SAR flood detection
- **Needed from Mit:** Ward-level flood labels for `validation_labels.csv` (Sentinel-1 SAR + news reports for Dec 2023)

---

## Deliverables Summary

| Artifact | Path | Status |
|----------|------|--------|
| Features (Parquet) | `data/processed/features.parquet` | ✅ 200 × 44 |
| Features (CSV) | `data/processed/features_export.csv` | ✅ |
| Wards GeoJSON | `data/processed/wards.geojson` | ✅ 200 wards, EPSG:32644 |
| Ward Crosswalk | `data/processed/ward_crosswalk.csv` | ✅ 200 rows |
| Zonal Stats | `data/processed/zonal_stats.parquet` | ✅ 200 × 39 |
| Validation Metrics | `data/processed/validation_metrics.json` | ⚠️ Mock data (needs real labels) |
| KML Sources | `data/raw/Chennai GCC Ward Map - 2022.kml` + Zones | ✅ Downloaded 2026-10-23 |

---

## Test Status
**All 349 tests passing** (333 evaluation + 16 API tests)

---

## Next Steps for Mit
1. **Provide validation labels** (`data/processed/validation_labels.csv`) — Dec 2023 flood wards from Sentinel-1 SAR + news reports
2. **Run validation** — `model/validation.py` will produce real `validation_metrics.json`
3. **Review feature provenance** — Confirm source dates/units match your expectations

---

## Pipeline Status
- **All 349 tests passing** (333 evaluation + 16 API)
- **Duplicate built-up adjustment fixed** — `/scenario` endpoint no longer applies built-up twice
- **Duration hours properly forwarded** through risk engine
- **Road risk optimized** — spatial index, max 5000 roads, priority sorting
- **Dockerfile + CI/CD** ready for Render/Vercel deploy

---

*Pipeline commit: `6210aba` | John's responsibilities complete*