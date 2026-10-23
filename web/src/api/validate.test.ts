import { describe, expect, it } from 'vitest';
import {
  ApiDataError,
  validateAlerts,
  validateRiskResponse,
  validateRoads,
  validateShelters,
  validateValidation,
  validateWardFeature,
  validateWards,
} from './validate';
import { mockApi } from './mock';

// Responses that crashed or corrupted the dashboard in manual testing against the live UI.
const ward = (over: Record<string, unknown>) => ({
  ward_id: 1, ward_number: '1', ward_name: 'A', risk_score: 0.5, risk_level: 'moderate',
  depth_band: '0.15-0.5m', peak_window_hours: 4, reasons: ['r'], features: { elevation_mean: 3 }, ...over,
});
const risk = (wards: unknown, extra: Record<string, unknown> = {}) => ({
  scenario: { rainfall_mm: 100, duration_hours: 3 }, generated_at: '2026-10-23T10:00:00Z', model_version: '1', wards, ...extra,
});

describe('validateRiskResponse', () => {
  it.each([
    ['an HTML page (SPA fallback / wrong proxy)', '<!doctype html><html></html>'],
    ['null', null],
    ['wards: null', risk(null)],
    ['wards: object', risk({ 0: ward({}) })],
    ['no usable wards', risk([{ ward_id: 'x' }, null, 42])],
  ])('rejects %s with ApiDataError', (_, body) => {
    expect(() => validateRiskResponse(body)).toThrow(ApiDataError);
  });

  it('clamps scores, re-derives unknown levels and drops broken fields instead of showing garbage', () => {
    const r = validateRiskResponse(risk([
      ward({ ward_id: 1, risk_score: 57, risk_level: 'catastrophic', depth_band: '9m', peak_window_hours: -3, reasons: null, features: null }),
      ward({ ward_id: 2, risk_score: -1, peak_window_hours: 1e9, reasons: 'not-an-array', features: { elevation_mean: 'abc', slope_mean: 2 } }),
      ward({ ward_id: 3, risk_score: 'NaN' }),
      ward({ ward_id: 4, ward_name: 'C'.repeat(5000), reasons: ['x'.repeat(5000), 7, null] }),
    ], { generated_at: 'not a date' }));

    expect(r.wards.map((w) => w.ward_id)).toEqual([1, 4, 2]); // NaN score dropped, sorted by score
    const [w1, w4, w2] = r.wards;
    expect(w1).toMatchObject({ risk_score: 1, risk_level: 'very_high', depth_band: 'none', peak_window_hours: 0, reasons: [], features: {} });
    expect(w2).toMatchObject({ risk_score: 0, risk_level: 'very_low', peak_window_hours: 72, reasons: [], features: { slope_mean: 2 } });
    expect(w4.ward_name).toHaveLength(120);
    expect(w4.reasons).toEqual(['x'.repeat(300)]);
    expect(Number.isNaN(new Date(r.generated_at).getTime())).toBe(false);
  });

  it('keeps the first of duplicate ward ids', () => {
    const r = validateRiskResponse(risk([ward({ ward_id: 9, risk_score: 0.2 }), ward({ ward_id: 9, risk_score: 0.9 })]));
    expect(r.wards).toHaveLength(1);
    expect(r.wards[0].risk_score).toBe(0.2);
  });

  it('passes real responses through unchanged', () => {
    const real = mockApi.getRisk({ rainfall_mm: 150, duration_hours: 6 });
    const v = validateRiskResponse(JSON.parse(JSON.stringify(real)));
    expect(v.wards).toEqual(real.wards);
    expect(v.scenario).toMatchObject({ rainfall_mm: 150, duration_hours: 6 });
  });
});

describe('validateWards', () => {
  it('drops geometry Leaflet cannot draw but keeps the ward', () => {
    const wards = validateWards([
      { ward_id: 1, ward_number: '1', ward_name: 'ok', area_sqkm: 1, geometry: { type: 'Polygon', coordinates: [[[80, 13], [80.1, 13], [80.1, 13.1], [80, 13]]] } },
      { ward_id: 2, ward_number: '2', ward_name: 'nan', area_sqkm: 1, geometry: { type: 'Polygon', coordinates: [[['x', 13], [80.1, 13], [80.1, 13.1], [80, 13]]] } },
      { ward_id: 3, ward_number: '3', ward_name: 'point', area_sqkm: 1, geometry: { type: 'Point', coordinates: [80, 13] } },
      { ward_id: 4, ward_number: '4', ward_name: 'off-planet', area_sqkm: 1, geometry: { type: 'Polygon', coordinates: [[[800, 13], [80.1, 13], [80.1, 13.1], [800, 13]]] } },
    ]);
    expect(wards.map((w) => [w.ward_id, !!w.geometry])).toEqual([[1, true], [2, false], [3, false], [4, false]]);
  });

  it('rejects a non-list and an empty list', () => {
    expect(() => validateWards({ wards: [] })).toThrow(ApiDataError);
    expect(() => validateWards([])).toThrow(ApiDataError);
  });

  it('accepts the real mock wards', () => {
    expect(validateWards(JSON.parse(JSON.stringify(mockApi.getWards())))).toHaveLength(200);
  });
});

describe('validateWardFeature', () => {
  it('rejects a ward with missing measurements instead of rendering "NaN m"', () => {
    expect(() => validateWardFeature({ ward_id: 1, ward_name: null, elevation_mean: null })).toThrow(ApiDataError);
  });

  it('clamps fractions and counts', () => {
    const f = validateWardFeature({ ...mockApi.getWard(1), impervious_frac: 7, underpass_count: -2.6, dist_to_water_m: -5 });
    expect(f).toMatchObject({ impervious_frac: 1, underpass_count: 0, dist_to_water_m: 0 });
  });
});

describe('other endpoints', () => {
  it('validation metrics must be real ratios and counts', () => {
    const ok = mockApi.getValidation();
    expect(validateValidation(ok)).toEqual(ok);
    expect(() => validateValidation({ ...ok, recall: 7 })).toThrow(ApiDataError);
    expect(() => validateValidation({ ...ok, true_positives: -1 })).toThrow(ApiDataError);
    expect(() => validateValidation('<html>')).toThrow(ApiDataError);
  });

  it('alerts with unknown channels or no text are dropped; messages are length-limited', () => {
    const r = validateAlerts({ sent_at: 'x', alerts: [
      { ward_id: 1, ward_name: 'A', channel: 'pigeon', language: 'en', message: 'm' },
      { ward_id: 1, ward_name: 'A', channel: 'sms', language: 'xx', message: 'y'.repeat(9999) },
      { ward_id: 1, channel: 'sms', message: null },
    ] });
    expect(r.alerts).toHaveLength(1);
    expect(r.alerts[0]).toMatchObject({ channel: 'sms', language: 'en' });
    expect(r.alerts[0].message).toHaveLength(1000);
  });

  it('shelters off the map or without a name are dropped', () => {
    const s = validateShelters([
      { shelter_id: 1, name: 'School', latitude: 13, longitude: 80.2, capacity: 300, distance_km: 1, walking_time_min: 15 },
      { shelter_id: 2, name: 'Nowhere', latitude: 9999, longitude: 80, capacity: 1, distance_km: 1, walking_time_min: 1 },
      { shelter_id: 3, name: '', latitude: 13, longitude: 80, capacity: 1, distance_km: 1, walking_time_min: 1 },
      { shelter_id: 4, name: 'Bad route', latitude: 13, longitude: 80, capacity: 1, distance_km: 1, walking_time_min: 1e12, route_geometry: { type: 'LineString', coordinates: [['a', 'b']] } },
    ]);
    expect(s.map((x) => x.shelter_id)).toEqual([1, 4]);
    expect(s[1]).toMatchObject({ walking_time_min: 1440, route_geometry: undefined });
  });

  it('roads without drawable geometry are dropped', () => {
    const roads = validateRoads([
      { road_id: 'a', name: 'R', highway_type: 'primary', risk_score: 0.8, risk_level: 'high', is_underpass: 'yes', flood_depth_estimate_m: 1, geometry: { type: 'LineString', coordinates: [[80, 13], [80.1, 13]] } },
      { road_id: 'b', name: 'R', risk_score: 0.8, geometry: { type: 'Point', coordinates: [80, 13] } },
    ]);
    expect(roads).toHaveLength(1);
    expect(roads[0].is_underpass).toBe(false); // only a real boolean counts
  });
});
