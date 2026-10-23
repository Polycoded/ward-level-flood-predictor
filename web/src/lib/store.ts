import { create } from 'zustand';
import type { Ward, WardFeature, RiskResponse, ValidationMetrics, Shelter, RoadRisk } from '../types';
import type { RainfallReading } from './rainfall';
import { parseValidation } from './validation';

export type DataSource = 'unknown' | 'live' | 'mock';

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
  error: string | null;
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
    language: 'en' | 'ta';
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
  setScenario: (scenario: Partial<FloodState['scenario']>) => void;
  setMapView: (view: FloodState['ui']['mapView']) => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  setDetailWard: (wardId: number | null) => void;
  setAlertsOpen: (open: boolean) => void;
  setValidationOpen: (open: boolean) => void;
  setLanguage: (lang: 'en' | 'ta') => void;
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
  error: null,
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
    language: 'en',
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
  setScenario: (scenario) => set((state) => ({ scenario: { ...state.scenario, ...scenario } })),
  setMapView: (mapView) => set((state) => ({ ui: { ...state.ui, mapView } })),
  toggleSidebar: () => set((state) => ({ ui: { ...state.ui, sidebarOpen: !state.ui.sidebarOpen } })),
  setSidebarOpen: (sidebarOpen) => set((state) => ({ ui: { ...state.ui, sidebarOpen } })),
  setDetailWard: (detailWardId) => set((state) => ({ ui: { ...state.ui, detailWardId } })),
  setAlertsOpen: (alertsOpen) => set((state) => ({ ui: { ...state.ui, alertsOpen } })),
  setValidationOpen: (validationOpen) => set((state) => ({ ui: { ...state.ui, validationOpen } })),
  setLanguage: (language) => set((state) => ({ ui: { ...state.ui, language } })),
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
