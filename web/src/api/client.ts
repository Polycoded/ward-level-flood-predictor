import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';
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
} from '../types';
import { mockApi } from './mock';
import { useFloodStore, type DataSource } from '../lib/store';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';
const FORCE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

class ApiClient {
  private client: AxiosInstance;
  private source: Promise<Exclude<DataSource, 'unknown'>> | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
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
        console.error('API Error:', error.response?.data || error.message);
        return Promise.reject(error);
      }
    );
  }

  // Decide once per session whether to talk to the backend or the bundled mock,
  // so live and mock data never get mixed (e.g. live wards with mock risk scores).
  private resolveSource() {
    this.source ??= (async () => {
      if (FORCE_MOCK) return 'mock' as const;
      try {
        const { data } = await this.client.get<ReadyResponse>('/readyz', { timeout: 3000 });
        if (data.checks?.features && data.checks?.wards) return 'live' as const;
        console.warn('API is up but not ready (missing features/wards) - using mock data', data.checks);
      } catch {
        console.warn(`API unreachable at ${API_BASE_URL} - using mock data`);
      }
      return 'mock' as const;
    })().then((source) => {
      useFloodStore.getState().setDataSource(source);
      return source;
    });
    return this.source;
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
    return this.call(async () => (await this.client.get<Ward[]>('/wards')).data, mockApi.getWards);
  }

  async getWard(wardId: number): Promise<WardFeature> {
    return this.call(
      async () => (await this.client.get<WardFeature>(`/wards/${wardId}`)).data,
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
      async () => (await this.client.post<RiskResponse>('/risk', input)).data,
      () => mockApi.getRisk(input)
    );
  }

  async getScenarioRisk(input: ScenarioInput): Promise<RiskResponse> {
    return this.call(
      async () => (await this.client.post<RiskResponse>('/scenario', input)).data,
      () => mockApi.getScenarioRisk(input)
    );
  }

  async getValidation(): Promise<ValidationMetrics> {
    return this.call(async () => (await this.client.get<ValidationMetrics>('/validation')).data, mockApi.getValidation);
  }

  async generateAlerts(
    wardIds: number[],
    rainfallMm: number,
    language: 'en' | 'ta' = 'en',
    channels: ('sms' | 'whatsapp' | 'voice' | 'livekit')[] = ['sms', 'whatsapp']
  ): Promise<AlertResponse> {
    return this.call(
      async () =>
        (
          await this.client.post<AlertResponse>('/alerts', {
            ward_ids: wardIds,
            rainfall_mm: rainfallMm,
            language,
            channels,
          })
        ).data,
      () => mockApi.generateAlerts(wardIds, rainfallMm, language, channels)
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
        (
          await this.client.post<Shelter[]>('/shelters', {
            latitude,
            longitude,
            max_distance_km: maxDistanceKm,
            max_results: maxResults,
          })
        ).data,
      () => mockApi.findShelters(latitude, longitude, maxDistanceKm, maxResults)
    );
  }

  async getRoadRisk(rainfallMm: number): Promise<RoadRisk[]> {
    return this.call(
      async () => (await this.client.get<RoadRisk[]>('/roads/risk', { params: { rainfall_mm: rainfallMm } })).data,
      () => mockApi.getRoadRisk(rainfallMm)
    );
  }
}

export const api = new ApiClient();
