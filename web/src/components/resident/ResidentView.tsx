import { useCallback, useState } from 'react';
import { useFloodStore } from '../../lib/store';
import { translate, useT } from '../../lib/i18n';
import { notifyAlert } from '../../lib/push';
import type { BroadcastAlert } from '../../types';
import { RiskStatusCard } from './RiskStatusCard';
import { ShelterList } from './ShelterList';
import { SubscribeSheet } from './SubscribeSheet';
import { WardPicker } from './WardPicker';
import { readFollowPreference, useActiveAlerts, useFollowLocation, useWardIndex } from './hooks';

/** The simple screen for people in Chennai: my ward, my risk, where to go, get alerts. */
export function ResidentView() {
  const t = useT();
  const { ui, resident, alertsPreview, dataSource, setMyWard, setLanguage, setMode, setOpenAlert } = useFloodStore();
  const { index, error, retry } = useWardIndex();
  const [picking, setPicking] = useState(false);
  const [showShelters, setShowShelters] = useState(false);
  const [subscribeOpen, setSubscribeOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const ward = resident.wardId !== null && index ? index.get(resident.wardId) ?? null : null;
  const wardList = index ? index.list() : [];

  const onNewAlert = useCallback(
    (alert: BroadcastAlert) => {
      const title = translate(ui.language, alert.level === 'warning' ? 'alert.warning' : 'alert.watch');
      notifyAlert(alert, ui.language, `${title} · ${alert.ward_name}`).catch(() => undefined);
      setOpenAlert(alert.id);
    },
    [ui.language, setOpenAlert]
  );
  const activeAlerts = useActiveAlerts(ward?.ward_id ?? null, onNewAlert);

  useFollowLocation(index, readFollowPreference(), (wardName) => {
    setToast(t('sub.moved', { ward: wardName }));
    window.setTimeout(() => setToast(null), 5000);
  });

  const pick = (wardId: number) => {
    setMyWard(wardId);
    setPicking(false);
    setShowShelters(false);
  };

  const subscribed = ward !== null && resident.subscription?.ward_id === ward.ward_id;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-20">
        <div className="max-w-md mx-auto px-4 py-3 flex items-center gap-3">
          <img src="/icons/icon-192.png" alt="" className="w-9 h-9 rounded-lg" width={36} height={36} />
          <h1 className="text-base font-bold text-gray-900 leading-tight flex-1">{t('app.title')}</h1>
          <button
            onClick={() => setLanguage(ui.language === 'en' ? 'ta' : 'en')}
            className="btn-secondary min-h-11 px-3"
            aria-label={`${t('lang.label')}: ${t('lang.other')}`}
            lang={ui.language === 'en' ? 'ta' : 'en'}
          >
            {t('lang.other')}
          </button>
        </div>
      </header>

      {dataSource === 'mock' && (
        <p role="note" className="bg-amber-100 text-amber-950 text-sm font-medium text-center px-4 py-2 border-b border-amber-200">
          {t('demo.banner')}
        </p>
      )}
      {alertsPreview && dataSource !== 'mock' && (
        <p className="bg-sky-50 text-sky-900 text-xs text-center px-4 py-1.5 border-b border-sky-100">
          <strong>{t('preview.badge')}:</strong> {t('preview.help')}
        </p>
      )}

      <main className="max-w-md mx-auto p-4 space-y-4 pb-24">
        {activeAlerts.length > 0 && (
          <button
            onClick={() => setOpenAlert(activeAlerts[0].id)}
            className={`w-full text-left rounded-xl p-4 shadow ${activeAlerts[0].level === 'warning' ? 'bg-red-700 text-white' : 'bg-amber-400 text-gray-950'}`}
          >
            <span className="block text-sm font-medium">{t('alert.active')}</span>
            <span className="block text-xl font-bold">
              ⚠️ {t(activeAlerts[0].level === 'warning' ? 'alert.warning' : 'alert.watch')} · {t('alert.view')} →
            </span>
          </button>
        )}

        <section className="card p-4" aria-labelledby="my-ward-title">
          <h2 id="my-ward-title" className="sr-only">{t('ward.title')}</h2>
          {error && (
            <div className="space-y-2" role="alert">
              <p className="text-gray-800">{t('ward.unavailable')}</p>
              <button onClick={retry} className="btn-secondary min-h-11">{t('status.retry')}</button>
            </div>
          )}
          {!error && (ward && !picking ? (
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm text-gray-700">{t('ward.title')}</p>
                <p className="text-2xl font-bold text-gray-900">{ward.ward_name}</p>
              </div>
              <button onClick={() => setPicking(true)} className="btn-secondary min-h-11">{t('ward.change')}</button>
            </div>
          ) : (
            <WardPicker index={index} wards={wardList} onPick={pick} />
          ))}
        </section>

        {ward && !picking && (
          <>
            <RiskStatusCard wardId={ward.ward_id} />

            <nav className="grid grid-cols-2 gap-3" aria-label={t('ward.title')}>
              <button
                onClick={() => setShowShelters((v) => !v)}
                aria-expanded={showShelters}
                className="card min-h-24 p-3 flex flex-col items-center justify-center gap-1 text-center font-semibold text-gray-900 hover:bg-gray-50"
              >
                <span className="text-2xl" aria-hidden="true">🏫</span>
                {t('action.shelter')}
              </button>
              <button
                onClick={() => setSubscribeOpen(true)}
                className={`card min-h-24 p-3 flex flex-col items-center justify-center gap-1 text-center font-semibold hover:bg-gray-50 ${subscribed ? 'text-green-800 border-green-300' : 'text-gray-900'}`}
              >
                <span className="text-2xl" aria-hidden="true">{subscribed ? '✅' : '🔔'}</span>
                {subscribed ? t('action.alertsOn') : t('action.alerts')}
              </button>
              <a href="tel:1913" className="card min-h-20 p-3 flex flex-col items-center justify-center gap-1 text-center font-semibold text-gray-900 hover:bg-gray-50">
                <span className="text-2xl" aria-hidden="true">📞</span>
                {t('action.call')}
              </a>
              <a href="tel:112" className="card min-h-20 p-3 flex flex-col items-center justify-center gap-1 text-center font-semibold text-gray-900 hover:bg-gray-50">
                <span className="text-2xl" aria-hidden="true">🚨</span>
                {t('action.emergency')}
              </a>
            </nav>

            {showShelters && <ShelterList ward={ward} />}
          </>
        )}

        <p className="text-center pt-4">
          <button onClick={() => setMode('official')} className="text-sm text-gray-600 underline underline-offset-2">
            {t('mode.official')} →
          </button>
        </p>
      </main>

      {toast && (
        <p role="status" className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-gray-900 text-white text-sm rounded-lg px-4 py-2 shadow-lg max-w-[90vw]">
          {toast}
        </p>
      )}

      {subscribeOpen && ward && <SubscribeSheet ward={ward} onClose={() => setSubscribeOpen(false)} />}
    </div>
  );
}
