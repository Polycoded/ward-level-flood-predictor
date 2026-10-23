import { lazy, Suspense, useCallback, useEffect } from 'react';
import { useFloodStore } from './lib/store';
import { AlertScreen } from './components/AlertScreen';

// Each screen downloads only its own code: phones never load the map library unless asked.
const ResidentView = lazy(() => import('./components/resident/ResidentView').then((m) => ({ default: m.ResidentView })));
const OfficialDashboard = lazy(() => import('./components/OfficialDashboard').then((m) => ({ default: m.OfficialDashboard })));
const BroadcastSimulation = lazy(() => import('./components/simulation/BroadcastSimulation').then((m) => ({ default: m.BroadcastSimulation })));

const ALERT_PARAM = 'alert';

function App() {
  const mode = useFloodStore((s) => s.ui.mode);
  const language = useFloodStore((s) => s.ui.language);
  const openAlertId = useFloodStore((s) => s.ui.openAlertId);
  const setOpenAlert = useFloodStore((s) => s.setOpenAlert);
  const simulation = useFloodStore((s) => s.ui.simulation);
  const setSimulation = useFloodStore((s) => s.setSimulation);
  const closeSimulation = useCallback(() => setSimulation(null), [setSimulation]);

  // Notification taps open /?alert=<id>
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get(ALERT_PARAM);
    if (id && /^[\w-]{1,80}$/.test(id)) setOpenAlert(id);
  }, [setOpenAlert]);

  useEffect(() => {
    document.documentElement.lang = language === 'ta' ? 'ta' : 'en';
  }, [language]);

  const closeAlert = useCallback(() => {
    setOpenAlert(null);
    const url = new URL(window.location.href);
    if (url.searchParams.has(ALERT_PARAM)) {
      url.searchParams.delete(ALERT_PARAM);
      window.history.replaceState(null, '', url.pathname + url.search + url.hash);
    }
  }, [setOpenAlert]);

  return (
    <>
      <Suspense fallback={<div className="min-h-screen bg-gray-50" aria-busy="true" />}>
        {mode === 'resident' ? <ResidentView /> : <OfficialDashboard />}
      </Suspense>
      {openAlertId && <AlertScreen alertId={openAlertId} onClose={closeAlert} />}
      {simulation && (
        <Suspense fallback={null}>
          <BroadcastSimulation request={simulation} onClose={closeSimulation} />
        </Suspense>
      )}
    </>
  );
}

export default App;
