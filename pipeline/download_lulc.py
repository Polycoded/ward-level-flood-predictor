"""Download and clip ESA WorldCover LULC for Chennai from Microsoft Planetary Computer STAC.

Output:
  data/processed/lulc_chennai.tif - Clipped to Chennai wards (EPSG:32644), 10m resolution

Source: ESA WorldCover 10m v200 (2021) via Planetary Computer STAC
  Collection: esa-worldcover
  Tile: N12E078 (covers 78E-81E, 12N-15N - includes Chennai)

No synthetic fallback: if the COG is unavailable the script fails.
"""

from __future__ import annotations

import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.mask import mask
from pathlib import Path
import structlog
import pystac_client
import planetary_computer

logger = structlog.get_logger()

CHENNAI_BBOX_WGS84 = (80.0, 12.8, 80.35, 13.3)
CHENNAI_BBOX_UTM44N = (199000, 1415000, 238000, 1458000)

OUTPUT_LULC = Path("data/processed/lulc_chennai.tif")
TARGET_CRS = "EPSG:32644"
TARGET_RESOLUTION = 10.0  # metres (native ESA WorldCover resolution)

STAC_CATALOG = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "esa-worldcover"
ITEM_ID = "ESA_WorldCover_10m_2021_v200_N12E078"  # Covers Chennai
ASSET_KEY = "map"  # The LULC classification COG


def get_lulc_cog_url() -> str:
    """Query STAC for the ESA WorldCover COG URL with signed SAS token."""
    logger.info("Querying Planetary Computer STAC for ESA WorldCover")

    catalog = pystac_client.Client.open(
        STAC_CATALOG,
        modifier=planetary_computer.sign_inplace,
    )

    search = catalog.search(
        collections=[COLLECTION],
        ids=[ITEM_ID],
    )
    items = list(search.items())

    if not items:
        raise RuntimeError(f"Item {ITEM_ID} not found in {COLLECTION}")

    item = items[0]
    asset = item.assets.get(ASSET_KEY)
    if not asset:
        raise RuntimeError(f"Asset '{ASSET_KEY}' not found in item {ITEM_ID}")

    # The signed URL is valid for ~1 hour
    url = asset.href
    logger.info("Found LULC COG", item=ITEM_ID, url=url[:80] + "...")
    return url


def clip_cog_to_chennai(cog_url: str, output_path: Path, bounds_utm: tuple, resolution: float) -> None:
    """Open COG via HTTP, reproject to UTM44N, and clip to Chennai bounds."""
    logger.info("Opening LULC COG", url=cog_url[:80] + "...")

    with rasterio.open(cog_url) as src:
        logger.info("LULC COG info", crs=str(src.crs), bounds=src.bounds, shape=(src.height, src.width), dtype=src.dtypes[0])

        # Calculate transform for target CRS and bounds
        transform, width, height = calculate_default_transform(
            src.crs, TARGET_CRS, src.width, src.height, *CHENNAI_BBOX_WGS84, resolution=resolution
        )

        out_meta = src.meta.copy()
        out_meta.update({
            "crs": TARGET_CRS,
            "transform": transform,
            "width": width,
            "height": height,
            "compress": "lzw",
            "dtype": "uint8",
            "nodata": 0,
            "tiled": True,
            "blockxsize": 256,
            "blockysize": 256,
        })

        logger.info("Reprojecting and clipping LULC", output_shape=(height, width))
        with rasterio.open(output_path, "w", **out_meta) as dest:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dest, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=TARGET_CRS,
                    resampling=Resampling.nearest,
                )

        logger.info("LULC saved", path=str(output_path), shape=(height, width))


def main() -> None:
    OUTPUT_LULC.parent.mkdir(parents=True, exist_ok=True)

    if OUTPUT_LULC.exists():
        logger.info("LULC already exists, skipping")
        return

    cog_url = get_lulc_cog_url()
    clip_cog_to_chennai(cog_url, OUTPUT_LULC, CHENNAI_BBOX_UTM44N, TARGET_RESOLUTION)


if __name__ == "__main__":
    main()