# Geographic module contracts and John handoff

These modules compute terrain and spatial summaries, not flood observations or
hydraulic predictions. Tests use labelled artificial data only. Existing public
function names and positional argument order are retained; new controls are keyword-only.

## Slope: `model.slope.compute_slope`

```python
compute_slope(dem_path, slope_path, vertical_units="m")
```

Input: a single-band real numeric raster, at least 2 rows by 2 columns, with a
verified **projected CRS whose two horizontal axes are metres**, positive x pixel
spacing, negative y pixel spacing and finite affine coefficients. Rotation, shear,
south-up, reversed x, degenerate transforms, geographic and feet-based grids are
rejected with `ValueError`. Do not just relabel a geographic raster as projected.
Use the reprojection helper first for supported geographic inputs.

Elevations must already be in metres. `vertical_units="m"` explicitly defaults to
the legacy caller assumption when metadata is absent; source provenance must confirm
that assumption. Declared band units, when present, must also be metres. Feet/degree
elevations and nontrivial scale/offset metadata are rejected: convert actual values
first, then set correct metadata. This module cannot infer the vertical datum or
detect incorrectly labelled units. No vertical datum transformation is performed.

With row spacing dy = abs(transform.e), column spacing dx = transform.a:

```
gx = elevation derivative across columns / dx
gy = elevation derivative across rows / dy
slope_degrees = degrees(arctan(hypot(gx, gy)))
```

Internally the derivatives use centred differences, with first-order one-sided
differences on the outer boundary. Rectangular/non-square pixels are supported.
Both horizontal and vertical distances are metres, so the gradient is dimensionless.
The row axis points south on a north-up grid; its sign does not affect slope magnitude.

The raster validity mask and declared nodata are read together (`masked=True`), and
NaN/infinite elevations are also treated as unavailable. A slope needs a valid
centre and all cells used by its two derivative stencils. A missing cell invalidates
itself and its affected horizontal/vertical neighbours, not automatically every
diagonal. One-sided edge stencils obey the same policy. No zeros or invented heights
are substituted. An all-missing DEM produces an all-nodata slope raster.

Output: one-band float32 GeoTIFF, degrees (`degree` band unit), **-9999 nodata**,
LZW compression, with original width/height, affine transform and CRS. No NaN/inf
slope values are written. Sampling boundaries and resampling affect slope estimates;
DEM resolution/noise and ward aggregation hide small-scale relief. The module loads
the raster in memory; it is not a tiled large-raster processor.

## Reprojection: `model.slope.reproject_raster`

```python
reproject_raster(src_path, dst_path, dst_crs="EPSG:32644", resolution=30.0,
                 bounds=None, vertical_units="m")
```

Input is a single-band elevation raster (dimensions at least 1×1). The same grid,
numeric, scale/offset and vertical-metre checks apply. Source CRS may be a two-axis
geographic degree CRS or projected metre CRS; destination must be projected metres.
Resolution is a finite positive scalar in destination metres, with square pixels.

When `bounds=None`, Rasterio/GDAL `calculate_default_transform` derives the destination
extent from **actual source bounds in source CRS** and the requested resolution.
If supplied, `bounds=(left, bottom, right, top)` means an explicit **destination-CRS
extent in metres**; width/height are rounded up, left/top anchored exactly, so right
and bottom can extend by less than one pixel. This clarifies the old helper's
ambiguous behavior: it previously passed bounds as though they were source bounds
while retaining full source dimensions. No repository callers of this helper were found.

Masked/nonfinite source cells become NaN source nodata. Elevations are bilinearly
resampled into a float64 work array, then stored as float32, avoiding integer rounding.
A second bilinear warp of 1/0 validity (zero participates, not ignored as source nodata)
rejects any output with validity below 1 (numerical tolerance 1e-12). This prevents
bridging known holes using only the remaining elevations. Outside source coverage
stays unavailable. Output nodata is -9999; valid source elevations equal to that
sentinel are rejected rather than confused with missing data. Output records metre
band units, target CRS and the newly calculated grid.

This is **resampling, not filling**. GDAL's bilinear support/edge handling determines
which cells contribute; partial support at the source perimeter is not a coverage
fraction measurement. The validity warp conservatively excludes known holes within
that support, not all unsampled subpixel terrain. This is not categorical-raster
resampling, hydrological conditioning, vertical datum conversion, multi-band warping,
antimeridian handling or a guarantee of local projection suitability. Rotation/shear
must be warped by an external verified workflow before using this helper. Choose
resolution from source accuracy; smaller pixels do not add terrain information.

## Distances: `model.distance`

```python
distance_to_nearest(wards, targets, metric_crs="EPSG:32644")
compute_ward_water_distances(wards, water, metric_crs="EPSG:32644")
compute_road_distances(points, roads, metric_crs="EPSG:32644")
compute_feature_distances(wards, {"water": water}, metric_crs="EPSG:32644")
```

Inputs are GeoDataFrames with active geometry and verified CRS, including empty
datasets. Input CRSs may differ: both are transformed to metric_crs **before taking
source centroids**. Two-axis geographic degree and projected metre inputs are
supported; missing CRS and projected feet/other units are rejected. metric_crs must
be projected metres; Chennai defaults to UTM 44N (EPSG:32644). Choose an appropriate
local projected CRS explicitly for other locations. A metre axis does not guarantee
low projection distortion (e.g. Web Mercator); caller must verify geographic extent
and projection suitability. This is a planar distance, not a geodesic distance.

The measurement is **ward-centroid-to-nearest-water-geometry distance in metres**,
not polygon-boundary distance, centroid-to-centroid distance, water-edge distance
from every residence, street travel distance or hydraulic connectivity. The centroid
is computed on the projected ward geometry and may lie outside a concave/multipart
ward. A centroid inside/on water has a genuine distance of zero. Target points,
lines and polygons are supported, including multipart geometries. The under-the-hood
union is computed once per call; all wards then measure against it. This is an
in-memory method without spatial-index acceleration for very large target layers.

Output is a **float64 pandas Series**, not a GeoSeries: distances are numbers, not
geometries. Index labels, index name, order and duplicate indices match the original
wards. `compute_feature_distances` returns a dictionary of these Series. Inputs are
not mutated. Source points work through the same centroid operation for road calls.

Missing data policy:

- Null/empty source geometry → NaN for that row.
- Empty target layer, all missing targets, **or any null/empty target geometry** →
  all NaN, because nearest distance to a potentially incomplete set is unknown.
  Do not silently drop missing water records. Verify coverage upstream before removing
  placeholders; a nonempty layer alone does not prove real-world completeness.
- Invalid/nonfinite geometry in either input → actionable ValueError (including after
  reprojection). No silent geometry repair, record dropping or replacement with zero.
- Only 2D geometries are supported; Z coordinates must be explicitly removed upstream.
- Empty source datasets return empty numeric Series after CRS/target validation.

`point_to_line_distance(point, line, *, crs=None)` retains the existing raw Shapely
calling pattern. Shapely carries no CRS: absent crs, the caller asserts that both
geometries already use the same metre grid. An explicit crs is validated as projected
metres; it does not transform coordinates. Null/empty geometries return NaN; invalid,
nonfinite or 3D geometries raise. Prefer GeoDataFrame entry points for CRS safety.

## Exactly how John should integrate (pipeline implementation unchanged here)

1. **Fix actual DEM coordinates before slope.** In pipeline/download_dem.py,
   merge_and_clip_dem currently supplies UTM bounds/res=30 to `rasterio.merge`
   without verifying/reprojecting input tiles, then writes EPSG:32644 metadata. Merely
   assigning CRS is not reprojection. Inspect each tile's actual CRS, units, nodata,
   resolution and provenance. For supported single-band geographic tiles, warp each
   tile to EPSG:32644 with reproject_raster; then merge on a common metric grid with
   explicit nodata. Do not warp a bad merged file whose CRS was already mislabelled.
   Handle tiled overlap and coverage explicitly; do not replace failures with synthetic
   data for production use. Do not infer that this task verified any downloaded tile.
2. **Replace duplicate slope calculation**, including both existing call sites of
   download_dem.create_slope_raster. Delegate that wrapper to the model or import it:

   ```python
   from model.slope import compute_slope, reproject_raster

   # Only when source provenance confirms metre-valued elevations:
   reproject_raster(raw_dem_path, metric_dem_path, "EPSG:32644", 30.0,
                    bounds=verified_destination_extent, vertical_units="m")
   compute_slope(metric_dem_path, slope_path, vertical_units="m")
   ```

   Omit bounds to derive footprint from actual source bounds. Regenerate stale slope
   artifacts: the current pipeline skips when DEM/slope files already exist. Keep
   synthetic fixtures clearly separated from evidence-bearing artifacts. Run/import
   with repository root on Python's module path, e.g. `python -m pipeline.download_dem`.
3. **Replace duplicate zonal_stats.compute_distance_to_water**, which currently also
   references `unary_union` without importing it. Preserve its DataFrame contract:

   ```python
   from model.distance import compute_ward_water_distances

   distance = compute_ward_water_distances(wards_gdf, water_gdf)
   water_dist = distance.to_frame(name="dist_to_water_m")
   ```

   Keep index alignment through joins/concatenation; avoid accidental positional joins
   after filtering. A missing water.gpkg may be represented by an empty frame with a
   verified CRS, but its output is unavailable, never a zero-distance measurement.
4. **Respect raster masks/coverage during zonal aggregation.** The slope nodata sentinel
   is explicit for current zonal_stats_raster filtering. Prefer masked reads and record
   valid-cell counts/coverage; a ward mean over a small surviving subset is not complete
   coverage. Null/empty ward handling in zonal routines also needs upstream attention.
5. **Preserve unknowns through build_features.validate_features**: remove missing-column
   zero creation and coercion/fillna(0) for measurements. Model scoring correctly rejects
   unknown slope/distance; propagate unavailable status rather than inventing inputs.

No pipeline, API, frontend or deployment files are modified in this task. These
handoffs are required before the corrected modules affect pipeline-generated features.
