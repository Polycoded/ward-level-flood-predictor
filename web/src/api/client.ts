import axios, { AxiosInstance, InternalAxiosRequestConfig, type AxiosAdapter } from 'axios';
import type {
  Ward,
  WardFeature,
  RiskResponse,
  RainfallInput,
  ScenarioInput,
  AlertResponse,
  ValidationMetrics,
  Shelter,
  RoadRisk,
  HealthResponse,
  ReadyResponse,
  BroadcastAlert,
  Subscription,
  SubscriptionRequest,
  WardLite,
} from '../types';
import * as mockAlerts from './mockAlerts';
import { mockApi } from './mock';
import { parseValidation, unavailableValidation } from '../lib/validation';
import {
  validateAlerts,
  validateRiskResponse,
  validateRoads,
  validateShelters,
  validateWardFeature,
  validateWards,
  validateBroadcastAlert,
  validateBroadcastAlerts,
  validateSubscription,
  validateWardsLite,
} from './validate';
import { useFloodStore, type DataSource } from '../lib/store';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';
const FORCE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

interface ApiClientOptions {
  baseURL?: string;
  forceMock?: boolean;
  /** lets tests stand in for the network */
  adapter?: AxiosAdapter;
}

export class ApiClient {
  private client: AxiosInstance;
  private source: Promise<Exclude<DataSource, 'unknown'>> | null = null;
  private forceMock: boolean;

  constructor({ baseURL = API_BASE_URL, forceMock = FORCE_MOCK, adapter }: ApiClientOptions = {}) {
    this.forceMock = forceMock;
    this.client = axios.create({
      baseURL,
      adapter,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => config,
      (error) => Promise.reject(error)
    );

    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        // 4xx answers are expected and handled by callers (e.g. endpoints not built yet);
        // only log network failures and server errors.
        const status = error.response?.status;
        if (!status || status >= 500) console.error('API error', status ?? error.message, error.config?.url);
        return Promise.reject(error);
      }
    );
  }

  // Decide once per session whether to talk to the backend or the bundled mock,
  // so live and mock data never get mixed (e.g. live wards with mock risk scores).
  private resolveSource() {
    this.source ??= (async () => {
      if (this.forceMock) return 'mock' as const;
      // Offline is not "backend missing": stay on real data so the service worker's cached
      // wards are used. Falling back to the synthetic demo here showed made-up wards to residents.
      if (typeof navigator !== 'undefined' && navigator.onLine === false) return 'live' as const;
      try {
        const { data } = await this.client.get<ReadyResponse>('/readyz', { timeout: 3000 });
        if (data.checks?.features && data.checks?.wards) return 'live' as const;
        console.warn('API is up but not ready (missing features/wards) - using mock data', data.checks);
      } catch {
        console.warn(`API unreachable at ${this.client.defaults.baseURL} - using mock data`);
      }
      return 'mock' as const;
    })().then((source) => {
      useFloodStore.getState().setDataSource(source);
      return source;
    });
    return this.source;
  }

  /**
   * For endpoints from docs/ACTION_PLAN_ALERTS.md that the backend may not have yet:
   * a 404/405/501 from a live server falls back to the in-browser mock and marks the
   * feature as a preview, so the UI can say so instead of pretending it's real.
   */
  private async callContract<T>(live: () => Promise<T>, mock: () => T | Promise<T>): Promise<T> {
    if ((await this.resolveSource()) === 'mock') return mock();
    try {
      return await live();
    } catch (error) {
      const status = (error as { response?: { status?: number } }).response?.status;
      if (status === 404 || status === 405 || status === 501) {
        useFloodStore.getState().setAlertsPreview(true);
        return mock();
      }
      throw error;
    }
  }

  private async call<T>(live: () => Promise<T>, mock: () => T): Promise<T> {
    return (await this.resolveSource()) === 'live' ? live() : mock();
  }

  async healthCheck(): Promise<HealthResponse> {
    return this.call(async () => (await this.client.get<HealthResponse>('/healthz')).data, mockApi.healthCheck);
  }

  async readyCheck(): Promise<ReadyResponse> {
    return this.call(async () => (await this.client.get<ReadyResponse>('/readyz')).data, mockApi.readyCheck);
  }

  async getWards(): Promise<Ward[]> {
    return this.call(async () => validateWards((await this.client.get('/wards')).data), mockApi.getWards);
  }

  async getWard(wardId: number): Promise<WardFeature> {
    return this.call(
      async () => validateWardFeature((await this.client.get(`/wards/${wardId}`)).data),
      () => mockApi.getWard(wardId)
    );
  }

  async getWardsGeoJSON(): Promise<GeoJSON.FeatureCollection> {
    return this.call(
      async () => (await this.client.get<GeoJSON.FeatureCollection>('/wards/geojson')).data,
      mockApi.getWardsGeoJSON
    );
  }

  async getRisk(input: RainfallInput): Promise<RiskResponse> {
    return this.call(
      async () => validateRiskResponse((await this.client.post('/risk', input)).data),
      () => mockApi.getRisk(input)
    );
  }

  async getScenarioRisk(input: ScenarioInput): Promise<RiskResponse> {
    return this.call(
      async () => validateRiskResponse((await this.client.post('/scenario', input)).data),
      () => mockApi.getScenarioRisk(input)
    );
  }

  async getValidation(): Promise<ValidationMetrics> {
    try {
      return parseValidation(await this.call(async () => (await this.client.get<unknown>('/validation')).data, mockApi.getValidation));
    } catch {
      return unavailableValidation('Validation evidence could not be loaded.');
    }
  }

  async generateAlerts(
    wardIds: number[],
    rainfallMm: number,
    language: 'en' | 'ta' = 'en',
    channels: ('sms' | 'whatsapp' | 'voice' | 'livekit')[] = ['sms', 'whatsapp'],
    durationHours?: number
  ): Promise<AlertResponse> {
    return this.call(
      async () =>
        validateAlerts(
          (
            await this.client.post('/alerts', {
              ward_ids: wardIds,
              rainfall_mm: rainfallMm,
              language,
              channels,
              ...(durationHours === undefined ? {} : { duration_hours: durationHours }),
            })
          ).data
        ),
      () => mockApi.generateAlerts(wardIds, rainfallMm, language, channels, durationHours)
    );
  }

  async findShelters(
    latitude: number,
    longitude: number,
    maxDistanceKm: number = 5,
    maxResults: number = 5
  ): Promise<Shelter[]> {
    return this.call(
      async () =>
        validateShelters(
          (
            await this.client.post('/shelters', {
              latitude,
              longitude,
              max_distance_km: maxDistanceKm,
              max_results: maxResults,
            })
          ).data
        ),
      () => mockApi.findShelters(latitude, longitude, maxDistanceKm, maxResults)
    );
  }

  async getRoadRisk(rainfallMm: number): Promise<RoadRisk[]> {
    return this.call(
      async () => validateRoads((await this.client.get('/roads/risk', { params: { rainfall_mm: rainfallMm } })).data),
      () => mockApi.getRoadRisk(rainfallMm)
    );
  }

  // --- phone alerts (contracts in docs/ACTION_PLAN_ALERTS.md) ---------------

  /** Simplified shapes for on-device ward lookup; uses the full /wards until /wards/lite exists. */
  async getWardsLite(): Promise<WardLite[]> {
    if ((await this.resolveSource()) === 'mock') return validateWardsLite(mockApi.getWards());
    try {
      return validateWardsLite((await this.client.get('/wards/lite')).data);
    } catch (error) {
      const status = (error as { response?: { status?: number } }).response?.status;
      // Until /wards/lite exists, FastAPI routes "lite" to /wards/{ward_id} and answers 422.
      if (status === 404 || status === 405 || status === 422) return validateWardsLite(await this.getWards());
      throw error;
    }
  }

  async runAlertCheck(input: { rainfall_mm: number; duration_hours: number }): Promise<BroadcastAlert[]> {
    return this.callContract(
      async () => validateBroadcastAlerts((await this.client.post('/alerts/check', input)).data),
      // the preview engine must score the same wards the user sees: live scores when the
      // backend is up (only /alerts/check is missing), demo scores only in demo mode
      async () => mockAlerts.runAlertCheck(await this.getScenarioRisk({ ...input, builtup_increase_pct: 0 }))
    );
  }

  async getPendingAlerts(): Promise<BroadcastAlert[]> {
    return this.callContract(
      async () => validateBroadcastAlerts((await this.client.get('/alerts/pending')).data),
      mockAlerts.listPending
    );
  }

  async approveAlert(id: string): Promise<BroadcastAlert> {
    return this.callContract(
      async () => validateBroadcastAlert((await this.client.post(`/alerts/${encodeURIComponent(id)}/approve`)).data),
      () => mockAlerts.approveAlert(id)
    );
  }

  async cancelAlert(id: string): Promise<BroadcastAlert> {
    return this.callContract(
      async () => validateBroadcastAlert((await this.client.post(`/alerts/${encodeURIComponent(id)}/cancel`)).data),
      () => mockAlerts.cancelAlert(id)
    );
  }

  async getActiveAlerts(wardId: number): Promise<BroadcastAlert[]> {
    return this.callContract(
      async () => validateBroadcastAlerts((await this.client.get('/alerts/active', { params: { ward_id: wardId } })).data),
      () => mockAlerts.listActive(wardId)
    );
  }

  async getAlert(id: string): Promise<BroadcastAlert | null> {
    return this.callContract(
      async () => validateBroadcastAlert((await this.client.get(`/alerts/${encodeURIComponent(id)}`)).data),
      () => mockAlerts.getAlert(id)
    );
  }

  async createSubscription(req: SubscriptionRequest): Promise<Subscription> {
    return this.callContract(
      async () => validateSubscription((await this.client.post('/subscriptions', req)).data),
      () => mockAlerts.createSubscription(req)
    );
  }

  async updateSubscription(id: string, wardId: number): Promise<Subscription> {
    return this.callContract(
      async () => validateSubscription((await this.client.patch(`/subscriptions/${encodeURIComponent(id)}`, { ward_id: wardId })).data),
      () => mockAlerts.updateSubscription(id, wardId)
    );
  }

  async deleteSubscription(id: string): Promise<void> {
    return this.callContract(
      async () => {
        await this.client.delete(`/subscriptions/${encodeURIComponent(id)}`);
      },
      () => mockAlerts.deleteSubscription(id)
    );
  }
}

export const api = new ApiClient();
