from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class RiskLevel(str, Enum):
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class DepthBand(str, Enum):
    NONE = "none"
    LOW = "0-0.15m"
    MEDIUM = "0.15-0.5m"
    HIGH = "0.5-1.0m"
    VERY_HIGH = "1.0m+"


class AlertChannel(str, Enum):
    SMS = "sms"
    WHATSAPP = "whatsapp"
    VOICE = "voice"
    LIVEKIT = "livekit"


class Language(str, Enum):
    ENGLISH = "en"
    TAMIL = "ta"


class WardBase(BaseModel):
    ward_id: int
    ward_number: str
    ward_name: str
    area_sqkm: float


class WardResponse(WardBase):
    geometry: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class WardFeatureResponse(BaseModel):
    ward_id: int
    ward_number: str
    ward_name: str
    area_sqkm: float
    elevation_mean: float
    slope_mean: float
    impervious_frac: float
    water_frac: float
    vegetation_frac: float
    dist_to_water_m: float
    road_density_km_per_sqkm: float
    underpass_count: int
    flood_prone_index: float
    geometry: Optional[Dict[str, Any]] = None


class RainfallInput(BaseModel):
    rainfall_mm: float = Field(..., ge=0, le=500, description="Total rainfall accumulation in mm over duration_hours")
    duration_hours: float = Field(default=3.0, ge=1, le=24, description="Duration in hours")
    scenario_name: Optional[str] = Field(default=None, max_length=100)


class ScenarioInput(BaseModel):
    rainfall_mm: float = Field(..., ge=0, le=500)
    duration_hours: float = Field(default=3.0, ge=1, le=24)
    builtup_increase_pct: float = Field(default=0.0, ge=0, le=100, description="Percentage increase in built-up area")


class WardRiskResponse(BaseModel):
    ward_id: int
    ward_number: str
    ward_name: str
    risk_score: float = Field(..., ge=0, le=1)
    risk_level: RiskLevel
    depth_band: DepthBand
    peak_window_hours: int
    reasons: List[str]
    features: Dict[str, float]


class RiskResponse(BaseModel):
    scenario: RainfallInput
    wards: List[WardRiskResponse]
    generated_at: datetime
    model_version: str


def _unique(items: list) -> list:
    return list(dict.fromkeys(items))


class AlertRequest(BaseModel):
    # Bounded so one small request cannot make the server build a huge response
    # (200 wards x 1000 duplicate channels used to return 43 MB).
    ward_ids: List[int] = Field(..., min_length=1, max_length=200)
    rainfall_mm: float = Field(..., ge=0, le=500)
    language: Language = Language.ENGLISH
    channels: List[AlertChannel] = Field(
        default=[AlertChannel.SMS, AlertChannel.WHATSAPP], min_length=1, max_length=4
    )

    @field_validator("ward_ids", "channels")
    @classmethod
    def drop_duplicates(cls, v: list) -> list:
        return _unique(v)


class AlertMessage(BaseModel):
    ward_id: int
    ward_name: str
    channel: AlertChannel
    language: Language
    message: str
    whatsapp_deeplink: Optional[str] = None


class AlertResponse(BaseModel):
    alerts: List[AlertMessage]
    sent_at: datetime


class EvidenceMetric(BaseModel):
    model_config = ConfigDict(strict=True, allow_inf_nan=False, extra="allow")
    value: float | None = Field(ge=0, le=1)
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    unavailable_reason: str | None

    @model_validator(mode="after")
    def check_availability(self):
        if self.value is None and not self.unavailable_reason:
            raise ValueError("Null metrics require an unavailability reason")
        if self.value is not None and (self.denominator == 0 or self.unavailable_reason):
            raise ValueError("Available metrics require a denominator and no unavailable reason")
        return self


class ValidationMetrics(BaseModel):
    """Evidence-status envelope; no legacy accuracy defaults."""
    model_config = ConfigDict(strict=True, allow_inf_nan=False, extra="allow")
    schema_version: Literal["2.0"] = "2.0"
    status: Literal["unavailable", "partial", "evaluated"]
    status_reason: str | None = None
    metrics: Dict[str, EvidenceMetric] | None = None
    coverage: Dict[str, EvidenceMetric] | None = None
    event_metadata: Dict[str, Any] | None = None
    warnings: List[str] = Field(default_factory=list)


class ShelterResponse(BaseModel):
    shelter_id: int
    name: str
    latitude: float
    longitude: float
    capacity: int
    distance_km: float
    walking_time_min: int
    route_geometry: Optional[Dict[str, Any]] = None


class ShelterRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    max_distance_km: float = Field(default=5.0, gt=0, le=50)
    max_results: int = Field(default=5, ge=1, le=50)


class RoadRiskResponse(BaseModel):
    road_id: str
    name: str
    highway_type: str
    risk_score: float
    risk_level: RiskLevel
    is_underpass: bool
    flood_depth_estimate_m: float
    geometry: Dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime


class ReadyResponse(BaseModel):
    ready: bool
    checks: Dict[str, bool]
    timestamp: datetime


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime
