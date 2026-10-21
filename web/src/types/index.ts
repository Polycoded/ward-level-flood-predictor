export interface Ward {
  ward_id: number;
  ward_number: string;
  ward_name: string;
  area_sqkm: number;
  geometry?: GeoJSON.Geometry;
}

export interface WardFeature extends Ward {
  elevation_mean: number;
  slope_mean: number;
  impervious_frac: number;
  water_frac: number;
  vegetation_frac: number;
  dist_to_water_m: number;
  road_density_km_per_sqkm: number;
  underpass_count: number;
  flood_prone_index: number;
}

export type RiskLevel = 'very_low' | 'low' | 'moderate' | 'high' | 'very_high';
export type DepthBand = 'none' | '0-0.15m' | '0.15-0.5m' | '0.5-1.0m' | '1.0m+';
export type Language = 'en' | 'ta';
export type AlertChannel = 'sms' | 'whatsapp' | 'voice' | 'livekit';

export interface WardRisk {
  ward_id: number;
  ward_number: string;
  ward_name: string;
  risk_score: number;
  risk_level: RiskLevel;
  depth_band: DepthBand;
  peak_window_hours: number;
  reasons: string[];
  features: Record<string, number>;
}

export interface RiskResponse {
  scenario: RainfallInput;
  wards: WardRisk[];
  generated_at: string;
  model_version: string;
}

export interface RainfallInput {
  rainfall_mm: number;
  duration_hours: number;
  scenario_name?: string;
}

export interface ScenarioInput extends RainfallInput {
  builtup_increase_pct: number;
}

export interface AlertMessage {
  ward_id: number;
  ward_name: string;
  channel: AlertChannel;
  language: Language;
  message: string;
  whatsapp_deeplink?: string;
}

export interface AlertResponse {
  alerts: AlertMessage[];
  sent_at: string;
}

export interface ValidationMetrics {
  precision_at_20: number;
  recall: number;
  false_positive_rate: number;
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  total_flooded_wards: number;
  total_wards: number;
  event_date: string;
  notes: string;
}

export interface Shelter {
  shelter_id: number;
  name: string;
  latitude: number;
  longitude: number;
  capacity: number;
  distance_km: number;
  walking_time_min: number;
  route_geometry?: GeoJSON.Geometry;
}

export interface RoadRisk {
  road_id: string;
  name: string;
  highway_type: string;
  risk_score: number;
  risk_level: RiskLevel;
  is_underpass: boolean;
  flood_depth_estimate_m: number;
  geometry: GeoJSON.Geometry;
}

export interface HealthResponse {
  status: string;
  version: string;
  timestamp: string;
}

export interface ReadyResponse {
  ready: boolean;
  checks: Record<string, boolean>;
  timestamp: string;
}

export const RISK_LEVEL_COLORS: Record<RiskLevel, string> = {
  very_low: '#10b981',
  low: '#84cc16',
  moderate: '#f59e0b',
  high: '#f97316',
  very_high: '#ef4444',
};

export const RISK_LEVEL_LABELS: Record<RiskLevel, string> = {
  very_low: 'Very Low',
  low: 'Low',
  moderate: 'Moderate',
  high: 'High',
  very_high: 'Very High',
};

export const DEPTH_BAND_LABELS: Record<DepthBand, string> = {
  none: 'No Flooding',
  '0-0.15m': '0-15 cm (Ankle)',
  '0.15-0.5m': '15-50 cm (Knee)',
  '0.5-1.0m': '50-100 cm (Waist)',
  '1.0m+': '1m+ (Over Head)',
};

export const DEPTH_BAND_COLORS: Record<DepthBand, string> = {
  none: '#10b981',
  '0-0.15m': '#84cc16',
  '0.15-0.5m': '#f59e0b',
  '0.5-1.0m': '#f97316',
  '1.0m+': '#ef4444',
};