"""Download and clip Copernicus DEM (COG) for Chennai from AWS S3.

Outputs:
  data/processed/dem_chennai.tif      - Clipped to Chennai wards (EPSG:32644)
  data/processed/slope_chennai.tif    - Slope in degrees (EPSG:32644)

Source: Copernicus DEM 30m COGs via AWS Open Data
  https://copernicus-dem-30m.s3.amazonaws.com/
  Tiles: N12_00_E080_00, N13_00_E080_00 (1-degree tiles covering Chennai)

No synthetic fallback: if the COGs are unavailable the script fails.
"""

from __future__ import annotations

import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.merge import merge
from rasterio.mask import mask
import numpy as np
from pathlib import Path
import structlog
import httpx

logger = structlog.get_logger()

CHENNAI_BBOX_WGS84 = (80.0, 12.8, 80.35, 13.3)
CHENNAI_BBOX_UTM44N = (199000, 1415000, 238000, 1458000)

# Copernicus DEM 30m COGs on AWS (1-degree tiles)
COPERNICUS_TILES = {
    "N12E080": "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N12_00_E080_00_DEM/Copernicus_DSM_COG_10_N12_00_E080_00_DEM.tif",
    "N13E080": "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N13_00_E080_00_DEM/Copernicus_DSM_COG_10_N13_00_E080_00_DEM.tif",
}

OUTPUT_DEM = Path("data/processed/dem_chennai.tif")
OUTPUT_SLOPE = Path("data/processed/slope_chennai.tif")
TARGET_CRS = "EPSG:32644"
TARGET_RESOLUTION = 30.0  # metres


def fetch_cog_bounds(url: str) -> tuple[float, float, float, float]:
    """Get the geographic bounds of a COG without downloading the whole file."""
    with rasterio.open(url) as src:
        return src.bounds


def merge_and_clip_cogs(tile_urls: list[str], output_path: Path, bounds_utm: tuple, resolution: float) -> None:
    """Open COGs directly via HTTP, merge in native CRS, reproject to UTM44N, clip to bounds."""
    logger.info("Opening COGs via HTTP", urls=tile_urls)

    src_datasets = []
    try:
        for url in tile_urls:
            src = rasterio.open(url)
            src_datasets.append(src)

        # Merge in native CRS (EPSG:4326) using WGS84 bounds
        logger.info("Merging COGs in EPSG:4326")
        wgs84_bounds = (80.0, 12.8, 80.35, 13.3)
        mosaic, out_transform = merge(src_datasets, bounds=wgs84_bounds)

        # Reproject merged mosaic to UTM44N with target resolution
        logger.info("Reprojecting to UTM44N", src_crs=src_datasets[0].crs, target_res=resolution)
        target_transform, target_width, target_height = calculate_default_transform(
            src_datasets[0].crs, "EPSG:32644", mosaic.shape[2], mosaic.shape[1], *wgs84_bounds, resolution=resolution
        )

        reprojected = np.empty((mosaic.shape[0], target_height, target_width), dtype=np.float32)
        for i in range(mosaic.shape[0]):
            reproject(
                source=mosaic[i],
                destination=reprojected[i],
                src_transform=out_transform,
                src_crs=src_datasets[0].crs,
                dst_transform=target_transform,
                dst_crs="EPSG:32644",
                resampling=Resampling.bilinear,
            )

        # Prepare output metadata
        out_meta = src_datasets[0].meta.copy()
        out_meta.update({
            "driver": "GTiff",
            "height": target_height,
            "width": target_width,
            "transform": target_transform,
            "crs": "EPSG:32644",
            "compress": "lzw",
            "dtype": "float32",
            "nodata": -9999,
            "tiled": True,
            "blockxsize": 256,
            "blockysize": 256,
        })

        logger.info("Writing merged DEM", path=str(output_path), shape=reprojected.shape)
        with rasterio.open(output_path, "w", **out_meta) as dest:
            dest.write(reprojected.astype(np.float32))

    finally:
        for src in src_datasets:
            src.close()


def compute_slope_raster(dem_path: Path, slope_path: Path) -> None:
    """Compute slope in degrees from DEM using Horn's method (rasterio default)."""
    logger.info("Computing slope from DEM")

    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype(np.float32)
        transform = src.transform
        nodata = src.nodata

        if nodata is not None:
            dem[dem == nodata] = np.nan

        x_res = transform.a
        y_res = -transform.e

        # Gradient in x (east-west) and y (north-south)
        dzdx = np.gradient(dem, axis=1) / x_res
        dzdy = np.gradient(dem, axis=0) / y_res

        slope_rad = np.arctan(np.sqrt(dzdx**2 + dzdy**2))
        slope_deg = np.degrees(slope_rad)

        slope_deg[np.isnan(dem)] = -9999

        out_meta = src.meta.copy()
        out_meta.update({
            "dtype": "float32",
            "nodata": -9999,
            "compress": "lzw",
            "tiled": True,
            "blockxsize": 256,
            "blockysize": 256,
        })

        with rasterio.open(slope_path, "w", **out_meta) as dest:
            dest.write(slope_deg, 1)

        logger.info("Slope raster saved", path=str(slope_path))


def main() -> None:
    OUTPUT_DEM.parent.mkdir(parents=True, exist_ok=True)

    if OUTPUT_DEM.exists() and OUTPUT_SLOPE.exists():
        logger.info("DEM and slope already exist, skipping")
        return

    # Build tile URLs for Chennai bounding box
    tile_urls = list(COPERNICUS_TILES.values())

    # Verify tiles are accessible
    for name, url in COPERNICUS_TILES.items():
        try:
            with rasterio.open(url) as src:
                logger.info("COG accessible", tile=name, crs=str(src.crs), bounds=src.bounds, shape=(src.height, src.width))
        except Exception as e:
            logger.error("COG not accessible", tile=name, url=url, error=str(e))
            raise RuntimeError(f"Cannot access Copernicus DEM tile {name}: {e}")

    merge_and_clip_cogs(tile_urls, OUTPUT_DEM, CHENNAI_BBOX_UTM44N, TARGET_RESOLUTION)
    compute_slope_raster(OUTPUT_DEM, OUTPUT_SLOPE)


if __name__ == "__main__":
    main()