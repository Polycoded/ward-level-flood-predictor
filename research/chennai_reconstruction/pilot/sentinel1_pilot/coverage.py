"""Coverage, mask and grid-alignment helpers for the Sentinel-1 pilot."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from rasterio.warp import Resampling, reproject
from shapely.ops import unary_union

from .acquisition import bbox_polygon, footprint_box


def valid_mask(array: np.ndarray, nodata: float | None = None,
               valid_range: tuple[float, float] | None = None) -> np.ndarray:
    data = np.asarray(array)
    mask = np.isfinite(data)
    if nodata is not None:
        mask &= data != nodata
    if valid_range is not None:
        low, high = valid_range
        mask &= (data >= low) & (data <= high)
    return mask


def border_mask(valid: np.ndarray, border_px: int = 1) -> np.ndarray:
    if border_px < 0:
        raise ValueError("border_px must be non-negative")
    mask = np.zeros(np.asarray(valid).shape, dtype=bool)
    if border_px == 0:
        return mask
    mask[:border_px, :] = True
    mask[-border_px:, :] = True
    mask[:, :border_px] = True
    mask[:, -border_px:] = True
    return mask & np.asarray(valid, dtype=bool)


def coverage_stats(valid: np.ndarray) -> dict:
    valid = np.asarray(valid, dtype=bool)
    total = int(valid.size)
    observed = int(valid.sum())
    return {
        "pixels_total": total,
        "pixels_valid": observed,
        "pixels_nodata": total - observed,
        "valid_fraction": observed / total if total else None,
    }


def common_valid_mask(masks: list[np.ndarray]) -> np.ndarray:
    if not masks:
        raise ValueError("At least one mask is required")
    shapes = {np.asarray(mask).shape for mask in masks}
    if len(shapes) > 1:
        raise ValueError(f"Mask shapes differ: {sorted(shapes)}")
    result = np.ones(next(iter(shapes)), dtype=bool)
    for mask in masks:
        result &= np.asarray(mask, dtype=bool)
    return result


def union_footprint_coverage(items: list[dict], bbox_wgs84: list[float]) -> dict:
    target = bbox_polygon(bbox_wgs84)
    if not items:
        return {"bbox_area_deg2": target.area, "union_area_deg2": 0.0,
                "coverage_fraction": 0.0}
    union = unary_union([footprint_box(item) for item in items])
    intersection = union.intersection(target)
    return {
        "bbox_area_deg2": float(target.area),
        "union_area_deg2": float(union.area),
        "intersection_area_deg2": float(intersection.area),
        "coverage_fraction": float(intersection.area / target.area),
    }


def boundary_coverage(boundary_path: Path, items: list[dict],
                      boundary_crs: str | None = None) -> dict:
    """Return coverage over a boundary layer only if the file exists.

    Callers must separately enforce licence/authority. A missing file is a blocker,
    not a reason to substitute another boundary.
    """
    path = Path(boundary_path)
    if not path.exists():
        return {"status": "blocked", "reason": f"boundary not found: {path}",
                "coverage_fraction": None}
    import geopandas as gpd

    boundary = gpd.read_file(path)
    if boundary.crs is None:
        return {"status": "blocked", "reason": "boundary has no CRS",
                "coverage_fraction": None}
    boundary = boundary.to_crs(4326)
    union = unary_union(boundary.geometry.tolist())
    footprint = unary_union([footprint_box(item) for item in items])
    fraction = union.intersection(footprint).area / union.area if union.area else None
    return {"status": "calculated", "reason": None,
            "coverage_fraction": float(fraction) if fraction is not None else None}


def reproject_to_grid(source: np.ndarray, source_transform, source_crs: str,
                      destination_shape: tuple[int, int], destination_transform,
                      destination_crs: str, nodata: float = np.nan,
                      resampling: Resampling = Resampling.nearest) -> np.ndarray:
    """Align a raster array to a target grid; used only when data are available."""
    source = np.asarray(source)
    destination = np.full(destination_shape, nodata, dtype=source.dtype)
    reproject(
        source=source,
        destination=destination,
        src_transform=source_transform,
        src_crs=source_crs,
        dst_transform=destination_transform,
        dst_crs=destination_crs,
        src_nodata=nodata,
        dst_nodata=nodata,
        resampling=resampling,
    )
    return destination
