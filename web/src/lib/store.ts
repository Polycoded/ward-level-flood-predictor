import { create } from 'zustand';
import type { Ward, WardFeature, RiskResponse, ValidationMetrics, Shelter, RoadRisk } from '../types';

export type DataSource = 'unknown' | 'live' | 'mock';

interface FloodState {
  wards: Ward[];
  selectedWard: WardFeature | null;
  riskData: RiskResponse | null;
  validationData: ValidationMetrics | null;
  shelters: Shelter[];
  roadRisks: RoadRisk[];
  dataSource: DataSource;
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
  validationData: null,
  shelters: [],
  roadRisks: [],
  dataSource: 'unknown',
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
  setValidationData: (validationData) => set({ validationData }),
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
      selectedWard: null,
      scenario: { ...state.scenario, builtup_increase_pct: 0 },
      ui: { ...state.ui, detailWardId: null, alertsOpen: false },
    })),
}));
