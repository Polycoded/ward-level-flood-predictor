import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np
from pathlib import Path
import structlog

logger = structlog.get_logger()


def compute_slope(dem_path: Path, slope_path: Path) -> None:
    logger.info("Computing slope from DEM")
    
    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype(np.float32)
        transform = src.transform
        crs = src.crs
        nodata = src.nodata
        
        if nodata is not None:
            dem[dem == nodata] = np.nan
        
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


def reproject_raster(src_path: Path, dst_path: Path, dst_crs: str = "EPSG:32644", 
                      resolution: float = 30.0, bounds: tuple = None) -> None:
    logger.info("Reprojecting raster", src=src_path.name, dst_crs=dst_crs)
    
    with rasterio.open(src_path) as src:
        if bounds:
            transform, width, height = calculate_default_transform(
                src.crs, dst_crs, src.width, src.height, *bounds, resolution=resolution
            )
        else:
            transform, width, height = calculate_default_transform(
                src.crs, dst_crs, src.width, src.height, *src.bounds, resolution=resolution
            )
        
        out_meta = src.meta.copy()
        out_meta.update({
            "crs": dst_crs,
            "transform": transform,
            "width": width,
            "height": height,
            "compress": "lzw",
        })
        
        with rasterio.open(dst_path, "w", **out_meta) as dest:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dest, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.bilinear,
                )
        
        logger.info("Raster reprojected", path=str(dst_path))