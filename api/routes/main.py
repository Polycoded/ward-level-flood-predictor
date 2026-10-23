from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import geopandas as gpd
import pandas as pd
from pathlib import Path
import structlog

from api.schemas import (
    WardResponse, WardFeatureResponse, WardRiskResponse, 
    RiskResponse, RainfallInput, ScenarioInput,
    ValidationMetrics, AlertRequest, AlertResponse, AlertMessage,
    ShelterRequest, ShelterResponse, RoadRiskResponse,
    HealthResponse, ReadyResponse, ErrorResponse,
    RiskLevel, DepthBand, Language, AlertChannel
)

router = APIRouter(prefix="/api/v1", tags=["wards", "risk", "alerts", "shelters", "roads"])
logger = structlog.get_logger()

FEATURES_PATH = Path("data/processed/features.parquet")
WARDS_PATH = Path("data/processed/wards.geojson")
VALIDATION_PATH = Path("data/processed/validation_metrics.json")
SHELTERS_PATH = Path("data/processed/shelters.parquet")
ROADS_PATH = Path("data/processed/roads.gpkg")
UNDERPASSES_PATH = Path("data/processed/underpasses.gpkg")

_features_cache: Optional[gpd.GeoDataFrame] = None
_wards_cache: Optional[gpd.GeoDataFrame] = None
_shelters_cache: Optional[gpd.GeoDataFrame] = None
_roads_cache: Optional[gpd.GeoDataFrame] = None
_underpasses_cache: Optional[gpd.GeoDataFrame] = None


def load_features() -> gpd.GeoDataFrame:
    global _features_cache
    if _features_cache is None:
        if not FEATURES_PATH.exists():
            raise HTTPException(status_code=503, detail="Features not available. Run pipeline first.")
        _features_cache = gpd.read_parquet(FEATURES_PATH)
    return _features_cache


def load_wards() -> gpd.GeoDataFrame:
    global _wards_cache
    if _wards_cache is None:
        if not WARDS_PATH.exists():
            raise HTTPException(status_code=503, detail="Wards not available. Run pipeline first.")
        _wards_cache = gpd.read_file(WARDS_PATH)
    return _wards_cache


def load_shelters() -> gpd.GeoDataFrame:
    global _shelters_cache
    if _shelters_cache is None:
        if not SHELTERS_PATH.exists():
            return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        _shelters_cache = gpd.read_parquet(SHELTERS_PATH)
    return _shelters_cache


def load_roads() -> gpd.GeoDataFrame:
    global _roads_cache
    if _roads_cache is None:
        if not ROADS_PATH.exists():
            return gpd.GeoDataFrame(geometry=[], crs="EPSG:32644")
        _roads_cache = gpd.read_file(ROADS_PATH)
    return _roads_cache


def load_underpasses() -> gpd.GeoDataFrame:
    global _underpasses_cache
    if _underpasses_cache is None:
        if not UNDERPASSES_PATH.exists():
            return gpd.GeoDataFrame(geometry=[], crs="EPSG:32644")
        _underpasses_cache = gpd.read_file(UNDERPASSES_PATH)
    return _underpasses_cache


@router.get("/healthz", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        timestamp=pd.Timestamp.now()
    )


@router.get("/readyz", response_model=ReadyResponse)
async def ready_check():
    checks = {
        "features": FEATURES_PATH.exists(),
        "wards": WARDS_PATH.exists(),
        "validation": VALIDATION_PATH.exists(),
        "shelters": SHELTERS_PATH.exists(),
        "roads": ROADS_PATH.exists(),
    }
    return ReadyResponse(
        ready=all(checks.values()),
        checks=checks,
        timestamp=pd.Timestamp.now()
    )


@router.get("/wards", response_model=List[WardResponse])
async def list_wards():
    wards = load_wards()
    wards_wgs84 = wards.to_crs("EPSG:4326")
    return [
        WardResponse(
            ward_id=int(row.ward_id),
            ward_number=str(row.ward_number),
            ward_name=str(row.ward_name),
            area_sqkm=float(row.area_sqkm),
            geometry=row.geometry.__geo_interface__ if row.geometry else None
        )
        for _, row in wards_wgs84.iterrows()
    ]


# Declared before /wards/{ward_id}; otherwise FastAPI tries to parse "geojson" as an int.
@router.get("/wards/geojson")
async def get_wards_geojson():
    wards = load_wards()
    wards_wgs84 = wards.to_crs("EPSG:4326")
    return wards_wgs84.__geo_interface__


@router.get("/wards/{ward_id}", response_model=WardFeatureResponse)
async def get_ward(ward_id: int):
    features = load_features()
    ward = features[features.ward_id == ward_id]
    if len(ward) == 0:
        raise HTTPException(status_code=404, detail="Ward not found")
    
    row = ward.iloc[0]
    ward_wgs84 = ward.to_crs("EPSG:4326")
    geom = ward_wgs84.iloc[0].geometry
    
    return WardFeatureResponse(
        ward_id=int(row.ward_id),
        ward_number=str(row.ward_number),
        ward_name=str(row.ward_name),
        area_sqkm=float(row.area_sqkm),
        elevation_mean=float(row.elevation_mean),
        slope_mean=float(row.slope_mean),
        impervious_frac=float(row.impervious_frac),
        water_frac=float(row.water_frac),
        vegetation_frac=float(row.vegetation_frac),
        dist_to_water_m=float(row.dist_to_water_m),
        road_density_km_per_sqkm=float(row.road_density_km_per_sqkm),
        underpass_count=int(row.underpass_count),
        flood_prone_index=float(row.flood_prone_index),
        geometry=geom.__geo_interface__ if geom else None
    )


def compute_risk_score(row: pd.Series, rainfall_mm: float, builtup_increase: float = 0.0, duration_hours: float = 3.0) -> tuple:
    from model.risk_engine import score_ward
    return score_ward(row, rainfall_mm, builtup_increase, duration_hours=duration_hours)


@router.post("/risk", response_model=RiskResponse)
async def get_risk(input_data: RainfallInput):
    features = load_features()
    
    results = []
    for _, row in features.iterrows():
        risk_score, risk_level, depth_band, peak_window, reasons = compute_risk_score(
            row, input_data.rainfall_mm, duration_hours=input_data.duration_hours
        )

        feature_dict = {
            "elevation_mean": float(row.elevation_mean),
            "slope_mean": float(row.slope_mean),
            "impervious_frac": float(row.impervious_frac),
            "water_frac": float(row.water_frac),
            "dist_to_water_m": float(row.dist_to_water_m),
            "road_density": float(row.road_density_km_per_sqkm),
            "underpass_count": int(row.underpass_count),
        }
        
        results.append(WardRiskResponse(
            ward_id=int(row.ward_id),
            ward_number=str(row.ward_number),
            ward_name=str(row.ward_name),
            risk_score=risk_score,
            risk_level=risk_level,
            depth_band=depth_band,
            peak_window_hours=peak_window,
            reasons=reasons,
            features=feature_dict
        ))
    
    results.sort(key=lambda x: x.risk_score, reverse=True)
    
    return RiskResponse(
        scenario=input_data,
        wards=results,
        generated_at=pd.Timestamp.now(),
        model_version="0.1.0"
    )


@router.post("/scenario", response_model=RiskResponse)
async def get_scenario_risk(input_data: ScenarioInput):
    features = load_features()
    
    results = []
    for _, row in features.iterrows():
        risk_score, risk_level, depth_band, peak_window, reasons = compute_risk_score(
            row, input_data.rainfall_mm, input_data.builtup_increase_pct, duration_hours=input_data.duration_hours
        )
        
        feature_dict = {
            "elevation_mean": float(row.elevation_mean),
            "slope_mean": float(row.slope_mean),
            "impervious_frac": float(row.impervious_frac),
            "water_frac": float(row.water_frac),
            "dist_to_water_m": float(row.dist_to_water_m),
            "road_density": float(row.road_density_km_per_sqkm),
            "underpass_count": int(row.underpass_count),
        }
        
        results.append(WardRiskResponse(
            ward_id=int(row.ward_id),
            ward_number=str(row.ward_number),
            ward_name=str(row.ward_name),
            risk_score=risk_score,
            risk_level=risk_level,
            depth_band=depth_band,
            peak_window_hours=peak_window,
            reasons=reasons,
            features=feature_dict
        ))
    
    results.sort(key=lambda x: x.risk_score, reverse=True)
    
    scenario = RainfallInput(
        rainfall_mm=input_data.rainfall_mm,
        duration_hours=input_data.duration_hours,
        scenario_name=f"+{input_data.builtup_increase_pct}% built-up"
    )
    
    return RiskResponse(
        scenario=scenario,
        wards=results,
        generated_at=pd.Timestamp.now(),
        model_version="0.1.0"
    )


@router.get("/validation", response_model=ValidationMetrics)
async def get_validation():
    from api.validation_status import validation_status
    return validation_status(VALIDATION_PATH)


@router.post("/alerts", response_model=AlertResponse)
async def generate_alerts(request: AlertRequest):
    from model.alerts import generate_alert_messages
    
    features = load_features()
    wards = features[features.ward_id.isin(request.ward_ids)]
    
    if len(wards) == 0:
        raise HTTPException(status_code=404, detail="No wards found")
    
    alerts = []
    for _, row in wards.iterrows():
        risk_score, risk_level, depth_band, peak_window, reasons = compute_risk_score(
            row, request.rainfall_mm
        )
        
        for channel in request.channels:
            message, deeplink = generate_alert_messages(
                ward_name=row.ward_name,
                risk_level=risk_level.value,
                depth_band=depth_band.value,
                rainfall_mm=request.rainfall_mm,
                language=request.language.value,
                channel=channel.value
            )
            
            alerts.append(AlertMessage(
                ward_id=int(row.ward_id),
                ward_name=str(row.ward_name),
                channel=channel,
                language=request.language,
                message=message,
                whatsapp_deeplink=deeplink
            ))
    
    return AlertResponse(
        alerts=alerts,
        sent_at=pd.Timestamp.now()
    )


@router.post("/shelters", response_model=List[ShelterResponse])
async def find_shelters(request: ShelterRequest):
    from model.shelters import find_nearest_shelters
    
    shelters = load_shelters()
    if len(shelters) == 0:
        return []
    
    results = find_nearest_shelters(
        latitude=request.latitude,
        longitude=request.longitude,
        shelters_gdf=shelters,
        max_distance_km=request.max_distance_km,
        max_results=request.max_results
    )
    
    return [
        ShelterResponse(
            shelter_id=int(r["shelter_id"]),
            name=r["name"],
            latitude=r["latitude"],
            longitude=r["longitude"],
            capacity=int(r["capacity"]),
            distance_km=r["distance_km"],
            walking_time_min=r["walking_time_min"],
            route_geometry=r.get("route_geometry")
        )
        for r in results
    ]


@router.get("/roads/risk", response_model=List[RoadRiskResponse])
async def get_road_risk(rainfall_mm: float = Query(..., ge=0, le=500)):
    from model.road_risk import score_roads
    
    roads = load_roads()
    underpasses = load_underpasses()
    features = load_features()
    
    if len(roads) == 0:
        return []
    
    results = score_roads(roads, underpasses, features, rainfall_mm)
    
    return [
        RoadRiskResponse(
            road_id=str(r["road_id"]),
            name=r["name"],
            highway_type=r["highway_type"],
            risk_score=r["risk_score"],
            risk_level=r["risk_level"],
            is_underpass=r["is_underpass"],
            flood_depth_estimate_m=r["flood_depth_estimate_m"],
            geometry=r["geometry"]
        )
        for r in results
    ]
