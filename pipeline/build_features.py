import pandas as pd
import geopandas as gpd
from pathlib import Path
import structlog

logger = structlog.get_logger()

FEATURE_SCHEMA = {
    "ward_id": "int64",
    "ward_number": "string",
    "ward_name": "string",
    "area_sqkm": "float64",
    "elevation_mean": "float64",
    "elevation_std": "float64",
    "elevation_min": "float64",
    "elevation_max": "float64",
    "elevation_p10": "float64",
    "elevation_p50": "float64",
    "elevation_p90": "float64",
    "slope_mean": "float64",
    "slope_std": "float64",
    "slope_min": "float64",
    "slope_max": "float64",
    "slope_p10": "float64",
    "slope_p50": "float64",
    "slope_p90": "float64",
    "lulc_frac_10": "float64",
    "lulc_frac_20": "float64",
    "lulc_frac_30": "float64",
    "lulc_frac_40": "float64",
    "lulc_frac_50": "float64",
    "lulc_frac_60": "float64",
    "lulc_frac_80": "float64",
    "lulc_frac_90": "float64",
    "lulc_frac_95": "float64",
    "impervious_frac": "float64",
    "water_frac": "float64",
    "vegetation_frac": "float64",
    "dist_to_water_m": "float64",
    "road_density_km_per_sqkm": "float64",
    "underpass_count": "int64",
    "waterbody_count": "int64",
    "waterbody_area_sqkm": "float64",
    "road_count": "int64",
    "road_length_km": "float64",
}

def validate_features(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Validating feature schema")
    
    missing_cols = set(FEATURE_SCHEMA.keys()) - set(df.columns)
    if missing_cols:
        logger.warning("Missing feature columns", missing=list(missing_cols))
        for col in missing_cols:
            dtype = FEATURE_SCHEMA[col]
            if "int" in dtype:
                df[col] = 0
            elif dtype == "string":
                df[col] = ""
            else:
                df[col] = 0.0
    
    extra_cols = set(df.columns) - set(FEATURE_SCHEMA.keys()) - {"geometry"}
    if extra_cols:
        logger.info("Extra columns found (will be kept)", extra=list(extra_cols))
    
    for col, dtype in FEATURE_SCHEMA.items():
        if col in df.columns:
            if "int" in dtype:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")
            elif dtype == "string":
                df[col] = df[col].astype("string").fillna("")
            else:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype("float64")
    
    df = df[sorted(df.columns, key=lambda x: list(FEATURE_SCHEMA.keys()).index(x) if x in FEATURE_SCHEMA else 999)]
    
    logger.info("Feature validation complete", rows=len(df), cols=len(df.columns))
    return df

def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Adding derived features")
    
    df = df.copy()
    
    df["elevation_range"] = df["elevation_max"] - df["elevation_min"]
    df["slope_range"] = df["slope_max"] - df["slope_min"]
    df["low_lying_area_frac"] = ((df["elevation_p10"] < 5.0) & (df["slope_mean"] < 2.0)).astype(float)
    df["flood_prone_index"] = (
        (1 - df["elevation_mean"] / df["elevation_mean"].max()) * 0.3 +
        df["impervious_frac"] * 0.3 +
        (1 - df["dist_to_water_m"] / df["dist_to_water_m"].max()).clip(0, 1) * 0.2 +
        df["slope_mean"].clip(0, 10) / 10 * 0.1 +
        (df["underpass_count"] > 0).astype(float) * 0.1
    )
    
    return df

def main():
    processed_dir = Path("data/processed")
    
    zonal_path = processed_dir / "zonal_stats.parquet"
    wards_path = processed_dir / "wards.geojson"
    output_path = processed_dir / "features.parquet"
    
    if not zonal_path.exists():
        logger.error("Zonal stats not found, run zonal_stats.py first")
        return
    
    logger.info("Loading zonal stats")
    features = pd.read_parquet(zonal_path)
    
    if "geometry" in features.columns:
        features = features.drop(columns=["geometry"])
    
    features = validate_features(features)
    features = add_derived_features(features)
    
    wards = gpd.read_file(wards_path)
    geometry_df = wards[["ward_id", "geometry"]].copy()
    
    features = features.merge(geometry_df, on="ward_id", how="left")
    features = gpd.GeoDataFrame(features, geometry="geometry", crs="EPSG:32644")
    
    features.to_parquet(output_path, index=False)
    logger.info("Features saved", path=str(output_path), shape=features.shape)
    
    schema_path = processed_dir / "feature_schema.yaml"
    import yaml
    with open(schema_path, "w") as f:
        yaml.dump({
            "features": {col: {"type": dtype, "description": ""} 
                        for col, dtype in FEATURE_SCHEMA.items()},
            "derived_features": {
                "elevation_range": {"type": "float64", "description": "Elevation max - min"},
                "slope_range": {"type": "float64", "description": "Slope max - min"},
                "low_lying_area_frac": {"type": "float64", "description": "Fraction of area with elevation <5m and slope <2deg"},
                "flood_prone_index": {"type": "float64", "description": "Composite flood susceptibility index [0,1]"},
            },
            "crs": "EPSG:32644",
            "ward_count": int(len(features)),
        }, f)
    
    logger.info("Feature schema saved", path=str(schema_path))

if __name__ == "__main__":
    main()