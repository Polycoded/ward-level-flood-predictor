import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import httpx
import numpy as np
from pathlib import Path
import structlog
import tempfile

logger = structlog.get_logger()

CHENNAI_BBOX_WGS84 = [80.0, 12.8, 80.35, 13.3]
CHENNAI_BBOX_UTM44N = [199000, 1415000, 238000, 1458000]

ESA_WORLDCOVER_URL = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/ESA_WorldCover_10m_2021_v200_N12E080_Map.tif"

LULC_CLASSES = {
    10: "Tree cover",
    20: "Shrubland",
    30: "Grassland",
    40: "Cropland",
    50: "Built-up",
    60: "Bare / sparse vegetation",
    70: "Snow and ice",
    80: "Permanent water bodies",
    90: "Herbaceous wetland",
    95: "Mangroves",
    100: "Moss and lichen",
}

IMPERVIOUS_CLASSES = {50}
WATER_CLASSES = {80, 90, 95}

def download_lulc(output_path: Path) -> Path:
    raw_path = output_path.parent / "raw_lulc.tif"
    
    if raw_path.exists():
        logger.info("LULC raw file already exists")
        return raw_path
    
    logger.info("Downloading ESA WorldCover LULC", url=ESA_WORLDCOVER_URL)
    
    try:
        with httpx.stream("GET", ESA_WORLDCOVER_URL, timeout=300.0) as response:
            response.raise_for_status()
            with open(raw_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
        logger.info("LULC downloaded", path=str(raw_path))
        return raw_path
    except Exception as e:
        logger.error("Failed to download LULC", error=str(e))
        raise

def clip_and_reproject_lulc(input_path: Path, output_path: Path) -> None:
    logger.info("Clipping and reprojecting LULC to UTM44N")
    
    with rasterio.open(input_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, "EPSG:32644", src.width, src.height, *CHENNAI_BBOX_WGS84
        )
        
        out_meta = src.meta.copy()
        out_meta.update({
            "crs": "EPSG:32644",
            "transform": transform,
            "width": width,
            "height": height,
            "compress": "lzw",
            "dtype": "uint8",
        })
        
        with rasterio.open(output_path, "w", **out_meta) as dest:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dest, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs="EPSG:32644",
                    resampling=Resampling.nearest,
                )
    
    logger.info("LULC clipped and reprojected", path=str(output_path))

def create_synthetic_lulc(output_path: Path) -> None:
    logger.info("Creating synthetic LULC for development")
    
    height = 1400
    width = 1300
    transform = rasterio.transform.from_bounds(*CHENNAI_BBOX_UTM44N, width, height)
    
    y, x = np.meshgrid(np.arange(height), np.arange(width), indexing='ij')
    
    lulc = np.full((height, width), 40, dtype=np.uint8)
    
    center_y, center_x = height // 2, width // 2
    dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)
    max_dist = np.sqrt(center_x**2 + center_y**2)
    
    built_up_mask = dist < max_dist * 0.6
    lulc[built_up_mask] = 50
    
    water_mask = (x < width * 0.15) | (y > height * 0.85)
    lulc[water_mask] = 80
    
    tree_mask = (dist > max_dist * 0.7) & np.random.random((height, width)) < 0.3
    lulc[tree_mask] = 10
    
    out_meta = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "uint8",
        "crs": "EPSG:32644",
        "transform": transform,
        "nodata": 0,
        "compress": "lzw",
    }
    
    with rasterio.open(output_path, "w", **out_meta) as dest:
        dest.write(lulc, 1)
    
    logger.info("Synthetic LULC created", path=str(output_path))

def main():
    processed_dir = Path("data/processed")
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = processed_dir / "lulc_chennai.tif"
    
    if output_path.exists():
        logger.info("LULC already exists, skipping")
        return
    
    try:
        raw_path = download_lulc(processed_dir)
        clip_and_reproject_lulc(raw_path, output_path)
    except Exception as e:
        logger.error("Failed to process LULC", error=str(e))
        logger.warning("Creating synthetic LULC for development")
        create_synthetic_lulc(output_path)

if __name__ == "__main__":
    main()