// Offline stand-in for the FastAPI backend. Used when the API is unreachable or
// not ready (no features.parquet yet), or when VITE_USE_MOCK=true.
// Ward polygons are a synthetic grid over Chennai, NOT real ward boundaries.
// Scoring mirrors model/risk_engine.py so the UI behaves like the real thing.

import type {
  Ward,
  WardFeature,
  WardRisk,
  RiskResponse,
  RainfallInput,
  ScenarioInput,
  AlertChannel,
  AlertMessage,
  AlertResponse,
  ValidationMetrics,
  Shelter,
  RoadRisk,
  RiskLevel,
  DepthBand,
  Language,
  HealthResponse,
  ReadyResponse,
} from '../types';
import { baseSusceptibility, rainfallFactor, toFactorInputs } from '../lib/explain';
import { whatsAppShareUrl } from '../lib/safe';

function mulberry32(seed: number) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
const KM_PER_DEG_LAT = 111;
const KM_PER_DEG_LNG = 108;

// Greater Chennai Corporation's 15 zones, roughly north to south.
const ZONES = [
  'Tiruvottiyur', 'Manali', 'Madhavaram', 'Tondiarpet', 'Royapuram',
  'Thiru Vi Ka Nagar', 'Ambattur', 'Anna Nagar', 'Teynampet', 'Kodambakkam',
  'Valasaravakkam', 'Alandur', 'Adyar', 'Perungudi', 'Sholinganallur',
];

const ROWS = 20;
const COLS = 10;
const LAT_MIN = 12.9;
const LAT_MAX = 13.22;
const LNG_WEST = 80.16;
const coastLng = (lat: number) => 80.25 + (lat - LAT_MIN) * 0.12;

const RIVERS_LAT = [13.075 /* Cooum */, 13.015 /* Adyar */, 13.2 /* Kosasthalaiyar */];
const MARSH = { lat: 12.95, lng: 80.215 }; // Pallikaranai / Velachery low-lying belt
const CBD = { lat: 13.06, lng: 80.25 };

function buildWards(): WardFeature[] {
  const rand = mulberry32(42);
  const wards: WardFeature[] = [];
  const latStep = (LAT_MAX - LAT_MIN) / ROWS;

  for (let r = 0; r < ROWS; r++) {
    const south = LAT_MAX - (r + 1) * latStep;
    const north = LAT_MAX - r * latStep;
    const midLat = (south + north) / 2;
    const east = coastLng(midLat);
    const lngStep = (east - LNG_WEST) / COLS;

    for (let c = 0; c < COLS; c++) {
      const id = r * COLS + c + 1;
      const west = LNG_WEST + c * lngStep;
      const lng = west + lngStep / 2;
      const zone = ZONES[Math.min(ZONES.length - 1, Math.floor((id - 1) / (ROWS * COLS / ZONES.length)))];

      const inlandKm = (coastLng(midLat) - lng) * KM_PER_DEG_LNG;
      const riverKm = Math.min(...RIVERS_LAT.map((rl) => Math.abs(midLat - rl) * KM_PER_DEG_LAT));
      const canalKm = Math.abs(inlandKm - 1.2);
      const waterKm = Math.min(riverKm, inlandKm, canalKm);
      const marshKm = Math.hypot((midLat - MARSH.lat) * KM_PER_DEG_LAT, (lng - MARSH.lng) * KM_PER_DEG_LNG);
      const cbdKm = Math.hypot((midLat - CBD.lat) * KM_PER_DEG_LAT, (lng - CBD.lng) * KM_PER_DEG_LNG);

      const elevation = clamp(
        1.5 + inlandKm * 1.3 - 2 * Math.exp(-riverKm) - 4 * Math.exp(-marshKm / 2) + (rand() * 2.5 - 1),
        0.5,
        30
      );
      const impervious = clamp(0.88 - cbdKm * 0.025 + (rand() * 0.16 - 0.08), 0.2, 0.95);
      const water = clamp(0.02 + 0.15 * Math.exp(-waterKm) + rand() * 0.03, 0, 0.4);
      const area = (latStep * KM_PER_DEG_LAT) * (lngStep * KM_PER_DEG_LNG);

      const ward: WardFeature = {
        ward_id: id,
        ward_number: String(id),
        ward_name: `${zone} ${((id - 1) % 13) + 1}`,
        area_sqkm: Number(area.toFixed(2)),
        geometry: {
          type: 'Polygon',
          coordinates: [[[west, south], [west + lngStep, south], [west + lngStep, north], [west, north], [west, south]]],
        },
        elevation_mean: Number(elevation.toFixed(1)),
        slope_mean: Number((0.3 + rand() * 2.2 + inlandKm * 0.08).toFixed(2)),
        impervious_frac: Number(impervious.toFixed(3)),
        water_frac: Number(water.toFixed(3)),
        vegetation_frac: Number(clamp((1 - impervious - water) * 0.7, 0.02, 0.6).toFixed(3)),
        dist_to_water_m: Math.round(waterKm * 1000),
        road_density_km_per_sqkm: Number((4 + impervious * 14 + rand() * 3).toFixed(1)),
        underpass_count: rand() < 0.18 ? 1 + Math.floor(rand() * 2) : 0,
        flood_prone_index: 0,
      };
      ward.flood_prone_index = Number(baseScore(ward, 0).toFixed(3));
      wards.push(ward);
    }
  }
  return wards;
}

// --- port of model/risk_engine.py -------------------------------------------

const baseScore = (w: WardFeature, builtupIncrease: number) =>
  baseSusceptibility(toFactorInputs(w as unknown as Record<string, number>), builtupIncrease);

const RISK_THRESHOLDS: [RiskLevel, number][] = [
  ['very_low', 0.2], ['low', 0.35], ['moderate', 0.55], ['high', 0.75], ['very_high', Infinity],
];
const DEPTH_THRESHOLDS: [DepthBand, number][] = [
  ['none', 0.01], ['0-0.15m', 0.15], ['0.15-0.5m', 0.5], ['0.5-1.0m', 1.0], ['1.0m+', Infinity],
];

function reasonsFor(w: WardFeature, rainfallMm: number): string[] {
  const reasons: string[] = [];
  if (w.elevation_mean < 5) reasons.push(`Low mean elevation (${w.elevation_mean.toFixed(1)}m) increases flood susceptibility`);
  if (w.slope_mean < 1.5) reasons.push(`Very flat terrain (mean slope ${w.slope_mean.toFixed(1)}°) limits drainage`);
  if (w.impervious_frac > 0.6) reasons.push(`High impervious surface fraction (${Math.round(w.impervious_frac * 100)}%) reduces infiltration`);
  if (w.dist_to_water_m < 500) reasons.push(`Close to water body (${w.dist_to_water_m}m) - backflow risk`);
  if (w.underpass_count > 0) reasons.push(`Contains ${w.underpass_count} underpass(es) - high flood risk`);
  if (w.road_density_km_per_sqkm > 15) reasons.push(`High road density (${w.road_density_km_per_sqkm.toFixed(1)} km/km²) indicates dense urbanization`);
  if (rainfallMm > 150) reasons.push(`High rainfall forecast (${rainfallMm}mm) exceeds drainage capacity`);
  else if (rainfallMm > 75) reasons.push(`Moderate rainfall forecast (${rainfallMm}mm) may overwhelm low-lying areas`);
  if (reasons.length === 0) reasons.push('No single dominant risk factor; composite score drives assessment');
  return reasons;
}

export function scoreWard(w: WardFeature, rainfallMm: number, builtupIncrease = 0): WardRisk {
  const rf = rainfallFactor(rainfallMm);
  const risk_score = Math.min(baseScore(w, builtupIncrease) * rf, 1);
  const risk_level = RISK_THRESHOLDS.find(([, hi]) => risk_score < hi)![0];
  const depthM = (risk_score * 150 * rf) / 100;
  const depth_band = DEPTH_THRESHOLDS.find(([, hi]) => depthM < hi)![0];

  return {
    ward_id: w.ward_id,
    ward_number: w.ward_number,
    ward_name: w.ward_name,
    risk_score,
    risk_level,
    depth_band,
    peak_window_hours: Math.max(1, Math.floor(3 * (1 + risk_score))),
    reasons: reasonsFor(w, rainfallMm),
    features: {
      elevation_mean: w.elevation_mean,
      slope_mean: w.slope_mean,
      impervious_frac: w.impervious_frac,
      water_frac: w.water_frac,
      dist_to_water_m: w.dist_to_water_m,
      road_density: w.road_density_km_per_sqkm,
      underpass_count: w.underpass_count,
    },
  };
}

// --- alerts ------------------------------------------------------------------

const ALERT_TEMPLATES: Record<Language, Record<RiskLevel, string>> = {
  en: {
    very_low: 'No significant flood risk expected for {ward}. Rainfall: {mm}mm.',
    low: 'Low flood risk for {ward}. Minor waterlogging possible. Rainfall: {mm}mm. Stay alert.',
    moderate: 'Moderate flood risk for {ward}. Waterlogging expected up to {depth}. Rainfall: {mm}mm. Avoid low-lying areas.',
    high: 'HIGH FLOOD RISK for {ward}. Significant waterlogging up to {depth} expected. Rainfall: {mm}mm. Move to higher ground if needed.',
    very_high: 'SEVERE FLOOD WARNING for {ward}. Dangerous flooding up to {depth} expected. Rainfall: {mm}mm. EVACUATE if advised by authorities.',
  },
  // Needs a native-speaker review before the demo.
  ta: {
    very_low: '{ward}: குறிப்பிடத்தக்க வெள்ள அபாயம் இல்லை. மழை: {mm} மி.மீ.',
    low: '{ward}: குறைந்த வெள்ள அபாயம். லேசான நீர் தேக்கம் இருக்கலாம். மழை: {mm} மி.மீ. விழிப்புடன் இருங்கள்.',
    moderate: '{ward}: மிதமான வெள்ள அபாயம். {depth} வரை நீர் தேங்கலாம். மழை: {mm} மி.மீ. தாழ்வான பகுதிகளைத் தவிர்க்கவும்.',
    high: '{ward}: அதிக வெள்ள அபாயம்! {depth} வரை நீர் தேங்கும். மழை: {mm} மி.மீ. தேவைப்பட்டால் மேடான இடத்திற்குச் செல்லவும்.',
    very_high: '{ward}: கடும் வெள்ள எச்சரிக்கை! {depth} வரை ஆபத்தான வெள்ளம். மழை: {mm} மி.மீ. அதிகாரிகள் அறிவுறுத்தினால் உடனே வெளியேறவும்.',
  },
};

const DEPTH_WORDS: Record<Language, Record<DepthBand, string>> = {
  en: { none: 'no flooding', '0-0.15m': 'ankle-deep', '0.15-0.5m': 'knee-deep', '0.5-1.0m': 'waist-deep', '1.0m+': 'over 1 metre' },
  ta: { none: 'வெள்ளம் இல்லை', '0-0.15m': 'கணுக்கால் அளவு', '0.15-0.5m': 'முழங்கால் அளவு', '0.5-1.0m': 'இடுப்பு அளவு', '1.0m+': '1 மீட்டருக்கு மேல்' },
};

// --- shelters ----------------------------------------------------------------

const SHELTERS = [
  { name: 'Corporation Higher Sec. School, Tiruvottiyur', lat: 13.16, lng: 80.3, capacity: 400 },
  { name: 'Community Hall, Tondiarpet', lat: 13.125, lng: 80.285, capacity: 250 },
  { name: 'Corporation School, Perambur', lat: 13.115, lng: 80.235, capacity: 350 },
  { name: 'Community Hall, Anna Nagar', lat: 13.085, lng: 80.21, capacity: 300 },
  { name: 'Corporation School, Choolaimedu', lat: 13.065, lng: 80.225, capacity: 280 },
  { name: 'Marriage Hall Relief Centre, Mylapore', lat: 13.035, lng: 80.265, capacity: 500 },
  { name: 'Corporation School, Saidapet', lat: 13.022, lng: 80.225, capacity: 320 },
  { name: 'Community Hall, Adyar', lat: 13.005, lng: 80.255, capacity: 260 },
  { name: 'Corporation School, Velachery', lat: 12.978, lng: 80.22, capacity: 450 },
  { name: 'Relief Centre, Perungudi', lat: 12.965, lng: 80.245, capacity: 300 },
  { name: 'Community Hall, Valasaravakkam', lat: 13.04, lng: 80.175, capacity: 220 },
  { name: 'Corporation School, Sholinganallur', lat: 12.9, lng: 80.23, capacity: 380 },
];

function haversineKm(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(a));
}

// --- roads & underpasses -----------------------------------------------------

// One east-west arterial segment through every third ward plus one short segment
// per underpass, scored from the ward they sit in.
function mockRoads(rainfallMm: number): RoadRisk[] {
  const roads: RoadRisk[] = [];
  for (const w of allWards()) {
    const ring = (w.geometry as GeoJSON.Polygon).coordinates[0];
    const [west, south] = ring[0];
    const [east, north] = ring[2];
    const midLat = (south + north) / 2;
    const midLng = (west + east) / 2;
    const wardRisk = scoreWard(w, rainfallMm);
    const depthM = (wardRisk.risk_score * 150 * rainfallFactor(rainfallMm)) / 100;

    const push = (id: string, name: string, coords: number[][], isUnderpass: boolean) => {
      const risk_score = Math.min(wardRisk.risk_score * (isUnderpass ? 1.3 : 1), 1);
      roads.push({
        road_id: id,
        name,
        highway_type: isUnderpass ? 'primary' : 'secondary',
        risk_score,
        risk_level: RISK_THRESHOLDS.find(([, hi]) => risk_score < hi)![0],
        is_underpass: isUnderpass,
        flood_depth_estimate_m: Number((depthM * (isUnderpass ? 1.5 : 1)).toFixed(2)),
        geometry: { type: 'LineString', coordinates: coords },
      });
    };

    if (w.ward_id % 3 === 0) {
      push(`road-${w.ward_id}`, `Arterial road, ${w.ward_name}`, [[west, midLat], [east, midLat]], false);
    }
    for (let u = 0; u < w.underpass_count; u++) {
      const dLng = (east - west) * (0.15 + 0.3 * u);
      push(
        `underpass-${w.ward_id}-${u}`,
        `Underpass ${u + 1}, ${w.ward_name}`,
        [[midLng - dLng / 4, midLat + (north - south) * 0.2], [midLng + dLng / 4, midLat + (north - south) * 0.2]],
        true
      );
    }
  }
  return roads.sort((a, b) => b.risk_score - a.risk_score);
}

// --- public mock API (same shape as ApiClient) -------------------------------

let wardCache: WardFeature[] | null = null;
const allWards = () => (wardCache ??= buildWards());

function findWard(wardId: number): WardFeature {
  const ward = allWards().find((w) => w.ward_id === wardId);
  if (!ward) throw new Error(`Ward ${wardId} not found`);
  return ward;
}

function riskResponse(input: RainfallInput, builtupIncrease = 0): RiskResponse {
  return {
    scenario: input,
    wards: allWards()
      .map((w) => scoreWard(w, input.rainfall_mm, builtupIncrease))
      .sort((a, b) => b.risk_score - a.risk_score),
    generated_at: new Date().toISOString(),
    model_version: '0.1.0-mock',
  };
}

export const mockApi = {
  healthCheck: (): HealthResponse => ({ status: 'healthy', version: '0.1.0-mock', timestamp: new Date().toISOString() }),

  readyCheck: (): ReadyResponse => ({
    ready: true,
    checks: { features: true, wards: true, validation: true, shelters: true, roads: true },
    timestamp: new Date().toISOString(),
  }),

  getWards: (): Ward[] =>
    allWards().map(({ ward_id, ward_number, ward_name, area_sqkm, geometry }) => ({
      ward_id, ward_number, ward_name, area_sqkm, geometry,
    })),

  getWard: (wardId: number): WardFeature => findWard(wardId),

  getWardsGeoJSON: (): GeoJSON.FeatureCollection => ({
    type: 'FeatureCollection',
    features: allWards().map(({ geometry, ...props }) => ({ type: 'Feature', properties: props, geometry: geometry! })),
  }),

  getRisk: (input: RainfallInput): RiskResponse => riskResponse(input),

  getScenarioRisk: (input: ScenarioInput): RiskResponse => riskResponse(input, input.builtup_increase_pct),

  getValidation: (): ValidationMetrics => ({
    precision_at_20: 0.65,
    recall: 13 / 18,
    false_positive_rate: 7 / 182,
    true_positives: 13,
    false_positives: 7,
    false_negatives: 5,
    total_flooded_wards: 18,
    total_wards: 200,
    event_date: '2023-12-04',
    notes: 'MOCK NUMBERS: placeholder until validation_metrics.json from the real Dec 2023 run is committed.',
  }),

  generateAlerts: (
    wardIds: number[],
    rainfallMm: number,
    language: Language = 'en',
    channels: AlertChannel[] = ['sms', 'whatsapp']
  ): AlertResponse => {
    const alerts: AlertMessage[] = [];
    for (const wardId of wardIds) {
      const ward = findWard(wardId);
      const risk = scoreWard(ward, rainfallMm);
      const fullMessage = ALERT_TEMPLATES[language][risk.risk_level]
        .replace('{ward}', ward.ward_name)
        .replace('{depth}', DEPTH_WORDS[language][risk.depth_band])
        .replace('{mm}', rainfallMm.toFixed(0));

      for (const channel of channels) {
        const message =
          channel === 'sms' && language === 'en' && fullMessage.length > 160 ? fullMessage.slice(0, 157) + '...' : fullMessage;
        alerts.push({
          ward_id: ward.ward_id,
          ward_name: ward.ward_name,
          channel,
          language,
          message,
          whatsapp_deeplink: channel === 'whatsapp' ? whatsAppShareUrl(message) : undefined,
        });
      }
    }
    return { alerts, sent_at: new Date().toISOString() };
  },

  findShelters: (latitude: number, longitude: number, maxDistanceKm = 5, maxResults = 5): Shelter[] =>
    SHELTERS.map((s, i) => {
      const distance_km = haversineKm(latitude, longitude, s.lat, s.lng);
      return {
        shelter_id: i + 1,
        name: s.name,
        latitude: s.lat,
        longitude: s.lng,
        capacity: s.capacity,
        distance_km: Number(distance_km.toFixed(2)),
        // straight-line distance x1.3 detour factor at 4.5 km/h walking pace
        walking_time_min: Math.round(((distance_km * 1.3) / 4.5) * 60),
        route_geometry: { type: 'LineString', coordinates: [[longitude, latitude], [s.lng, s.lat]] } as GeoJSON.Geometry,
      };
    })
      .filter((s) => s.distance_km <= maxDistanceKm)
      .sort((a, b) => a.distance_km - b.distance_km)
      .slice(0, maxResults),

  getRoadRisk: (rainfallMm: number): RoadRisk[] => mockRoads(rainfallMm),
};
