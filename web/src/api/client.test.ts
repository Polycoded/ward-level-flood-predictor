import { describe, expect, it, vi, beforeEach } from 'vitest';
import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { ApiClient } from './client';
import { useFloodStore } from '../lib/store';

type Route = (config: InternalAxiosRequestConfig) => { status: number; data: unknown } | Error;

function adapter(route: Route) {
  const calls: string[] = [];
  const fn: AxiosAdapter = async (config) => {
    calls.push(`${config.method?.toUpperCase()} ${config.url}`);
    const result = route(config as InternalAxiosRequestConfig);
    if (result instanceof Error) throw result;
    const response = { data: result.data, status: result.status, statusText: '', headers: {}, config } as AxiosResponse;
    if (result.status >= 400) throw Object.assign(new Error(`status ${result.status}`), { response, isAxiosError: true });
    return response;
  };
  return { fn, calls };
}

const READY = { ready: true, checks: { features: true, wards: true, validation: false, shelters: true, roads: true }, timestamp: '' };
const LIVE_WARD = [{ ward_id: 7, ward_number: '7', ward_name: 'Live Ward', area_sqkm: 1 }];

beforeEach(() => {
  useFloodStore.setState({ dataSource: 'unknown' });
  vi.spyOn(console, 'warn').mockImplementation(() => {});
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

describe('ApiClient live/mock decision', () => {
  it('forwards explicitly selected alert duration', async () => {
    let body: unknown;
    const { fn } = adapter(c => {
      if (c.url === '/readyz') return { status: 200, data: READY };
      body = JSON.parse(c.data as string);
      return { status: 200, data: { alerts: [], sent_at: '' } };
    });
    await new ApiClient({ forceMock: false, adapter: fn }).generateAlerts([1], 100, 'en', ['sms'], 12);
    expect(body).toEqual({ ward_ids: [1], rainfall_mm: 100, language: 'en', channels: ['sms'], duration_hours: 12 });
  });
  it('suppresses legacy mock accuracy returned by a live backend', async () => {
    const { fn } = adapter(c => ({ status: 200, data: c.url === '/readyz' ? READY :
      { precision_at_20: 0.65, notes: 'MOCK NUMBERS' } }));
    const result = await new ApiClient({ forceMock: false, adapter: fn }).getValidation();
    expect(result.status).toBe('unavailable');
    expect(result.metrics).toBeUndefined();
    expect(result.status_reason).toMatch(/not accuracy evidence/);
  });

  it('returns explicit unavailable evidence on a live validation fetch failure', async () => {
    const { fn } = adapter(c => c.url === '/readyz' ? { status: 200, data: READY } : new Error('Network error'));
    const result = await new ApiClient({ forceMock: false, adapter: fn }).getValidation();
    expect(result.status).toBe('unavailable');
    expect(result.status_reason).toMatch(/could not be loaded/);
  });
  it('uses the backend when /readyz reports features and wards', async () => {
    const { fn, calls } = adapter((c) => (c.url === '/readyz' ? { status: 200, data: READY } : { status: 200, data: LIVE_WARD }));
    const client = new ApiClient({ forceMock: false, adapter: fn });
    expect(await client.getWards()).toEqual(LIVE_WARD);
    expect(calls).toEqual(['GET /readyz', 'GET /wards']);
    expect(useFloodStore.getState().dataSource).toBe('live');
  });

  it('falls back to mock data when the backend is unreachable', async () => {
    const { fn, calls } = adapter(() => new Error('Network Error'));
    const client = new ApiClient({ forceMock: false, adapter: fn });
    const wards = await client.getWards();
    expect(wards).toHaveLength(200);
    expect(calls).toEqual(['GET /readyz']);
    expect(useFloodStore.getState().dataSource).toBe('mock');
  });

  it('falls back to mock data when the backend is up but has no features yet', async () => {
    const { fn } = adapter(() => ({ status: 200, data: { ...READY, checks: { ...READY.checks, features: false } } }));
    const client = new ApiClient({ forceMock: false, adapter: fn });
    await client.getWards();
    expect(useFloodStore.getState().dataSource).toBe('mock');
  });

  it('treats a 500 from /readyz as unavailable', async () => {
    const { fn } = adapter(() => ({ status: 500, data: 'Internal Server Error' }));
    await new ApiClient({ forceMock: false, adapter: fn }).getWards();
    expect(useFloodStore.getState().dataSource).toBe('mock');
  });

  it('probes /readyz once even when the first calls run in parallel', async () => {
    const risk = { scenario: { rainfall_mm: 100, duration_hours: 3 }, generated_at: '2026-10-23T00:00:00Z', model_version: '1',
      wards: [{ ward_id: 7, ward_number: '7', ward_name: 'W', risk_score: 0.5, risk_level: 'moderate', depth_band: 'none', peak_window_hours: 4, reasons: [], features: {} }] };
    const { fn, calls } = adapter((c) =>
      c.url === '/readyz' ? { status: 200, data: READY } : c.url === '/wards' ? { status: 200, data: LIVE_WARD } : { status: 200, data: risk }
    );
    const client = new ApiClient({ forceMock: false, adapter: fn });
    await Promise.all([client.getWards(), client.getWards(), client.getRisk({ rainfall_mm: 100, duration_hours: 3 })]);
    expect(calls.filter((c) => c === 'GET /readyz')).toHaveLength(1);
  });

  it('never mixes sources: once live, a failing call surfaces instead of returning mock data', async () => {
    const { fn } = adapter((c) => (c.url === '/readyz' ? { status: 200, data: READY } : { status: 500, data: {} }));
    const client = new ApiClient({ forceMock: false, adapter: fn });
    await expect(client.getRisk({ rainfall_mm: 100, duration_hours: 3 })).rejects.toThrow();
  });

  it('sends the request body the FastAPI schemas expect', async () => {
    let body: unknown;
    const { fn } = adapter((c) => {
      if (c.url === '/readyz') return { status: 200, data: READY };
      body = JSON.parse(c.data as string);
      return { status: 200, data: { alerts: [], sent_at: '' } };
    });
    await new ApiClient({ forceMock: false, adapter: fn }).generateAlerts([1, 2], 120, 'ta', ['whatsapp']);
    expect(body).toEqual({ ward_ids: [1, 2], rainfall_mm: 120, language: 'ta', channels: ['whatsapp'] });
  });

  it('forceMock never touches the network', async () => {
    const { fn, calls } = adapter(() => ({ status: 200, data: READY }));
    await new ApiClient({ forceMock: true, adapter: fn }).getRisk({ rainfall_mm: 50, duration_hours: 3 });
    expect(calls).toEqual([]);
  });
});

describe('phone-alert endpoints before the backend has them', () => {
  it('falls back to the in-browser preview on 404 and says so', async () => {
    useFloodStore.setState({ alertsPreview: false });
    const { fn } = adapter((c) => (c.url === '/readyz' ? { status: 200, data: READY } : { status: 404, data: { detail: 'Not Found' } }));
    const client = new ApiClient({ forceMock: false, adapter: fn });
    expect(await client.getPendingAlerts()).toEqual(expect.any(Array));
    expect(useFloodStore.getState().alertsPreview).toBe(true);
  });

  it('does not hide real server failures behind the preview', async () => {
    const { fn } = adapter((c) => (c.url === '/readyz' ? { status: 200, data: READY } : { status: 500, data: {} }));
    const client = new ApiClient({ forceMock: false, adapter: fn });
    await expect(client.getPendingAlerts()).rejects.toThrow();
  });

  it('uses the full /wards for ward lookup until /wards/lite exists', async () => {
    const square = { type: 'Polygon', coordinates: [[[80, 13], [80.1, 13], [80.1, 13.1], [80, 13.1], [80, 13]]] };
    const { fn, calls } = adapter((c) =>
      c.url === '/readyz' ? { status: 200, data: READY }
        : c.url === '/wards/lite' ? { status: 422, data: { detail: [{ loc: ['path', 'ward_id'] }] } }
          : { status: 200, data: [{ ward_id: 7, ward_number: '7', ward_name: 'Live Ward', area_sqkm: 1, geometry: square }] }
    );
    const wards = await new ApiClient({ forceMock: false, adapter: fn }).getWardsLite();
    expect(wards.map((w) => w.ward_name)).toEqual(['Live Ward']);
    expect(calls).toEqual(expect.arrayContaining(['GET /wards/lite', 'GET /wards']));
  });

  it('sends only the ward number and push address when subscribing, never coordinates', async () => {
    let body: Record<string, unknown> = {};
    const { fn } = adapter((c) => {
      if (c.url === '/readyz') return { status: 200, data: READY };
      body = JSON.parse(c.data as string);
      return { status: 200, data: { id: 's1', ward_id: 12, language: 'ta', channels: ['push'] } };
    });
    await new ApiClient({ forceMock: false, adapter: fn }).createSubscription({ ward_id: 12, language: 'ta', push: { endpoint: 'https://push.example/x' } });
    expect(Object.keys(body).sort()).toEqual(['language', 'push', 'ward_id']);
    expect(JSON.stringify(body)).not.toMatch(/lat|lng|longitude|latitude/);
  });
});

describe('offline phones', () => {
  it('stay on real (cached) data instead of switching to the synthetic demo', async () => {
    const onLine = vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    const { fn, calls } = adapter((c) => (c.url === '/wards' ? { status: 200, data: LIVE_WARD } : new Error('Network Error')));
    const client = new ApiClient({ forceMock: false, adapter: fn });
    expect(await client.getWards()).toEqual(LIVE_WARD);
    expect(calls).not.toContain('GET /readyz');
    expect(useFloodStore.getState().dataSource).toBe('live');
    onLine.mockRestore();
  });
});

describe('alert check on a live backend', () => {
  it('returns null (server schedules alerts itself) instead of inventing alerts in the browser', async () => {
    const { resetMockAlerts, listPending } = await import('./mockAlerts');
    resetMockAlerts();
    const { fn } = adapter((c) => (c.url === '/readyz' ? { status: 200, data: READY } : { status: 405, data: {} }));
    const created = await new ApiClient({ forceMock: false, adapter: fn }).runAlertCheck({ rainfall_mm: 300, duration_hours: 3 });
    expect(created).toBeNull();
    expect(listPending()).toEqual([]);
  });

  it('reads the backend alert shape and approval dispatch summary', async () => {
    const alertOut = {
      id: 'a-1', ward_id: 77, ward_name: 'Ward 168', risk_level: 'very_high', risk_score: 0.95, alert_type: 'warning',
      status: 'pending', rainfall_mm: 300, duration_hours: 3, message_en: 'EN text', message_ta: 'TA text',
      created_at: '2026-10-23T08:00:00Z', approved_at: null, sent_at: null, exercise: true,
    };
    let approved = false;
    const { fn } = adapter((c) => {
      if (c.url === '/readyz') return { status: 200, data: READY };
      if (c.url === '/alerts/pending') return { status: 200, data: [alertOut] };
      if (c.url === '/alerts/a-1/approve') { approved = true; return { status: 200, data: { alert_id: 'a-1', ward_id: 77, webpush: 4, whatsapp: 2, sms: 0, failed: 0, status: 'sent' } }; }
      if (c.url === '/alerts/a-1') return { status: 200, data: { ...alertOut, status: approved ? 'sent' : 'pending' } };
      return { status: 404, data: {} };
    });
    const client = new ApiClient({ forceMock: false, adapter: fn });
    const [pending] = await client.getPendingAlerts();
    expect(pending).toMatchObject({ level: 'warning', messages: { en: 'EN text', ta: 'TA text' }, status: 'pending' });
    const done = await client.approveAlert('a-1');
    expect(done).toMatchObject({ status: 'approved', delivery: { push_sent: 4, whatsapp_queued: 2 } });
  });

  it('reads /wards/lite as the GeoJSON FeatureCollection the backend serves', async () => {
    const square = { type: 'Polygon', coordinates: [[[80, 13, 0], [80.1, 13, 0], [80.1, 13.1, 0], [80, 13.1, 0], [80, 13, 0]]] };
    const { fn } = adapter((c) =>
      c.url === '/readyz' ? { status: 200, data: READY }
        : { status: 200, data: { type: 'FeatureCollection', features: [{ type: 'Feature', properties: { ward_id: 1, ward_number: '168' }, geometry: square }] } }
    );
    const wards = await new ApiClient({ forceMock: false, adapter: fn }).getWardsLite();
    expect(wards).toEqual([expect.objectContaining({ ward_id: 1, ward_number: '168', ward_name: 'Ward 168' })]);
  });
});
