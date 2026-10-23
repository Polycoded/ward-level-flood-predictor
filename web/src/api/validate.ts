// Every API response passes through here before the UI sees it. A broken or hostile
// backend (wrong proxy returning HTML, a bad deploy, a tampered response) must produce
// a clear error, never a crashed dashboard or nonsense like "NaN" or "risk 5700".

import type {
  AlertChannel,
  AlertMessage,
  BroadcastAlert,
  AlertResponse,
  DepthBand,
  Language,
  RiskLevel,
  RiskResponse,
  RoadRisk,
  Shelter,
  Subscription,
  SubscriptionChannel,
  ValidationMetrics,
  Ward,
  WardLite,
  WardFeature,
  WardRisk,
} from '../types';
import { classifyRisk } from '../lib/explain';
import { parseValidation } from '../lib/validation';

export class ApiDataError extends Error {
  constructor(what: string) {
    super(`Unexpected data from the server (${what}).`);
  }
}

const LEVELS: RiskLevel[] = ['very_low', 'low', 'moderate', 'high', 'very_high'];
const DEPTHS: DepthBand[] = ['none', '0-0.15m', '0.15-0.5m', '0.5-1.0m', '1.0m+'];
const CHANNELS: AlertChannel[] = ['sms', 'whatsapp', 'voice', 'livekit'];
const LANGUAGES: Language[] = ['en', 'ta'];

const MAX_NAME = 120;
const MAX_REASON = 300;
const MAX_REASONS = 12;
const MAX_MESSAGE = 1000;

type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v);
const finite = (v: unknown): number | null => {
  const n = typeof v === 'string' && v.trim() !== '' ? Number(v) : v;
  return typeof n === 'number' && Number.isFinite(n) ? n : null;
};
const text = (v: unknown, max = MAX_NAME): string | null =>
  typeof v === 'string' || typeof v === 'number' ? String(v).slice(0, max) : null;
const clamp = (n: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, n));
const oneOf = <T extends string>(v: unknown, allowed: readonly T[]): T | null =>
  allowed.includes(v as T) ? (v as T) : null;

function list(v: unknown, what: string): unknown[] {
  if (!Array.isArray(v)) throw new ApiDataError(`${what} is not a list`);
  return v;
}

// --- geometry ---------------------------------------------------------------

function validPosition(p: unknown): boolean {
  return Array.isArray(p) && p.length >= 2 && finite(p[0]) !== null && finite(p[1]) !== null
    && Math.abs(p[0] as number) <= 180 && Math.abs(p[1] as number) <= 90;
}
function validRing(r: unknown): boolean {
  return Array.isArray(r) && r.length >= 4 && r.every(validPosition);
}

/** Returns the geometry only if Leaflet can draw it; Leaflet throws on NaN or bad nesting. */
function polygonGeometry(g: unknown): GeoJSON.Geometry | undefined {
  if (!isObj(g)) return undefined;
  if (g.type === 'Polygon' && Array.isArray(g.coordinates) && g.coordinates.length > 0 && g.coordinates.every(validRing)) {
    return g as unknown as GeoJSON.Polygon;
  }
  if (g.type === 'MultiPolygon' && Array.isArray(g.coordinates) && g.coordinates.length > 0
    && g.coordinates.every((poly) => Array.isArray(poly) && poly.length > 0 && poly.every(validRing))) {
    return g as unknown as GeoJSON.MultiPolygon;
  }
  return undefined;
}

function lineGeometry(g: unknown): GeoJSON.LineString | undefined {
  if (isObj(g) && g.type === 'LineString' && Array.isArray(g.coordinates) && g.coordinates.length >= 2
    && g.coordinates.every(validPosition)) {
    return g as unknown as GeoJSON.LineString;
  }
  return undefined;
}

// --- wards ------------------------------------------------------------------

function wardIdentity(raw: Obj): Pick<Ward, 'ward_id' | 'ward_number' | 'ward_name'> | null {
  const id = finite(raw.ward_id);
  if (id === null || !Number.isInteger(id) || id < 0) return null;
  return {
    ward_id: id,
    ward_number: text(raw.ward_number, 20) ?? String(id),
    ward_name: text(raw.ward_name) ?? `Ward ${id}`,
  };
}

/** Drops entries without a usable id and keeps the first of any duplicate id. */
function uniqueById<T extends { ward_id: number }>(items: (T | null)[]): T[] {
  const seen = new Set<number>();
  return items.filter((w): w is T => w !== null && !seen.has(w.ward_id) && (seen.add(w.ward_id), true));
}

export function validateWards(data: unknown): Ward[] {
  const wards = uniqueById(
    list(data, 'ward list').map((raw) => {
      if (!isObj(raw)) return null;
      const id = wardIdentity(raw);
      if (!id) return null;
      return { ...id, area_sqkm: Math.max(0, finite(raw.area_sqkm) ?? 0), geometry: polygonGeometry(raw.geometry) };
    })
  );
  if (wards.length === 0) throw new ApiDataError('no valid wards');
  return wards;
}

const FEATURE_NUMBERS = [
  'elevation_mean', 'slope_mean', 'impervious_frac', 'water_frac', 'vegetation_frac',
  'dist_to_water_m', 'road_density_km_per_sqkm', 'underpass_count', 'flood_prone_index',
] as const;

export function validateWardFeature(data: unknown): WardFeature {
  if (!isObj(data)) throw new ApiDataError('ward detail is not an object');
  const id = wardIdentity(data);
  if (!id) throw new ApiDataError('ward detail has no id');
  const numbers = {} as Record<(typeof FEATURE_NUMBERS)[number], number>;
  for (const key of FEATURE_NUMBERS) {
    const n = finite(data[key]);
    if (n === null && key !== 'flood_prone_index') throw new ApiDataError(`ward ${key} is missing`);
    numbers[key] = n ?? 0;
  }
  return {
    ...id,
    area_sqkm: Math.max(0, finite(data.area_sqkm) ?? 0),
    geometry: polygonGeometry(data.geometry),
    ...numbers,
    impervious_frac: clamp(numbers.impervious_frac, 0, 1),
    water_frac: clamp(numbers.water_frac, 0, 1),
    vegetation_frac: clamp(numbers.vegetation_frac, 0, 1),
    dist_to_water_m: Math.max(0, numbers.dist_to_water_m),
    underpass_count: Math.max(0, Math.round(numbers.underpass_count)),
    flood_prone_index: clamp(numbers.flood_prone_index, 0, 1),
  };
}

// --- risk -------------------------------------------------------------------

function wardRisk(raw: unknown): WardRisk | null {
  if (!isObj(raw)) return null;
  const id = wardIdentity(raw);
  const score = finite(raw.risk_score);
  if (!id || score === null) return null;
  const risk_score = clamp(score, 0, 1);
  const features: Record<string, number> = {};
  if (isObj(raw.features)) {
    for (const [k, v] of Object.entries(raw.features)) {
      const n = finite(v);
      if (n !== null) features[k] = n;
    }
  }
  return {
    ...id,
    risk_score,
    // an unknown level, or one attached to an out-of-range score, is re-derived from the
    // (clamped) score so the label and the number on screen never contradict each other
    risk_level: (risk_score === score && oneOf(raw.risk_level, LEVELS)) || classifyRisk(risk_score),
    depth_band: oneOf(raw.depth_band, DEPTHS) ?? 'none',
    peak_window_hours: clamp(Math.round(finite(raw.peak_window_hours) ?? 0), 0, 72),
    reasons: Array.isArray(raw.reasons)
      ? raw.reasons.filter((r): r is string => typeof r === 'string').slice(0, MAX_REASONS).map((r) => r.slice(0, MAX_REASON))
      : [],
    features,
  };
}

export function validateRiskResponse(data: unknown): RiskResponse {
  if (!isObj(data)) throw new ApiDataError('risk response is not an object');
  const wards = uniqueById(list(data.wards, 'risk wards').map(wardRisk)).sort((a, b) => b.risk_score - a.risk_score);
  if (wards.length === 0) throw new ApiDataError('no scored wards');
  const scenario = isObj(data.scenario) ? data.scenario : {};
  const generated = typeof data.generated_at === 'string' ? new Date(data.generated_at) : new Date(NaN);
  return {
    scenario: {
      rainfall_mm: clamp(finite(scenario.rainfall_mm) ?? 0, 0, 500),
      duration_hours: clamp(finite(scenario.duration_hours) ?? 3, 1, 24),
      scenario_name: text(scenario.scenario_name, 60) ?? undefined,
    },
    wards,
    generated_at: Number.isNaN(generated.getTime()) ? new Date().toISOString() : generated.toISOString(),
    model_version: text(data.model_version, 40) ?? 'unknown',
  };
}

// --- other endpoints --------------------------------------------------------

export function validateValidation(data: unknown): ValidationMetrics {
  return parseValidation(data);
}

export function validateAlerts(data: unknown): AlertResponse {
  if (!isObj(data)) throw new ApiDataError('alerts response is not an object');
  const alerts = list(data.alerts, 'alerts').flatMap((raw): AlertMessage[] => {
    if (!isObj(raw)) return [];
    const channel = oneOf(raw.channel, CHANNELS);
    const message = text(raw.message, MAX_MESSAGE);
    const id = finite(raw.ward_id);
    if (!channel || !message || id === null) return [];
    return [{
      ward_id: id,
      ward_name: text(raw.ward_name) ?? `Ward ${id}`,
      channel,
      language: oneOf(raw.language, LANGUAGES) ?? 'en',
      message,
      // safeWhatsAppUrl() still vets this before it becomes a link
      whatsapp_deeplink: typeof raw.whatsapp_deeplink === 'string' ? raw.whatsapp_deeplink.slice(0, 4000) : undefined,
    }];
  });
  return { alerts, sent_at: text(data.sent_at, 40) ?? '' };
}

export function validateShelters(data: unknown): Shelter[] {
  return list(data, 'shelters').flatMap((raw): Shelter[] => {
    if (!isObj(raw)) return [];
    const lat = finite(raw.latitude);
    const lng = finite(raw.longitude);
    const id = finite(raw.shelter_id);
    const name = text(raw.name);
    if (lat === null || lng === null || Math.abs(lat) > 90 || Math.abs(lng) > 180 || id === null || !name) return [];
    return [{
      shelter_id: id,
      name,
      latitude: lat,
      longitude: lng,
      capacity: Math.max(0, Math.round(finite(raw.capacity) ?? 0)),
      distance_km: Math.max(0, finite(raw.distance_km) ?? 0),
      walking_time_min: clamp(Math.round(finite(raw.walking_time_min) ?? 0), 0, 24 * 60),
      route_geometry: lineGeometry(raw.route_geometry),
    }];
  });
}

export function validateRoads(data: unknown): RoadRisk[] {
  return list(data, 'roads').flatMap((raw): RoadRisk[] => {
    if (!isObj(raw)) return [];
    const geometry = lineGeometry(raw.geometry);
    const score = finite(raw.risk_score);
    if (!geometry || score === null) return [];
    const risk_score = clamp(score, 0, 1);
    return [{
      road_id: text(raw.road_id, 60) ?? '',
      name: text(raw.name) ?? 'Unnamed road',
      highway_type: text(raw.highway_type, 30) ?? '',
      risk_score,
      risk_level: (risk_score === score && oneOf(raw.risk_level, LEVELS)) || classifyRisk(risk_score),
      is_underpass: raw.is_underpass === true,
      flood_depth_estimate_m: Math.max(0, finite(raw.flood_depth_estimate_m) ?? 0),
      geometry,
    }];
  });
}

// --- phone alerts -----------------------------------------------------------

const BROADCAST_LEVELS = ['watch', 'warning'] as const;
const BROADCAST_STATUS = ['pending', 'approved', 'cancelled'] as const;

function broadcastAlert(raw: unknown): BroadcastAlert | null {
  if (!isObj(raw)) return null;
  const id = text(raw.id, 80);
  const ward = wardIdentity(raw);
  const level = oneOf(raw.level, BROADCAST_LEVELS);
  const status = oneOf(raw.status, BROADCAST_STATUS);
  const score = finite(raw.risk_score);
  const messages = isObj(raw.messages) ? raw.messages : {};
  const en = text(messages.en, MAX_MESSAGE);
  if (!id || !ward || !level || !status || score === null || !en) return null;
  const risk_score = clamp(score, 0, 1);
  const delivery = isObj(raw.delivery)
    ? {
        push_sent: Math.max(0, Math.round(finite(raw.delivery.push_sent) ?? 0)),
        whatsapp_queued: Math.max(0, Math.round(finite(raw.delivery.whatsapp_queued) ?? 0)),
      }
    : null;
  return {
    id,
    ward_id: ward.ward_id,
    ward_name: ward.ward_name,
    level,
    risk_level: (risk_score === score && oneOf(raw.risk_level, LEVELS)) || classifyRisk(risk_score),
    risk_score,
    rainfall_mm: clamp(finite(raw.rainfall_mm) ?? 0, 0, 500),
    duration_hours: clamp(finite(raw.duration_hours) ?? 3, 1, 24),
    created_at: text(raw.created_at, 40) ?? '',
    status,
    // anything that does not explicitly say exercise=false is treated as a drill
    exercise: raw.exercise !== false,
    messages: { en, ta: text(messages.ta, MAX_MESSAGE) ?? en },
    approved_at: text(raw.approved_at, 40),
    delivery,
  };
}

export function validateBroadcastAlerts(data: unknown): BroadcastAlert[] {
  return list(data, 'alerts').map(broadcastAlert).filter((a): a is BroadcastAlert => a !== null);
}

export function validateBroadcastAlert(data: unknown): BroadcastAlert {
  const alert = broadcastAlert(data);
  if (!alert) throw new ApiDataError('alert');
  return alert;
}

export function validateSubscription(data: unknown): Subscription {
  if (!isObj(data)) throw new ApiDataError('subscription is not an object');
  const id = text(data.id, 80);
  const wardId = finite(data.ward_id);
  if (!id || wardId === null || !Number.isInteger(wardId)) throw new ApiDataError('subscription');
  const channels = Array.isArray(data.channels)
    ? data.channels.filter((c): c is SubscriptionChannel => c === 'push' || c === 'whatsapp')
    : [];
  return { id, ward_id: wardId, language: oneOf(data.language, LANGUAGES) ?? 'en', channels };
}

/** Lite wards for on-device lookup: shapes are required (a ward without one can't be matched). */
export function validateWardsLite(data: unknown): WardLite[] {
  const wards = uniqueById(
    list(data, 'ward list').map((raw) => {
      if (!isObj(raw)) return null;
      const id = wardIdentity(raw);
      const geometry = polygonGeometry(raw.geometry);
      return id && geometry ? { ...id, geometry: geometry as WardLite['geometry'] } : null;
    })
  );
  if (wards.length === 0) throw new ApiDataError('no valid ward shapes');
  return wards;
}
