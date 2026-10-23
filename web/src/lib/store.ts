import { create } from 'zustand';
import type { Ward, WardFeature, RiskResponse, ValidationMetrics, Shelter, RoadRisk, Subscription } from '../types';
import { readJson, writeJson } from './persist';
import type { RainfallReading } from './rainfall';
import { parseValidation } from './validation';

export type DataSource = 'unknown' | 'live' | 'mock';
export type AppMode = 'resident' | 'official';
export type Language = 'en' | 'ta';

const KEYS = { mode: 'flood-mode', language: 'flood-language', ward: 'flood-my-ward', subscription: 'flood-subscription' };

// Phones default to the simple resident screen; officials work on laptops.
const initialMode = (): AppMode =>
  readJson<AppMode | null>(KEYS.mode, null) ??
  (typeof window !== 'undefined' && window.innerWidth < 1024 ? 'resident' : 'official');
const initialLanguage = (): Language =>
  readJson<Language | null>(KEYS.language, null) ??
  (typeof navigator !== 'undefined' && navigator.language?.toLowerCase().startsWith('ta') ? 'ta' : 'en');

interface FloodState {
  wards: Ward[];
  selectedWard: WardFeature | null;
  riskData: RiskResponse | null;
  /** Same rainfall at today's land use, kept to show what a future scenario changes. */
  baselineRisk: RiskResponse | null;
  rainfall: RainfallReading;
  validationData: ValidationMetrics | null;
  shelters: Shelter[];
  selectedShelterId: number | null;
  shelterOrigin: { lat: number; lng: number; label: string } | null;
  roadRisks: RoadRisk[];
  dataSource: DataSource;
  /** True when alert/subscription endpoints are served by the in-browser preview, not the backend. */
  alertsPreview: boolean;
  error: string | null;
  resident: {
    wardId: number | null;
    subscription: Subscription | null;
  };
  scenario: {
    rainfall_mm: number;
    duration_hours: number;
    builtup_increase_pct: number;
  };
  ui: {
    mapView: 'risk' | 'features' | 'roads' | 'shelters';
    sidebarOpen: boolean;
    detailWardId: number | null;
    alertsOpen: boolean;
    validationOpen: boolean;
    alertQueueOpen: boolean;
    /** alert shown full-screen (from a notification, ?alert=… or a new alert for my ward) */
    openAlertId: string | null;
    language: Language;
    mode: AppMode;
  };

  setWards: (wards: Ward[]) => void;
  setSelectedWard: (ward: WardFeature | null) => void;
  setRiskData: (data: RiskResponse | null) => void;
  setBaselineRisk: (data: RiskResponse | null) => void;
  setRainfall: (reading: RainfallReading) => void;
  setSelectedShelter: (id: number | null) => void;
  setShelterOrigin: (origin: FloodState['shelterOrigin']) => void;
  setError: (message: string | null) => void;
  setValidationData: (data: ValidationMetrics | null) => void;
  setShelters: (shelters: Shelter[]) => void;
  setRoadRisks: (roads: RoadRisk[]) => void;
  setDataSource: (source: DataSource) => void;
  setAlertsPreview: (preview: boolean) => void;
  setMode: (mode: AppMode) => void;
  setMyWard: (wardId: number | null) => void;
  setSubscription: (subscription: Subscription | null) => void;
  setAlertQueueOpen: (open: boolean) => void;
  setOpenAlert: (id: string | null) => void;
  setScenario: (scenario: Partial<FloodState['scenario']>) => void;
  setMapView: (view: FloodState['ui']['mapView']) => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  setDetailWard: (wardId: number | null) => void;
  setAlertsOpen: (open: boolean) => void;
  setValidationOpen: (open: boolean) => void;
  setLanguage: (lang: Language) => void;
  clearRiskData: () => void;
}

export const useFloodStore = create<FloodState>((set) => ({
  wards: [],
  selectedWard: null,
  riskData: null,
  baselineRisk: null,
  rainfall: { rainfall_mm: 100, duration_hours: 3, source: 'manual', label: 'Manual input' },
  validationData: null,
  shelters: [],
  selectedShelterId: null,
  shelterOrigin: null,
  roadRisks: [],
  dataSource: 'unknown',
  alertsPreview: false,
  error: null,
  resident: {
    wardId: readJson<number | null>(KEYS.ward, null),
    subscription: readJson<Subscription | null>(KEYS.subscription, null),
  },
  scenario: {
    rainfall_mm: 100,
    duration_hours: 3,
    builtup_increase_pct: 0,
  },
  ui: {
    mapView: 'risk',
    sidebarOpen: true,
    detailWardId: null,
    alertsOpen: false,
    validationOpen: false,
    alertQueueOpen: false,
    openAlertId: null,
    language: initialLanguage(),
    mode: initialMode(),
  },

  setWards: (wards) => set({ wards }),
  setSelectedWard: (selectedWard) => set({ selectedWard }),
  setRiskData: (riskData) => set({ riskData }),
  setBaselineRisk: (baselineRisk) => set({ baselineRisk }),
  setRainfall: (rainfall) => set({ rainfall }),
  setSelectedShelter: (selectedShelterId) => set({ selectedShelterId }),
  setShelterOrigin: (shelterOrigin) => set({ shelterOrigin }),
  setError: (error) => set({ error }),
  setValidationData: (validationData) => set({ validationData: validationData === null ? null : parseValidation(validationData) }),
  setShelters: (shelters) => set({ shelters }),
  setRoadRisks: (roadRisks) => set({ roadRisks }),
  setDataSource: (dataSource) => set({ dataSource }),
  setAlertsPreview: (alertsPreview) => set({ alertsPreview }),
  setMode: (mode) => {
    writeJson(KEYS.mode, mode);
    set((state) => ({ ui: { ...state.ui, mode } }));
  },
  setMyWard: (wardId) => {
    writeJson(KEYS.ward, wardId);
    set((state) => ({ resident: { ...state.resident, wardId } }));
  },
  setSubscription: (subscription) => {
    writeJson(KEYS.subscription, subscription);
    set((state) => ({ resident: { ...state.resident, subscription } }));
  },
  setAlertQueueOpen: (alertQueueOpen) => set((state) => ({ ui: { ...state.ui, alertQueueOpen } })),
  setOpenAlert: (openAlertId) => set((state) => ({ ui: { ...state.ui, openAlertId } })),
  setScenario: (scenario) => set((state) => ({ scenario: { ...state.scenario, ...scenario } })),
  setMapView: (mapView) => set((state) => ({ ui: { ...state.ui, mapView } })),
  toggleSidebar: () => set((state) => ({ ui: { ...state.ui, sidebarOpen: !state.ui.sidebarOpen } })),
  setSidebarOpen: (sidebarOpen) => set((state) => ({ ui: { ...state.ui, sidebarOpen } })),
  setDetailWard: (detailWardId) => set((state) => ({ ui: { ...state.ui, detailWardId } })),
  setAlertsOpen: (alertsOpen) => set((state) => ({ ui: { ...state.ui, alertsOpen } })),
  setValidationOpen: (validationOpen) => set((state) => ({ ui: { ...state.ui, validationOpen } })),
  setLanguage: (language) => {
    writeJson(KEYS.language, language);
    set((state) => ({ ui: { ...state.ui, language } }));
  },
  clearRiskData: () =>
    set((state) => ({
      riskData: null,
      baselineRisk: null,
      roadRisks: [],
      selectedWard: null,
      scenario: { ...state.scenario, builtup_increase_pct: 0 },
      ui: { ...state.ui, detailWardId: null, alertsOpen: false },
    })),
}));
