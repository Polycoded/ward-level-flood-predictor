import { useState } from 'react';
import { api } from '../../api/client';
import { useFloodStore } from '../../lib/store';
import { useT } from '../../lib/i18n';
import { disablePush, enablePush, pushSupport } from '../../lib/push';
import type { WardLite } from '../../types';
import { Modal } from '../Modal';
import { readFollowPreference, writeFollowPreference } from './hooks';

const WHATSAPP_NUMBER = (import.meta.env.VITE_WHATSAPP_NUMBER ?? '').replace(/\D/g, '');
const HAS_VAPID = Boolean(import.meta.env.VITE_VAPID_PUBLIC_KEY);

/** Turn alerts on/off for this phone: push notifications and/or WhatsApp opt-in. */
export function SubscribeSheet({ ward, onClose }: { ward: WardLite; onClose: () => void }) {
  const t = useT();
  const { ui, resident, setSubscription } = useFloodStore();
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<'denied' | 'unsupported' | 'error' | null>(null);
  const [follow, setFollow] = useState(readFollowPreference());
  const support = pushSupport();
  const subscribed = resident.subscription?.ward_id === ward.ward_id;

  const turnOn = async () => {
    setBusy(true);
    setProblem(null);
    try {
      const result = await enablePush();
      if (result.permission === 'denied') {
        setProblem('denied');
        return;
      }
      if (result.permission === 'unsupported') {
        setProblem('unsupported');
        return;
      }
      // Without VAPID keys (alert preview) the page shows notifications itself while open.
      const push = result.subscription ?? (!HAS_VAPID && result.permission === 'granted' ? { endpoint: 'local-preview' } : null);
      if (resident.subscription) await api.deleteSubscription(resident.subscription.id).catch(() => undefined);
      const sub = await api.createSubscription({ ward_id: ward.ward_id, language: ui.language, push });
      setSubscription(sub);
    } catch {
      setProblem('error');
    } finally {
      setBusy(false);
    }
  };

  const turnOff = async () => {
    if (!resident.subscription) return;
    setBusy(true);
    try {
      await api.deleteSubscription(resident.subscription.id);
      await disablePush();
      setSubscription(null);
    } catch {
      setProblem('error');
    } finally {
      setBusy(false);
    }
  };

  const whatsappUrl = WHATSAPP_NUMBER
    ? `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(`JOIN ${ward.ward_number}`)}`
    : null;

  return (
    <Modal title={t('sub.title')} onClose={onClose}>
      <div className="p-4 space-y-5 overflow-y-auto">
        <p className="text-base text-gray-900">{t('sub.intro', { ward: ward.ward_name })}</p>

        <section className="space-y-2" aria-labelledby="sub-push-title">
          <h3 id="sub-push-title" className="font-semibold text-gray-900">🔔 {t('sub.push')}</h3>
          <p className="text-sm text-gray-700">{support === 'needs-install' ? t('sub.pushIos') : t('sub.pushHelp')}</p>
          {subscribed ? (
            <>
              <p className="text-sm font-medium text-green-800 bg-green-50 border border-green-200 rounded-lg p-2.5" role="status">
                ✓ {t('sub.on', { ward: ward.ward_name })}
              </p>
              <button onClick={turnOff} disabled={busy} className="btn-secondary w-full min-h-12">{t('sub.disable')}</button>
            </>
          ) : (
            <button onClick={turnOn} disabled={busy || support === 'unsupported'} className="btn-primary w-full min-h-12 text-base">
              {t('sub.enable')}
            </button>
          )}
          {problem && (
            <p role="alert" className="text-sm text-red-800 bg-red-50 border border-red-200 rounded-lg p-2.5">
              {problem === 'denied' ? t('sub.denied') : problem === 'unsupported' ? t('sub.unsupported') : t('sub.error')}
            </p>
          )}
          <label className="flex items-start gap-2 text-sm text-gray-800 pt-1">
            <input
              type="checkbox"
              className="w-5 h-5 mt-0.5 accent-flood-600"
              checked={follow}
              onChange={(e) => {
                setFollow(e.target.checked);
                writeFollowPreference(e.target.checked);
              }}
            />
            {t('sub.follow')}
          </label>
        </section>

        <section className="space-y-2 border-t border-gray-200 pt-4" aria-labelledby="sub-wa-title">
          <h3 id="sub-wa-title" className="font-semibold text-gray-900">💬 {t('sub.whatsapp')}</h3>
          {whatsappUrl ? (
            <>
              <p className="text-sm text-gray-700">{t('sub.whatsappHelp', { n: ward.ward_number })}</p>
              <a href={whatsappUrl} target="_blank" rel="noopener noreferrer" className="btn-secondary w-full min-h-12">
                {t('sub.whatsappOpen')}
              </a>
            </>
          ) : (
            <p className="text-sm text-gray-700">{t('sub.whatsappSoon')}</p>
          )}
        </section>

        <p className="text-xs text-gray-600 border-t border-gray-200 pt-3">{t('sub.privacy')}</p>
        <button onClick={onClose} className="btn-ghost w-full min-h-11">{t('sub.close')}</button>
      </div>
    </Modal>
  );
}
