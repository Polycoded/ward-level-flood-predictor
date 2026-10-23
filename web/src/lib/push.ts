// Phone notifications: Web Push when the backend has VAPID keys, otherwise local
// notifications shown by our service worker while the alert pipeline is in preview.

import type { BroadcastAlert } from '../types';
import type { Language } from './store';

const VAPID_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY;

export type PushSupport = 'supported' | 'needs-install' | 'unsupported';

const isIos = () => /iPhone|iPad|iPod/i.test(navigator.userAgent);
const isStandalone = () =>
  window.matchMedia?.('(display-mode: standalone)').matches || (navigator as { standalone?: boolean }).standalone === true;

export function pushSupport(): PushSupport {
  if (typeof window === 'undefined' || !('Notification' in window)) return isIos() ? 'needs-install' : 'unsupported';
  if (isIos() && !isStandalone()) return 'needs-install';
  // Notifications work without a service worker (shown by the page while open); a worker
  // is only needed for background Web Push, which enablePush() handles when available.
  return 'supported';
}

function urlBase64ToBuffer(base64: string): ArrayBuffer {
  const padded = (base64 + '='.repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(padded);
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return bytes.buffer;
}

async function registration(timeoutMs = 4000): Promise<ServiceWorkerRegistration | null> {
  if (!('serviceWorker' in navigator)) return null;
  return Promise.race([
    navigator.serviceWorker.ready,
    new Promise<null>((resolve) => setTimeout(() => resolve(null), timeoutMs)),
  ]);
}

export interface EnableResult {
  permission: NotificationPermission | 'unsupported';
  /** Web Push subscription for the backend; null when the browser or server can't do push */
  subscription: { endpoint: string; keys?: Record<string, string> } | null;
}

export async function enablePush(): Promise<EnableResult> {
  if (pushSupport() !== 'supported') return { permission: 'unsupported', subscription: null };
  const permission = Notification.permission === 'granted' ? 'granted' : await Notification.requestPermission();
  if (permission !== 'granted' || !VAPID_KEY) return { permission, subscription: null };
  const reg = await registration();
  if (!reg || !('pushManager' in reg)) return { permission, subscription: null };
  const sub =
    (await reg.pushManager.getSubscription()) ??
    (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToBuffer(VAPID_KEY) }));
  const json = sub.toJSON();
  return { permission, subscription: json.endpoint ? { endpoint: json.endpoint, keys: json.keys } : null };
}

export async function disablePush(): Promise<void> {
  const reg = await registration(1500);
  const sub = await reg?.pushManager?.getSubscription();
  await sub?.unsubscribe().catch(() => undefined);
}

/** Show an alert as a phone notification (preview delivery, or when the page is open). */
export async function notifyAlert(alert: BroadcastAlert, language: Language, title: string): Promise<void> {
  if (!('Notification' in window) || Notification.permission !== 'granted') return;
  const payload = { id: alert.id, ward_id: alert.ward_id, level: alert.level, title, body: alert.messages[language] };
  const reg = await registration(1500);
  if (reg?.active) {
    reg.active.postMessage({ type: 'SHOW_ALERT', payload });
    return;
  }
  // no service worker (dev server): plain notification
  new Notification(title, { body: payload.body, tag: `ward-${alert.ward_id}`, icon: '/icons/icon-192.png' });
}

export function registerServiceWorker(): void {
  const enabled = import.meta.env.PROD || import.meta.env.VITE_ENABLE_SW === 'true';
  if (!enabled || !('serviceWorker' in navigator)) return;
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((error) => console.warn('Service worker not registered', error));
  });
}
