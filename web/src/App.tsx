import { useEffect, useState } from 'react';
import { useFloodStore } from './lib/store';
import { api } from './api/client';
import { cn } from './lib/utils';
import { Header } from './components/Header';
import { MapView } from './components/MapView';
import { Sidebar } from './components/Sidebar';
import { AlertPanel } from './components/AlertPanel';
import { ShelterPanel } from './components/ShelterPanel';
import { ValidationPanel } from './components/ValidationPanel';
import { WardDetailPanel } from './components/WardDetailPanel';
import { LoadingOverlay } from './components/LoadingOverlay';

function App() {
  const {
    scenario,
    riskData,
    ui,
    setWards,
    setRiskData,
    setValidationData,
    setScenario,
    clearRiskData,
  } = useFloodStore();
  const [loading, setLoading] = useState<string | null>('Loading wards...');

  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    try {
      const [wardsData, validation] = await Promise.all([
        api.getWards(),
        api.getValidation().catch(() => null),
      ]);
      setWards(wardsData);
      if (validation) setValidationData(validation);
    } catch (error) {
      console.error('Failed to load initial data:', error);
    } finally {
      setLoading(null);
    }
  };

  const handleRiskAnalysis = async (rainfallMm: number, builtupIncrease: number = 0) => {
    setLoading(`Scoring wards for ${rainfallMm} mm rainfall...`);
    try {
      let response;
      if (builtupIncrease > 0) {
        response = await api.getScenarioRisk({
          rainfall_mm: rainfallMm,
          duration_hours: 3,
          builtup_increase_pct: builtupIncrease,
        });
      } else {
        response = await api.getRisk({ rainfall_mm: rainfallMm, duration_hours: 3 });
      }
      setRiskData(response);
      setScenario({ rainfall_mm: rainfallMm, builtup_increase_pct: builtupIncrease });
    } catch (error) {
      console.error('Risk analysis failed:', error);
    } finally {
      setLoading(null);
    }
  };

  const handleClearRisk = () => {
    clearRiskData();
  };

  return (
    <div className="h-screen bg-gray-50 flex flex-col overflow-hidden">
      <Header
        onAnalyze={handleRiskAnalysis}
        onClear={handleClearRisk}
        hasRiskData={!!riskData}
        scenario={scenario}
      />

      <div className="flex-1 flex overflow-hidden relative">
        <aside className={cn(
          'absolute inset-y-0 left-0 z-30 lg:static w-80 lg:w-96 flex-shrink-0 bg-white border-r border-gray-200 transition-transform duration-300',
          ui.sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}>
          <Sidebar />
        </aside>

        <main className="flex-1 flex flex-col min-w-0 relative">
          <MapView />

          {ui.detailWardId !== null && (
            <WardDetailPanel wardId={ui.detailWardId} />
          )}
        </main>

        {!ui.sidebarOpen && (
          <button
            className="absolute left-4 top-4 z-30 btn-primary rounded-full p-3 shadow-lg lg:hidden"
            onClick={() => useFloodStore.getState().setSidebarOpen(true)}
            aria-label="Open sidebar"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        )}
      </div>

      {ui.alertsOpen && <AlertPanel onClose={() => useFloodStore.getState().setAlertsOpen(false)} />}
      {ui.mapView === 'shelters' && <ShelterPanel />}
      {ui.validationOpen && <ValidationPanel />}
      <LoadingOverlay visible={loading !== null} message={loading ?? undefined} />
    </div>
  );
}

export default App;
