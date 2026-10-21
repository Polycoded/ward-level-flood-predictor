import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import type {
  Ward,
  WardFeature,
  WardRisk,
  RiskResponse,
  RainfallInput,
  ScenarioInput,
  AlertMessage,
  AlertResponse,
  ValidationMetrics,
  Shelter,
  RoadRisk,
  HealthResponse,
  ReadyResponse,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

class ApiClient {
  private client: AxiosInstance;

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

  async healthCheck(): Promise<HealthResponse> {
    const response = await this.client.get<HealthResponse>('/healthz');
    return response.data;
  }

  async readyCheck(): Promise<ReadyResponse> {
    const response = await this.client.get<ReadyResponse>('/readyz');
    return response.data;
  }

  async getWards(): Promise<Ward[]> {
    const response = await this.client.get<Ward[]>('/wards');
    return response.data;
  }

  async getWard(wardId: number): Promise<WardFeature> {
    const response = await this.client.get<WardFeature>(`/wards/${wardId}`);
    return response.data;
  }

  async getWardsGeoJSON(): Promise<GeoJSON.FeatureCollection> {
    const response = await this.client.get<GeoJSON.FeatureCollection>('/wards/geojson');
    return response.data;
  }

  async getRisk(input: RainfallInput): Promise<RiskResponse> {
    const response = await this.client.post<RiskResponse>('/risk', input);
    return response.data;
  }

  async getScenarioRisk(input: ScenarioInput): Promise<RiskResponse> {
    const response = await this.client.post<RiskResponse>('/scenario', input);
    return response.data;
  }

  async getValidation(): Promise<ValidationMetrics> {
    const response = await this.client.get<ValidationMetrics>('/validation');
    return response.data;
  }

  async generateAlerts(
    wardIds: number[],
    rainfallMm: number,
    language: 'en' | 'ta' = 'en',
    channels: ('sms' | 'whatsapp' | 'voice' | 'livekit')[] = ['sms', 'whatsapp']
  ): Promise<AlertResponse> {
    const response = await this.client.post<AlertResponse>('/alerts', {
      ward_ids: wardIds,
      rainfall_mm: rainfallMm,
      language,
      channels,
    });
    return response.data;
  }

  async findShelters(
    latitude: number,
    longitude: number,
    maxDistanceKm: number = 5,
    maxResults: number = 5
  ): Promise<Shelter[]> {
    const response = await this.client.post<Shelter[]>('/shelters', {
      latitude,
      longitude,
      max_distance_km: maxDistanceKm,
      max_results: maxResults,
    });
    return response.data;
  }

  async getRoadRisk(rainfallMm: number): Promise<RoadRisk[]> {
    const response = await this.client.get<RoadRisk[]>('/roads/risk', {
      params: { rainfall_mm: rainfallMm },
    });
    return response.data;
  }
}

export const api = new ApiClient();