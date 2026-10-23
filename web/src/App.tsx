import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { useFloodStore } from './lib/store';
import { api } from './api/client';
import { cn } from './lib/utils';
import { reportError } from './lib/monitoring';
import { ApiDataError } from './api/validate';
import type { RainfallReading } from './lib/rainfall';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { MapView } from './components/MapView';
import { FutureScenarioToggle } from './components/FutureScenarioToggle';
import { LoadingOverlay } from './components/LoadingOverlay';

// Dialogs load on demand; the map is in the main bundle because its tiles are the largest paint.
const AlertPanel = lazy(() => import('./components/AlertPanel').then((m) => ({ default: m.AlertPanel })));
const ShelterPanel = lazy(() => import('./components/ShelterPanel').then((m) => ({ default: m.ShelterPanel })));
const ValidationPanel = lazy(() => import('./components/ValidationPanel').then((m) => ({ default: m.ValidationPanel })));
const WardDetailPanel = lazy(() => import('./components/WardDetailPanel').then((m) => ({ default: m.WardDetailPanel })));
const CrowdReportPanel = lazy(() => import('./components/CrowdReportPanel').then((m) => ({ default: m.CrowdReportPanel })));

function App() {
  const {
    rainfall,
    riskData,
    scenario,
    error,
    ui,
    setWards,
    setRiskData,
    setBaselineRisk,
    setRainfall,
    setRoadRisks,
    setValidationData,
    setScenario,
    setError,
    clearRiskData,
  } = useFloodStore();
  const [initialLoading, setInitialLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [reportsOpen, setReportsOpen] = useState(false);
  // one analysis at a time, even if an auto-clicker beats the disabled button's re-render
  const runningRef = useRef(false);

  useEffect(() => {
    const loadInitialData = async () => {
      try {
        const [wardsData, validation] = await Promise.all([
          api.getWards(),
          api.getValidation().catch(() => null),
        ]);
        setWards(wardsData);
        if (validation) setValidationData(validation);
      } catch (e) {
        reportError(e, { stage: 'initial-load' });
        setError(
          e instanceof ApiDataError
            ? 'The server sent ward data the dashboard could not use. Reload, or report this to the backend team.'
            : 'Could not load ward boundaries. Check that the API is running, then reload.'
        );
      } finally {
        setInitialLoading(false);
      }
    };
    loadInitialData();
  }, [setWards, setValidationData, setError]);

  const runAnalysis = async (reading: RainfallReading, builtupIncrease: number) => {
    if (runningRef.current) return;
    runningRef.current = true;
    setBusy(true);
    setError(null);
    const base = { rainfall_mm: reading.rainfall_mm, duration_hours: reading.duration_hours };
    try {
      // Everything goes through /scenario (0% = today's land use) so the current map and the
      // built-up comparison use the same endpoint and duration-aware formula.
      const [response, baseline] = await Promise.all([
        api.getScenarioRisk({ ...base, builtup_increase_pct: builtupIncrease }),
        builtupIncrease > 0 ? api.getScenarioRisk({ ...base, builtup_increase_pct: 0 }) : Promise.resolve(null),
      ]);
      setRiskData(response);
      setBaselineRisk(baseline ?? response);
      setRainfall(reading);
      setScenario({ ...base, builtup_increase_pct: builtupIncrease });
      // on phones the list covers the map; show the coloured map first
      if (window.innerWidth < 1024) useFloodStore.getState().setSidebarOpen(false);
    } catch (e) {
      reportError(e, { stage: 'risk', ...base, builtupIncrease });
      setError(
        e instanceof ApiDataError
          ? 'The server returned invalid risk data, so it was not shown. The previous result is still on screen.'
          : 'Risk analysis failed. The previous result is still shown.'
      );
    } finally {
      runningRef.current = false;
      setBusy(false);
    }
  };

  // Road layer follows the current rainfall scenario.
  useEffect(() => {
    if (ui.mapView !== 'roads' || !riskData) return;
    let cancelled = false;
    api
      .getRoadRisk(riskData.scenario.rainfall_mm)
      .then((roads) => !cancelled && setRoadRisks(roads))
      .catch((e) => {
        reportError(e, { stage: 'roads' });
        if (!cancelled) setError('Could not load road risk.');
      });
    return () => {
      cancelled = true;
    };
  }, [ui.mapView, riskData, setRoadRisks, setError]);

  return (
    <div className="h-screen bg-gray-50 flex flex-col overflow-hidden">
      <Header onClear={clearRiskData} onOpenReports={() => setReportsOpen(true)} />

      <div className="flex-1 flex overflow-hidden relative">
        <aside
          aria-label="Rainfall input and ward ranking"
          className={cn(
            'absolute inset-y-0 left-0 z-30 lg:static w-[22rem] max-w-[90vw] lg:w-96 flex-shrink-0 bg-white border-r border-gray-200 transition-transform duration-300',
            ui.sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
          )}
        >
          <Sidebar onAnalyze={(reading) => runAnalysis(reading, scenario.builtup_increase_pct)} busy={busy} />
        </aside>

        <main className="flex-1 flex flex-col min-w-0 relative">
          {error && (
            <div role="alert" className="absolute top-3 left-1/2 -translate-x-1/2 z-20 max-w-md w-[calc(100%-1.5rem)] flex items-start gap-3 bg-red-50 border border-red-200 text-red-800 text-sm rounded-lg p-3 shadow">
              <span className="flex-1">{error}</span>
              <button onClick={() => setError(null)} className="font-medium hover:text-red-900" aria-label="Dismiss error">✕</button>
            </div>
          )}
          <MapView />
          <FutureScenarioToggle busy={busy} onChange={(pct) => runAnalysis(rainfall, pct)} />
          <LoadingOverlay visible={initialLoading} message="Loading ward boundaries…" />
        </main>
      </div>

      <Suspense fallback={null}>
        {ui.detailWardId !== null && <WardDetailPanel key={ui.detailWardId} wardId={ui.detailWardId} />}
        {ui.alertsOpen && <AlertPanel onClose={() => useFloodStore.getState().setAlertsOpen(false)} />}
        {ui.mapView === 'shelters' && <ShelterPanel />}
        {ui.validationOpen && <ValidationPanel />}
        {reportsOpen && <CrowdReportPanel onClose={() => setReportsOpen(false)} />}
      </Suspense>
    </div>
  );
}

export default App;
