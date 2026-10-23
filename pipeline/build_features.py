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
    """Validate supplied measurements without fabricating coverage or mutating input."""
    import numpy as np
    from model.risk_engine import effective_inputs

    if not df.columns.is_unique:
        raise ValueError("Feature columns must be unique")
    missing = set(FEATURE_SCHEMA) - set(df.columns)
    if missing:
        raise ValueError(f"Missing feature columns: {sorted(missing)}")
    result = df.copy(deep=True)
    for col, dtype in FEATURE_SCHEMA.items():
        values = result[col]
        if dtype == "string":
            if values.isna().any() or values.astype(str).str.strip().eq("").any():
                raise ValueError(f"{col} must contain nonempty identities")
            result[col] = values.astype("string")
            continue
        if values.map(lambda v: isinstance(v, (bool, np.bool_))).any():
            raise ValueError(f"{col} cannot contain booleans")
        numeric = pd.to_numeric(values, errors="raise")
        if numeric.isna().any() or not np.isfinite(numeric).all():
            raise ValueError(f"{col} must contain finite measurements")
        if "int" in dtype and ((numeric % 1 != 0).any() or (numeric < 0).any()):
            raise ValueError(f"{col} must contain nonnegative integers")
        if "int" in dtype and (numeric >= 2**63).any():
            raise ValueError(f"{col} exceeds int64 storage range")
        result[col] = numeric.astype(dtype)
    if (result.ward_id <= 0).any() or result.ward_id.duplicated().any():
        raise ValueError("ward_id must be positive and unique")
    if result.ward_number.duplicated().any():
        raise ValueError("ward_number must be unique")
    if (result.area_sqkm <= 0).any():
        raise ValueError("area_sqkm must be positive")
    for _, row in result.iterrows():
        effective_inputs(row, 0)
    return result[sorted(result.columns, key=lambda c: list(FEATURE_SCHEMA).index(c)
                         if c in FEATURE_SCHEMA else 999)]

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
