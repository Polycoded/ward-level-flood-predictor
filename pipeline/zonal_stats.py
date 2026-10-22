import geopandas as gpd
import rasterio
from rasterio.mask import mask
import numpy as np
import pandas as pd
from pathlib import Path
import structlog
from shapely.geometry import mapping
from shapely.ops import unary_union

logger = structlog.get_logger()

def zonal_stats_raster(wards_gdf: gpd.GeoDataFrame, raster_path: Path, stat_name: str, 
                        nodata: float = None, percentiles: list = None) -> pd.DataFrame:
    logger.info("Computing zonal stats", raster=raster_path.name, stat=stat_name)
    
    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
        raster_nodata = src.nodata if nodata is None else nodata
        
        if wards_gdf.crs != raster_crs:
            wards_gdf = wards_gdf.to_crs(raster_crs)
        
        results = []
        
        for idx, row in wards_gdf.iterrows():
            geom = row.geometry
            if geom.is_empty:
                results.append({f"{stat_name}_mean": np.nan, f"{stat_name}_std": np.nan, 
                               f"{stat_name}_min": np.nan, f"{stat_name}_max": np.nan})
                continue
            
            try:
                out_image, out_transform = mask(src, [mapping(geom)], crop=True, nodata=raster_nodata)
                data = out_image[0]
                
                if raster_nodata is not None:
                    data = data[data != raster_nodata]
                
                data = data[~np.isnan(data)]
                
                if len(data) == 0:
                    stats = {f"{stat_name}_mean": np.nan, f"{stat_name}_std": np.nan,
                            f"{stat_name}_min": np.nan, f"{stat_name}_max": np.nan}
                else:
                    stats = {
                        f"{stat_name}_mean": float(np.mean(data)),
                        f"{stat_name}_std": float(np.std(data)),
                        f"{stat_name}_min": float(np.min(data)),
                        f"{stat_name}_max": float(np.max(data)),
                    }
                    
                    if percentiles:
                        for p in percentiles:
                            stats[f"{stat_name}_p{p}"] = float(np.percentile(data, p))
                
                results.append(stats)
                
            except Exception as e:
                logger.warning("Zonal stat failed for ward", ward_id=row.get("ward_id"), error=str(e))
                results.append({f"{stat_name}_mean": np.nan, f"{stat_name}_std": np.nan,
                               f"{stat_name}_min": np.nan, f"{stat_name}_max": np.nan})
    
    return pd.DataFrame(results, index=wards_gdf.index)

def zonal_stats_vector(wards_gdf: gpd.GeoDataFrame, vector_gdf: gpd.GeoDataFrame, 
                        stat_name: str, value_column: str = None) -> pd.DataFrame:
    logger.info("Computing zonal stats from vector", vector=len(vector_gdf), stat=stat_name)
    
    if wards_gdf.crs != vector_gdf.crs:
        vector_gdf = vector_gdf.to_crs(wards_gdf.crs)
    
    results = []
    
    for idx, ward in wards_gdf.iterrows():
        ward_geom = ward.geometry
        if ward_geom.is_empty:
            results.append({f"{stat_name}_count": 0, f"{stat_name}_length_km": 0.0, 
                           f"{stat_name}_area_sqkm": 0.0})
            continue
        
        intersecting = vector_gdf[vector_gdf.intersects(ward_geom)]
        
        if len(intersecting) == 0:
            results.append({f"{stat_name}_count": 0, f"{stat_name}_length_km": 0.0,
                           f"{stat_name}_area_sqkm": 0.0})
            continue
        
        if vector_gdf.geometry.geom_type.iloc[0] in ("LineString", "MultiLineString"):
            clipped = intersecting.intersection(ward_geom)
            total_length = clipped.length.sum() / 1000
            results.append({
                f"{stat_name}_count": len(intersecting),
                f"{stat_name}_length_km": float(total_length),
                f"{stat_name}_area_sqkm": 0.0,
            })
        else:
            clipped = intersecting.intersection(ward_geom)
            total_area = clipped.area.sum() / 1e6
            results.append({
                f"{stat_name}_count": len(intersecting),
                f"{stat_name}_length_km": 0.0,
                f"{stat_name}_area_sqkm": float(total_area),
            })
    
    return pd.DataFrame(results, index=wards_gdf.index)

def compute_lulc_fractions(wards_gdf: gpd.GeoDataFrame, lulc_path: Path) -> pd.DataFrame:
    logger.info("Computing LULC class fractions per ward")
    
    with rasterio.open(lulc_path) as src:
        if wards_gdf.crs != src.crs:
            wards_gdf = wards_gdf.to_crs(src.crs)
        
        results = []
        
        for idx, row in wards_gdf.iterrows():
            geom = row.geometry
            if geom.is_empty:
                fracs = {f"lulc_frac_{k}": 0.0 for k in [10, 20, 30, 40, 50, 60, 80, 90, 95]}
                results.append(fracs)
                continue
            
            try:
                out_image, _ = mask(src, [mapping(geom)], crop=True, nodata=0)
                data = out_image[0]
                data = data[data != 0]
                
                total = len(data)
                if total == 0:
                    fracs = {f"lulc_frac_{k}": 0.0 for k in [10, 20, 30, 40, 50, 60, 80, 90, 95]}
                else:
                    fracs = {}
                    for class_val in [10, 20, 30, 40, 50, 60, 80, 90, 95]:
                        count = np.sum(data == class_val)
                        fracs[f"lulc_frac_{class_val}"] = float(count / total)
                    
                    fracs["impervious_frac"] = fracs.get("lulc_frac_50", 0.0)
                    fracs["water_frac"] = fracs.get("lulc_frac_80", 0.0) + fracs.get("lulc_frac_90", 0.0) + fracs.get("lulc_frac_95", 0.0)
                    fracs["vegetation_frac"] = fracs.get("lulc_frac_10", 0.0) + fracs.get("lulc_frac_20", 0.0) + fracs.get("lulc_frac_30", 0.0)
                
                results.append(fracs)
                
            except Exception as e:
                logger.warning("LULC fraction failed for ward", ward_id=row.get("ward_id"), error=str(e))
                fracs = {f"lulc_frac_{k}": 0.0 for k in [10, 20, 30, 40, 50, 60, 80, 90, 95]}
                fracs["impervious_frac"] = 0.0
                fracs["water_frac"] = 0.0
                fracs["vegetation_frac"] = 0.0
                results.append(fracs)
    
    return pd.DataFrame(results, index=wards_gdf.index)

def compute_distance_to_water(wards_gdf: gpd.GeoDataFrame, water_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    logger.info("Computing distance to nearest water body")
    
    if wards_gdf.crs != water_gdf.crs:
        water_gdf = water_gdf.to_crs(wards_gdf.crs)
    
    water_union = unary_union(water_gdf.geometry.tolist())
    
    results = []
    for idx, row in wards_gdf.iterrows():
        centroid = row.geometry.centroid
        dist = centroid.distance(water_union)
        results.append({"dist_to_water_m": float(dist)})
    
    return pd.DataFrame(results, index=wards_gdf.index)

def compute_road_density(wards_gdf: gpd.GeoDataFrame, roads_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    logger.info("Computing road density per ward")
    
    if wards_gdf.crs != roads_gdf.crs:
        roads_gdf = roads_gdf.to_crs(wards_gdf.crs)
    
    results = []
    for idx, row in wards_gdf.iterrows():
        ward_geom = row.geometry
        if ward_geom.is_empty:
            results.append({"road_density_km_per_sqkm": 0.0})
            continue
        
        intersecting = roads_gdf[roads_gdf.intersects(ward_geom)]
        if len(intersecting) == 0:
            results.append({"road_density_km_per_sqkm": 0.0})
            continue
        
        clipped = intersecting.intersection(ward_geom)
        total_length_km = clipped.length.sum() / 1000
        ward_area_sqkm = ward_geom.area / 1e6
        density = total_length_km / ward_area_sqkm if ward_area_sqkm > 0 else 0.0
        results.append({"road_density_km_per_sqkm": float(density)})
    
    return pd.DataFrame(results, index=wards_gdf.index)

def compute_underpass_count(wards_gdf: gpd.GeoDataFrame, underpass_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    logger.info("Computing underpass count per ward")
    
    if wards_gdf.crs != underpass_gdf.crs:
        underpass_gdf = underpass_gdf.to_crs(wards_gdf.crs)
    
    results = []
    for idx, row in wards_gdf.iterrows():
        ward_geom = row.geometry
        if ward_geom.is_empty:
            results.append({"underpass_count": 0})
            continue
        
        count = len(underpass_gdf[underpass_gdf.intersects(ward_geom)])
        results.append({"underpass_count": int(count)})
    
    return pd.DataFrame(results, index=wards_gdf.index)

def main():
    processed_dir = Path("data/processed")
    
    wards_path = processed_dir / "wards.geojson"
    dem_path = processed_dir / "dem_chennai.tif"
    slope_path = processed_dir / "slope_chennai.tif"
    lulc_path = processed_dir / "lulc_chennai.tif"
    water_path = processed_dir / "water.gpkg"
    roads_path = processed_dir / "roads.gpkg"
    underpasses_path = processed_dir / "underpasses.gpkg"
    
    output_path = processed_dir / "zonal_stats.parquet"
    
    logger.info("Loading input data")
    wards = gpd.read_file(wards_path)
    
    dem_stats = zonal_stats_raster(wards, dem_path, "elevation", percentiles=[10, 50, 90])
    slope_stats = zonal_stats_raster(wards, slope_path, "slope", percentiles=[10, 50, 90])
    lulc_fracs = compute_lulc_fractions(wards, lulc_path)
    
    water_gdf = gpd.read_file(water_path) if water_path.exists() else gpd.GeoDataFrame(geometry=[], crs="EPSG:32644")
    roads_gdf = gpd.read_file(roads_path) if roads_path.exists() else gpd.GeoDataFrame(geometry=[], crs="EPSG:32644")
    underpass_gdf = gpd.read_file(underpasses_path) if underpasses_path.exists() else gpd.GeoDataFrame(geometry=[], crs="EPSG:32644")
    
    water_dist = compute_distance_to_water(wards, water_gdf)
    road_density = compute_road_density(wards, roads_gdf)
    underpass_count = compute_underpass_count(wards, underpass_gdf)
    
    water_stats = zonal_stats_vector(wards, water_gdf, "waterbody")
    road_stats = zonal_stats_vector(wards, roads_gdf, "road")
    
    all_stats = pd.concat([
        wards[["ward_id", "ward_number", "ward_name", "area_sqkm"]].reset_index(drop=True),
        dem_stats.reset_index(drop=True),
        slope_stats.reset_index(drop=True),
        lulc_fracs.reset_index(drop=True),
        water_dist.reset_index(drop=True),
        road_density.reset_index(drop=True),
        underpass_count.reset_index(drop=True),
        water_stats.reset_index(drop=True),
        road_stats.reset_index(drop=True),
    ], axis=1)
    
    all_stats.to_parquet(output_path, index=False)
    logger.info("Zonal stats saved", path=str(output_path), shape=all_stats.shape)

if __name__ == "__main__":
    main()