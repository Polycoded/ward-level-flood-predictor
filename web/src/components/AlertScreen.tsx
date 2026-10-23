import { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { api } from '../api/client';
import { useFloodStore } from '../lib/store';
import { useT } from '../lib/i18n';
import { readJson, writeJson } from '../lib/persist';
import type { BroadcastAlert, WardLite } from '../types';
import { loadWardIndex } from './resident/hooks';
import { ShelterList } from './resident/ShelterList';

const SAFE_KEY = 'flood-safe-acks';

/** Full-screen page for an official alert: what happened, what to do, where to go. */
export function AlertScreen({ alertId, onClose }: { alertId: string; onClose: () => void }) {
  const t = useT();
  const language = useFloodStore((s) => s.ui.language);
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const [state, setState] = useState<{ status: 'loading' } | { status: 'gone' } | { status: 'ready'; alert: BroadcastAlert }>({ status: 'loading' });
  const [ward, setWard] = useState<WardLite | null>(null);
  const [safe, setSafe] = useState(() => readJson<string[]>(SAFE_KEY, []).includes(alertId));

  useEffect(() => {
    let cancelled = false;
    api
      .getAlert(alertId)
      .then((alert) => {
        if (cancelled) return;
        if (!alert || alert.status !== 'approved') return setState({ status: 'gone' });
        setState({ status: 'ready', alert });
        loadWardIndex().then((index) => !cancelled && setWard(index.get(alert.ward_id) ?? null)).catch(() => undefined);
      })
      .catch(() => !cancelled && setState({ status: 'gone' }));
    return () => {
      cancelled = true;
    };
  }, [alertId]);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const markSafe = () => {
    writeJson(SAFE_KEY, [...readJson<string[]>(SAFE_KEY, []), alertId].slice(-100));
    setSafe(true);
  };

  const alert = state.status === 'ready' ? state.alert : null;
  const warning = alert?.level === 'warning';
  const tone = warning ? 'bg-red-700' : 'bg-amber-500';
  const toneText = warning ? 'text-white' : 'text-gray-950';

  return createPortal(
    <div role="alertdialog" aria-modal="true" aria-labelledby={titleId} className="fixed inset-0 z-[60] bg-white overflow-y-auto">
      {alert?.exercise && (
        <p className="bg-gray-900 text-white text-center text-sm font-semibold py-2 px-3">{t('exercise.banner')}</p>
      )}
      <header className={`${alert ? tone : 'bg-gray-700'} ${alert ? toneText : 'text-white'} px-4 py-6`}>
        <div className="max-w-md mx-auto flex items-start justify-between gap-3">
          <div>
            <h1 id={titleId} className="text-3xl font-bold leading-tight">
              {alert ? (warning ? `⚠️ ${t('alert.warning')}` : `⚠️ ${t('alert.watch')}`) : t('alert.view')}
            </h1>
            {alert && <p className="text-lg mt-1">{t('alert.issued', { ward: alert.ward_name })}</p>}
          </div>
          <button ref={closeRef} onClick={onClose} className="rounded-lg px-3 py-2 bg-black/20 font-medium" aria-label={t('alert.close')}>
            ✕
          </button>
        </div>
      </header>

      <main className="max-w-md mx-auto p-4 space-y-4">
        {state.status === 'loading' && <p role="status" className="text-gray-700">…</p>}
        {state.status === 'gone' && <p className="text-gray-900 text-lg">{t('alert.gone')}</p>}

        {alert && (
          <>
            <section className="card p-4">
              <h2 className="text-sm font-medium text-gray-700">{t('alert.message')}</h2>
              <p className="text-lg text-gray-900 mt-1 whitespace-pre-wrap break-words" lang={language}>{alert.messages[language]}</p>
            </section>

            <section className="card p-4" aria-labelledby="alert-do-now">
              <h2 id="alert-do-now" className="text-lg font-semibold text-gray-900 mb-2">{t('alert.doNow')}</h2>
              <ol className="space-y-2 text-base text-gray-900 list-decimal pl-5">
                <li>{t('alert.tip1')}</li>
                <li>{t('alert.tip2')}</li>
                <li>{t('alert.tip3')}</li>
                <li>{t('alert.tip4')}</li>
              </ol>
            </section>

            {ward && <ShelterList ward={ward} />}

            <div className="grid grid-cols-2 gap-2">
              <a href="tel:1913" className="btn-secondary min-h-12 text-base">📞 1913</a>
              <a href="tel:112" className="btn-secondary min-h-12 text-base">🚨 112</a>
            </div>

            {safe ? (
              <p className="text-center text-green-800 font-medium py-3" role="status">✓ {t('alert.safeThanks')}</p>
            ) : (
              <button onClick={markSafe} className="w-full min-h-14 rounded-xl bg-green-700 text-white text-lg font-semibold">
                {t('alert.safe')}
              </button>
            )}
          </>
        )}
      </main>
    </div>,
    document.body
  );
}
