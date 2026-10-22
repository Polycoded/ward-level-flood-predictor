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
    const { fn, calls } = adapter((c) => (c.url === '/readyz' ? { status: 200, data: READY } : { status: 200, data: [] }));
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
