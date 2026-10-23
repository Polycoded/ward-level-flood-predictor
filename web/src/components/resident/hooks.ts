import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
import { useFloodStore } from '../../lib/store';
import { WardIndex, type WardMatch } from '../../lib/wardLookup';
import { fetchOpenMeteoForecast } from '../../lib/rainfall';
import { readJson, writeJson } from '../../lib/persist';
import type { BroadcastAlert, WardRisk } from '../../types';

// --- ward shapes (once per page) -------------------------------------------

let indexPromise: Promise<WardIndex> | null = null;

export function loadWardIndex(): Promise<WardIndex> {
  indexPromise ??= api.getWardsLite().then((wards) => new WardIndex(wards)).catch((error) => {
    indexPromise = null; // allow a retry
    throw error;
  });
  return indexPromise;
}

export function useWardIndex() {
  const [index, setIndex] = useState<WardIndex | null>(null);
  const [error, setError] = useState(false);
  const load = useCallback(() => {
    setError(false);
    loadWardIndex().then(setIndex).catch(() => setError(true));
  }, []);
  useEffect(load, [load]);
  return { index, error, retry: load };
}

// --- "where am I" ----------------------------------------------------------

export type LocateError = 'denied' | 'unavailable' | 'outside' | 'unsupported';

export function locate(index: WardIndex): Promise<WardMatch> {
  return new Promise((resolve, reject) => {
    if (!('geolocation' in navigator)) return reject('unsupported' satisfies LocateError);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const match = index.find(pos.coords.latitude, pos.coords.longitude);
        if (match) resolve(match);
        else reject('outside' satisfies LocateError);
      },
      (err) => reject((err.code === err.PERMISSION_DENIED ? 'denied' : 'unavailable') satisfies LocateError),
      { enableHighAccuracy: true, timeout: 15_000, maximumAge: 60_000 }
    );
  });
}

// --- my ward's risk from the live forecast ------------------------------------

const FORECAST_HOURS = 6;
const FORECAST_TTL_MS = 15 * 60_000;
let forecastCache: { at: number; promise: Promise<{ rainfall_mm: number; duration_hours: number; wards: WardRisk[] }> } | null = null;

function cityForecastRisk() {
  if (forecastCache && Date.now() - forecastCache.at < FORECAST_TTL_MS) return forecastCache.promise;
  const promise = fetchOpenMeteoForecast(FORECAST_HOURS).then(async (reading) => {
    const risk = await api.getScenarioRisk({
      rainfall_mm: reading.rainfall_mm,
      duration_hours: reading.duration_hours,
      builtup_increase_pct: 0,
    });
    return { rainfall_mm: reading.rainfall_mm, duration_hours: reading.duration_hours, wards: risk.wards };
  });
  forecastCache = { at: Date.now(), promise };
  promise.catch(() => (forecastCache = null));
  return promise;
}

export function resetForecastCache() {
  forecastCache = null;
}

export function useWardForecast(wardId: number | null) {
  const [state, setState] = useState<
    | { status: 'idle' }
    | { status: 'loading' }
    | { status: 'error' }
    | { status: 'ready'; ward: WardRisk | null; rainfall_mm: number; duration_hours: number }
  >({ status: 'idle' });

  const load = useCallback(() => {
    if (wardId === null) return;
    let cancelled = false;
    setState({ status: 'loading' });
    cityForecastRisk()
      .then((f) => {
        if (!cancelled) setState({ status: 'ready', ward: f.wards.find((w) => w.ward_id === wardId) ?? null, rainfall_mm: f.rainfall_mm, duration_hours: f.duration_hours });
      })
      .catch(() => !cancelled && setState({ status: 'error' }));
    return () => {
      cancelled = true;
    };
  }, [wardId]);

  useEffect(() => load(), [load]);
  return { state, retry: () => void load() };
}

// --- active alerts for my ward --------------------------------------------------

const SEEN_KEY = 'flood-seen-alerts';
const POLL_MS = 30_000;

export function useActiveAlerts(wardId: number | null, onNew: (alert: BroadcastAlert) => void) {
  const [alerts, setAlerts] = useState<BroadcastAlert[]>([]);
  const onNewRef = useRef(onNew);
  onNewRef.current = onNew;

  useEffect(() => {
    if (wardId === null) {
      setAlerts([]);
      return;
    }
    let cancelled = false;
    const check = () => {
      api
        .getActiveAlerts(wardId)
        .then((list) => {
          if (cancelled) return;
          setAlerts(list);
          const seen = new Set(readJson<string[]>(SEEN_KEY, []));
          const fresh = list.filter((a) => !seen.has(a.id));
          if (fresh.length) {
            writeJson(SEEN_KEY, [...seen, ...fresh.map((a) => a.id)].slice(-200));
            fresh.forEach((a) => onNewRef.current(a));
          }
        })
        .catch(() => undefined); // keep showing the last known alerts
    };
    check();
    const timer = window.setInterval(check, POLL_MS);
    const onVisible = () => document.visibilityState === 'visible' && check();
    // the in-browser preview stores alerts in localStorage; another tab approving one fires this
    const onStorage = (e: StorageEvent) => e.key?.startsWith('flood-mock-alerts') && check();
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('storage', onStorage);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('storage', onStorage);
    };
  }, [wardId]);

  return alerts;
}

// --- keep the subscription's ward current while the app is open ----------------

const MIN_UPDATE_MS = 60_000;
const FOLLOW_KEY = 'flood-follow-location';

export const readFollowPreference = () => readJson<boolean>(FOLLOW_KEY, true);
export const writeFollowPreference = (on: boolean) => writeJson(FOLLOW_KEY, on);

/**
 * Like Where Is My Train: position is matched to a ward on the phone. When two readings in a
 * row agree on a new ward, the subscription moves; only the ward number is sent.
 */
export function useFollowLocation(index: WardIndex | null, enabled: boolean, onMoved: (wardName: string) => void) {
  const { resident, setMyWard, setSubscription } = useFloodStore();
  const lastUpdate = useRef(0);
  const candidate = useRef<number | null>(null);
  const onMovedRef = useRef(onMoved);
  onMovedRef.current = onMoved;
  const subscription = resident.subscription;

  useEffect(() => {
    if (!index || !enabled || !subscription || !('geolocation' in navigator)) return;
    const id = navigator.geolocation.watchPosition(
      (pos) => {
        const match = index.find(pos.coords.latitude, pos.coords.longitude);
        if (!match || match.ward.ward_id === subscription.ward_id) {
          candidate.current = null;
          return;
        }
        if (candidate.current !== match.ward.ward_id) {
          candidate.current = match.ward.ward_id; // wait for a second reading
          return;
        }
        if (Date.now() - lastUpdate.current < MIN_UPDATE_MS) return;
        lastUpdate.current = Date.now();
        api
          .updateSubscription(subscription.id, match.ward.ward_id)
          .then((updated) => {
            setSubscription(updated);
            setMyWard(updated.ward_id);
            onMovedRef.current(match.ward.ward_name);
          })
          .catch(() => undefined);
      },
      () => undefined,
      { enableHighAccuracy: false, maximumAge: 60_000, timeout: 30_000 }
    );
    return () => navigator.geolocation.clearWatch(id);
  }, [index, enabled, subscription, setMyWard, setSubscription]);
}
