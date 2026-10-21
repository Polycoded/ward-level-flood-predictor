import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.merge import merge
import httpx
import numpy as np
from pathlib import Path
import structlog
import tempfile
import os

logger = structlog.get_logger()

CHENNAI_BBOX_WGS84 = [80.0, 12.8, 80.35, 13.3]
CHENNAI_BBOX_UTM44N = [199000, 1415000, 238000, 1458000]

SRTM_TILES = {
    "N12E080": "https://srtm.csi.cgiar.org/wp-content/uploads/files/srtm_5x5/TIFF/srtm_56_06.zip",
    "N13E080": "https://srtm.csi.cgiar.org/wp-content/uploads/files/srtm_5x5/TIFF/srtm_56_07.zip",
}

def download_srtm_tiles(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tiff_paths = []
    
    for tile_name, url in SRTM_TILES.items():
        zip_path = output_dir / f"{tile_name}.zip"
        tiff_path = output_dir / f"{tile_name}.tif"
        
        if tiff_path.exists():
            logger.info("Tile already exists", tile=tile_name)
            tiff_paths.append(tiff_path)
            continue
        
        logger.info("Downloading SRTM tile", tile=tile_name, url=url)
        try:
            with httpx.stream("GET", url, timeout=300.0) as response:
                response.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
            
            import zipfile
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(output_dir)
            
            zip_path.unlink()
            
            extracted_tiffs = list(output_dir.glob("*.tif"))
            if extracted_tiffs:
                tiff_paths.append(extracted_tiffs[0])
                logger.info("Tile downloaded and extracted", tile=tile_name)
            else:
                logger.warning("No TIFF found in archive", tile=tile_name)
                
        except Exception as e:
            logger.error("Failed to download tile", tile=tile_name, error=str(e))
    
    return tiff_paths

def merge_and_clip_dem(tiff_paths: list[Path], output_path: Path, bounds_utm: tuple) -> None:
    if not tiff_paths:
        raise ValueError("No DEM tiles available")
    
    logger.info("Merging and clipping DEM tiles", count=len(tiff_paths))
    
    src_files = [rasterio.open(p) for p in tiff_paths]
    try:
        mosaic, out_transform = merge(src_files, bounds=bounds_utm, res=30.0)
        
        out_meta = src_files[0].meta.copy()
        out_meta.update({
            "driver": "GTiff",
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": out_transform,
            "crs": "EPSG:32644",
            "compress": "lzw",
            "dtype": "float32",
            "nodata": -9999,
        })
        
        with rasterio.open(output_path, "w", **out_meta) as dest:
            dest.write(mosaic.astype(np.float32))
        
        logger.info("DEM saved", path=str(output_path), shape=mosaic.shape)
        
    finally:
        for src in src_files:
            src.close()

def create_slope_raster(dem_path: Path, slope_path: Path) -> None:
    logger.info("Computing slope from DEM")
    
    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype(np.float32)
        transform = src.transform
        crs = src.crs
        nodata = src.nodata
        
        if nodata is not None:
            dem[dem == nodata] = np.nan
        
        from rasterio.warp import transform_bounds
        bounds_wgs84 = transform_bounds(crs, "EPSG:4326", *src.bounds)
        
        x_res = transform.a
        y_res = -transform.e
        
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
        })
        
        with rasterio.open(slope_path, "w", **out_meta) as dest:
            dest.write(slope_deg, 1)
        
        logger.info("Slope raster saved", path=str(slope_path))

def main():
    raw_dir = Path("data/raw/dem")
    processed_dir = Path("data/processed")
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    dem_path = processed_dir / "dem_chennai.tif"
    slope_path = processed_dir / "slope_chennai.tif"
    
    if dem_path.exists() and slope_path.exists():
        logger.info("DEM and slope already exist, skipping")
        return
    
    try:
        tiff_paths = download_srtm_tiles(raw_dir)
        
        if not tiff_paths:
            logger.warning("No SRTM tiles downloaded, creating synthetic DEM for development")
            create_synthetic_dem(dem_path)
        else:
            merge_and_clip_dem(tiff_paths, dem_path, CHENNAI_BBOX_UTM44N)
        
        create_slope_raster(dem_path, slope_path)
        
    except Exception as e:
        logger.error("Failed to process DEM", error=str(e))
        logger.warning("Creating synthetic DEM for development")
        create_synthetic_dem(dem_path)
        create_slope_raster(dem_path, slope_path)

def create_synthetic_dem(output_path: Path) -> None:
    logger.info("Creating synthetic DEM for Chennai")
    
    height = 1400
    width = 1300
    transform = rasterio.transform.from_bounds(*CHENNAI_BBOX_UTM44N, width, height)
    
    y, x = np.meshgrid(np.arange(height), np.arange(width), indexing='ij')
    
    center_y, center_x = height // 2, width // 2
    dist_from_center = np.sqrt((x - center_x)**2 + (y - center_y)**2)
    max_dist = np.sqrt(center_x**2 + center_y**2)
    
    base_elevation = 15.0
    elevation = base_elevation + 30 * (1 - dist_from_center / max_dist)
    elevation += np.random.normal(0, 2, size=elevation.shape)
    elevation = np.maximum(elevation, 0.5)
    
    out_meta = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:32644",
        "transform": transform,
        "nodata": -9999,
        "compress": "lzw",
    }
    
    with rasterio.open(output_path, "w", **out_meta) as dest:
        dest.write(elevation.astype(np.float32), 1)
    
    logger.info("Synthetic DEM created", path=str(output_path))

if __name__ == "__main__":
    main()