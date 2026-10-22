"""Metre-based DEM processing. Contracts and caller handoffs: docs/geographic_modules.md."""

from math import ceil
from numbers import Real
from pathlib import Path

import numpy as np
import rasterio
from pyproj import CRS
from rasterio.transform import from_origin
from rasterio.warp import Resampling, calculate_default_transform, reproject

NODATA = -9999.0
METRE_UNITS = {"m", "metre", "meter", "metres", "meters"}


def _validate_crs(crs, *, geographic: bool = False) -> CRS:
    if crs is None:
        raise ValueError("Raster CRS is missing; supply the verified source CRS")
    parsed = CRS.from_user_input(crs)
    axes = parsed.axis_info
    if geographic and parsed.is_geographic and len(axes) == 2:
        if all(axis.unit_name == "degree" for axis in axes):
            return parsed
    if not parsed.is_projected or len(axes) != 2 or not all(
        axis.unit_name in METRE_UNITS and axis.unit_conversion_factor == 1 for axis in axes
    ):
        raise ValueError("Use a projected metre CRS (e.g. EPSG:32644 for Chennai); "
                         "reproject geographic DEMs with reproject_raster first")
    return parsed


def _validate_dem(src, vertical_units: str, *, geographic: bool = False,
                  minimum_size: int = 2) -> None:
    _validate_crs(src.crs, geographic=geographic)
    if src.count != 1 or min(src.width, src.height) < minimum_size:
        raise ValueError(f"DEM must have one band and dimensions >= {minimum_size} cells")
    t = src.transform
    if not all(np.isfinite(tuple(t))) or t.b != 0 or t.d != 0 or t.a <= 0 or t.e >= 0:
        raise ValueError("DEM transform must be finite, north-up and unrotated with positive "
                         "x spacing and negative y spacing; warp to a supported grid first")
    if vertical_units not in METRE_UNITS or (
        src.units[0] is not None and src.units[0].lower() not in METRE_UNITS
    ):
        raise ValueError("DEM elevations must be in metres; convert vertical units first")
    if src.scales[0] != 1 or src.offsets[0] != 0:
        raise ValueError("Apply DEM band scale/offset to metre elevations before processing")
    if np.dtype(src.dtypes[0]).kind not in "iuf":
        raise ValueError("DEM must contain real numeric elevations")


def _read_dem(src) -> np.ndarray:
    dem = src.read(1, masked=True).astype(np.float64).filled(np.nan)
    # GDAL gives internal/.msk masks precedence over nodata metadata. Honour both.
    if src.nodata is not None:
        dem[dem == src.nodata] = np.nan
    dem[~np.isfinite(dem)] = np.nan
    return dem


def compute_slope(dem_path: Path, slope_path: Path, *, vertical_units: str = "m") -> None:
    """Write slope degrees on the original metric grid; unknown stencils stay nodata."""
    with rasterio.open(dem_path) as src:
        _validate_dem(src, vertical_units)
        dem = _read_dem(src)
        # Central differences internally, first-order one-sided differences at edges.
        with np.errstate(invalid="ignore", over="ignore"):
            dy, dx = np.gradient(dem, abs(src.transform.e), src.transform.a)
            slope = np.degrees(np.arctan(np.hypot(dx, dy)))
        slope[~np.isfinite(dem) | ~np.isfinite(slope)] = NODATA
        meta = src.meta.copy()
        meta.update(driver="GTiff", dtype="float32", count=1, nodata=NODATA, compress="lzw")
        with rasterio.open(slope_path, "w", **meta) as dest:
            dest.write(slope.astype(np.float32), 1)
            dest.set_band_unit(1, "degree")


def reproject_raster(src_path: Path, dst_path: Path, dst_crs: str = "EPSG:32644",
                     resolution: float = 30.0, bounds: tuple | None = None, *,
                     vertical_units: str = "m") -> None:
    """Warp one elevation band to a metric grid. bounds are in destination CRS units."""
    _validate_crs(dst_crs)
    if (isinstance(resolution, (bool, np.bool_)) or not isinstance(resolution, Real)
            or not np.isfinite(resolution) or resolution <= 0):
        raise ValueError("resolution must be a finite positive pixel spacing in metres")
    with rasterio.open(src_path) as src:
        _validate_dem(src, vertical_units, geographic=True, minimum_size=1)
        if bounds is None:
            transform, width, height = calculate_default_transform(
                src.crs, dst_crs, src.width, src.height, *src.bounds, resolution=resolution
            )
        else:
            if len(bounds) != 4 or not all(
                isinstance(value, Real) and not isinstance(value, (bool, np.bool_))
                and np.isfinite(value) for value in bounds
            ):
                raise ValueError("bounds must be finite (left, bottom, right, top) in destination CRS")
            left, bottom, right, top = bounds
            if left >= right or bottom >= top:
                raise ValueError("bounds must have left < right and bottom < top")
            width = ceil((right - left) / resolution)
            height = ceil((top - bottom) / resolution)
            transform = from_origin(left, top, resolution, resolution)
        dem = _read_dem(src)
        valid = np.isfinite(dem)
        if np.any(dem[valid] == NODATA):
            raise ValueError("Valid elevation -9999 conflicts with output nodata; recode input first")
        output = np.full((height, width), np.nan, dtype=np.float64)
        coverage = np.zeros((height, width), dtype=np.float64)
        warp_args = dict(src_transform=src.transform, src_crs=src.crs,
                         dst_transform=transform, dst_crs=dst_crs,
                         resampling=Resampling.bilinear, init_dest_nodata=True)
        reproject(dem, output, src_nodata=np.nan, dst_nodata=np.nan, **warp_args)
        # Unlike elevation warp, zeros participate: reject pixels influenced by missing data.
        reproject(valid.astype(np.float64), coverage, dst_nodata=0, **warp_args)
        output[(coverage < 1 - 1e-12) | ~np.isfinite(output)] = NODATA
        meta = src.meta.copy()
        meta.update(driver="GTiff", crs=dst_crs, transform=transform, width=width,
                    height=height, count=1, dtype="float32", nodata=NODATA, compress="lzw")
        with rasterio.open(dst_path, "w", **meta) as dest:
            dest.write(output.astype(np.float32), 1)
            dest.set_band_unit(1, "m")
