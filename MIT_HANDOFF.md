# Chennai Flood Predictor — Technical Handoff to Mit

**Date:** 2026-10-23  
**Pipeline Commit:** `40598b1` (data tracked) / `1bb52ed` (latest)  
**Tests:** 499/499 passing  

---

## 1. Delivered Files (All in Repository)

| File | Size | Description |
|------|------|-------------|
| `data/processed/features.parquet` | 1.09 MB | 200 wards × 44 features |
| `data/processed/features_export.csv` | 5.1 MB | CSV export |
| `data/processed/zonal_stats.parquet` | 73 KB | 200 × 39 zonal statistics |
| `data/processed/wards.geojson` | 4.1 MB | 200 ward polygons, EPSG:32644 |
| `data/processed/ward_crosswalk.csv` | 10.5 KB | ward_id ↔ ward_number ↔ zone mapping |
| `data/raw/Chennai GCC Ward Map - 2022.kml` | 2.8 MB | Original ward boundaries |
| `data/raw/Chennai GCC Zones Map - 2022.kml` | 758 KB | Original zone boundaries |

All files are tracked in the repository (commit `40598b1`).

---

## 2. Real vs Synthetic Inputs — Detailed Audit

### DEM (Elevation + Slope)
| Aspect | Detail |
|--------|--------|
| **Source** | Copernicus DEM 30m COGs via AWS S3 |
| **Tiles** | `Copernicus_DSM_COG_10_N12_00_E080_00_DEM.tif`, `N13_00_E080_00` |
| **Date** | Product metadata (observation vintage); downloaded 2026-10-23 |
| **Method** | Zonal statistics (mean/std/min/max/p10/p50/p90) at 30m resolution |
| **Slope** | `numpy.gradient` on DEM → degrees |
| **Synthetic fallback** | **None** — script `download_dem.py` explicitly states "No synthetic fallback: if the COGs are unavailable the script fails" |

### LULC (Impervious Fraction)
| Aspect | Detail |
|--------|--------|
| **Source** | ESA WorldCover 10m v200 (2021) via Planetary Computer STAC |
| **Tile** | `ESA_WorldCover_10m_2021_v200_N12E078_Map.tif` |
| **Date** | 2021 (product vintage); downloaded 2026-10-23 |
| **Method** | LULC class 50 (built-up) pixel count / total ward pixels |
| **Synthetic fallback** | **None** — script `download_lulc.py` explicitly states "No synthetic fallback: if the COG is unavailable the script fails" |

### OSM-Derived (Water, Roads, Underpasses)
| Aspect | Detail |
|--------|--------|
| **Source** | Geofabrik Southern Zone PBF extract (`southern-zone-261020.osm.pbf`) |
| **Snapshot date** | 2026-10-20 (from filename `261020` = YYMMDD) |
| **Download date** | 2026-10-23 |
| **Method** | Local PBF parsing via `pipeline/extract_osm_local.py` (bbox filter, `other_tags` regex for tunnel/layer/bridge/ford) |
| **Water** | `waterway=river/canal/drain/stream`, `natural=water` |
| **Roads** | `highway` in `motorway,trunk,primary,secondary,tertiary,residential,service,unclassified` |
| **Underpasses** | `tunnel=yes` OR `layer<0` OR `highway=ford` (from `other_tags`) |
| **Synthetic fallback** | **None** — local PBF is used; no Overpass API calls |

---

## 3. Missing Values & Zero Replacement

| Dataset | Null Count | Notes |
|---------|------------|-------|
| `zonal_stats.parquet` | 0 nulls across 39 columns × 200 wards | No missing values to fill |
| `features.parquet` | 0 nulls across 44 columns × 200 wards | No missing values to fill |

**Code behavior:** `build_features.py` has `fillna(0)` logic as defensive coding, but **zonal_stats already had 0 nulls** because all raster/vector zonal stats succeeded for all 200 wards. No values were artificially zeroed. Some all-zero columns (e.g., `lulc_frac_95`, `road_area_sqkm`) are true structural zeros from source data / geometry type, not replacements.

---

## 4. Ward Numbers — Correction

The GeoJSON contains **200 wards numbered 1–200** (not 1–99). The original KML `Name` field contains values 1–200 (non-sequential, matching official GCC numbering). The pipeline extracts `ward_number` via regex `(\d+)` from the `Name` field.

- `ward_id`: 1–200 (sequential internal index, assigned by KML feature order)
- `ward_number`: 1–200 (official GCC ward numbers, non-sequential)

---

## 5. KML Conversion — Actual Script Used

**Source:** User-supplied KML files (official GCC 2022 delimitation maps). No download URL in repository.

**Actual conversion script** (`pipeline/extract_wards_from_kml.py`, corrected to reproduce delivered artifacts):
```python
# pipeline/extract_wards_from_kml.py
import geopandas as gpd
import pandas as pd
import re
from pathlib import Path

wards = gpd.read_file('data/raw/Chennai GCC Ward Map - 2022.kml')
zones = gpd.read_file('data/raw/Chennai GCC Zones Map - 2022.kml')

wards['ward_number'] = wards['Name'].str.extract(r'(\d+)').astype(int)
wards['ward_name'] = 'Ward ' + wards['ward_number'].astype(str)

if wards.crs is None: wards = wards.set_crs('EPSG:4326')
if zones.crs is None: zones = zones.set_crs('EPSG:4326')

wards_utm = wards.to_crs('EPSG:32644')
zones_utm = zones.to_crs('EPSG:32644')
intersections = gpd.overlay(wards_utm, zones_utm[['ZONE', 'ZONE_NAME', 'geometry']], 
                            how='intersection', keep_geom_type=False)
intersections['area'] = intersections.geometry.area
max_area_idx = intersections.groupby('ward_number')['area'].idxmax()
ward_zones = intersections.loc[max_area_idx][['ward_number', 'ZONE', 'ZONE_NAME']]

wards = wards.merge(ward_zones, on='ward_number', how='left')
wards['geometry'] = wards.geometry.buffer(0)

# Assign ward_id sequentially by KML feature order (1..200)
wards['ward_id'] = range(1, len(wards) + 1)
wards_utm = wards.to_crs('EPSG:32644')
wards['area_sqkm'] = wards_utm.geometry.area / 1_000_000

# Save wards
wards.to_crs('EPSG:32644').to_file('data/processed/wards.geojson', driver='GeoJSON')

# Crosswalk - exact column order and values
crosswalk = pd.DataFrame({
    'ward_id': wards['ward_id'],
    'ward_number': wards['ward_number'],
    'ward_name': wards['ward_name'],
    'zone_number': wards['ZONE'],
    'zone_name': wards['ZONE_NAME'],
    'source': 'chennai_gcc_kml_2022'
})
crosswalk.to_csv('data/processed/ward_crosswalk.csv', index=False)
```

**Boundary Repairs Applied:**
- `buffer(0)` on all 200 geometries (fixed 9 invalid polygons)
- No manual polygon editing; only topological repair

---

## 6. Boundary Overlaps & Gaps

### Ward-Ward Overlaps
- **291 ward pairs** overlap by > 1 m² (verified in raw KML — pre-existing in source)
- Largest: Ward 32 & 31 (7,894 m²) — boundary artifact
- **Cause:** Original KML has boundary artifacts (shared boundaries digitized independently)
- **Resolution:** Not resolved in geometry; overlaps are boundary artifacts < 0.01% of ward areas
- **Impact:** Zonal stats use `intersection` which correctly handles overlaps

### Interior Gaps
- **Gap area:** 107,206 m² (0.025% of total summed ward area)
- **Assessment:** Negligible; boundaries form near-complete coverage of GCC bounds

---

## 7. Water Distance — Method Clarification

| Aspect | Implementation |
|--------|----------------|
| **Method** | Projected centroid distance (EPSG:32644) |
| **Formula** | `centroid.distance(water_union)` in meters |
| **Zero condition** | Not automatically zero when water touches; distance = 0 only if centroid falls within water polygon |
| **Touching wards** | 176 wards geometrically touch water, only 2 have `dist_to_water_m = 0` |
| **Not geodesic** | Uses projected Cartesian distance (EPSG:32644), not geodesic |

---

## 8. Source Dates & Methods

| Input | Source Date | Download Date | Method |
|-------|-------------|---------------|--------|
| DEM | Product metadata | 2026-10-23 | Zonal stats on Copernicus 30m COG |
| Slope | Derived 2026-10-23 | 2026-10-23 | `numpy.gradient` on DEM |
| LULC | 2021 (v200) | 2026-10-23 | Zonal fraction of class 50 |
| Water/Roads/Underpasses | OSM snapshot 2026-10-20 | 2026-10-23 | Local Geofabrik PBF (`extract_osm_local.py`) |

---

## 9. Sentinel-1 / Dec 2023 Flood Evidence

| Aspect | Status |
|--------|--------|
| **Sentinel-1 SAR data** | ❌ Not acquired; planned |
| **Flood maps** | ❌ Not generated; planned |
| **Processing scripts** | ❌ Not written; planned |
| **Dec 2023 boundary applicability** | ✅ Official GCC 2022 boundaries match Dec 2023 admin units |
| **Validation labels** | ❌ **Pending** — need Mit to provide `validation_labels.csv` |

**Status:** All Sentinel-1 / validation items are **planned/pending**. The boundary geometry is correct for Dec 2023, but flood labels and validation metrics are not yet produced.

---

## Immediate Actions for Mit

1. **Download files** from repo (all paths above)
2. **Provide `validation_labels.csv`** per evaluator schema: `ward_id,label,source_ref,event_id,boundary_version` (see `data/fixtures/validation_labels_TEMPLATE.csv`)
3. **Complete `data/evidence/chennai_2023/event_metadata_INCOMPLETE.json`** (remove `is_template`, fill all nulls)
4. **Run validation:** `python -m model.validation --predictions preds.csv --labels labels.csv --metadata meta.json --output metrics.json` → produces real `validation_metrics.json`
5. **Review feature provenance** — confirm source dates/units match expectations for evaluation runner config

---

## Pipeline Status Summary

| Component | Status |
|-----------|--------|
| Pipeline scripts | ✅ 6/6 working |
| FastAPI + endpoints | ✅ All working |
| Model modules | ✅ Complete |
| Integrations | ✅ Weather, Twilio, LiveKit (voice needs deps) |
| Dockerfile + CI/CD | ⚠️ CI needs fix (working-directory) |
| Real 200 wards | ✅ Official GCC KML |
| Tests | ✅ 499/499 passing |
| Deploy config | ⚠️ Secrets unset |

---

**Next Steps:** Mit to provide validation labels → real validation metrics → demo-ready system.

*Pipeline commit: `40598b1` | Latest: `1bb52ed` | All tests passing (499/499)*