// Stand-in for the backend alert pipeline (scheduler → pending alerts → approval →
// dispatch) until John's endpoints exist. State lives in localStorage so an official
// tab and a resident tab on the same laptop see the same alerts during a demo.
// Rules here are deliberately simple placeholders for Mit's model/alert_rules.py.

import type {
  BroadcastAlert,
  BroadcastLevel,
  Language,
  SubscriptionChannel,
  RiskResponse,
  Subscription,
  SubscriptionRequest,
} from '../types';

const KEY = 'flood-mock-alerts-v1';
const ACTIVE_HOURS = 12;
const REPEAT_HOURS = 6;
const MAX_WARDS_PER_RUN = 25;

interface MockState {
  alerts: BroadcastAlert[];
  subscriptions: (Subscription & { push: boolean })[];
}

let memory: MockState = { alerts: [], subscriptions: [] };

function load(): MockState {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) memory = JSON.parse(raw) as MockState;
  } catch {
    /* private mode or corrupt value: keep the in-memory copy */
  }
  return memory;
}

function save(state: MockState): void {
  memory = state;
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* storage full or blocked: memory still works for this tab */
  }
}

export function resetMockAlerts(): void {
  save({ alerts: [], subscriptions: [] });
}

const LEVEL_RANK: Record<BroadcastLevel, number> = { watch: 1, warning: 2 };
const LEVEL_TEXT: Record<Language, Record<BroadcastLevel, string>> = {
  en: { watch: 'WATCH', warning: 'WARNING' },
  ta: { watch: 'கவனம்', warning: 'எச்சரிக்கை' },
};

export function alertMessages(ward: string, level: BroadcastLevel, mm: number, hours: number, exercise: boolean): Record<Language, string> {
  const drillEn = exercise ? 'EXERCISE - ' : '';
  const drillTa = exercise ? 'பயிற்சி - ' : '';
  return {
    en: `${drillEn}Flood risk ${LEVEL_TEXT.en[level]} for ${ward}. Estimate from ${mm}mm rain over ${hours}h; uncalibrated, not a flood forecast. Avoid floodwater and follow official advice. Helpline 1913.`,
    ta: `${drillTa}${ward}: வெள்ள அபாயம் - ${LEVEL_TEXT.ta[level]}. ${mm}மி.மீ / ${hours} மணி நேர மழை மதிப்பீடு; அளவுத்திருத்தம் செய்யப்படாதது, வெள்ள முன்னறிவிப்பு அல்ல. வெள்ள நீரைத் தவிர்த்து அதிகாரிகளின் அறிவுரையைப் பின்பற்றவும். உதவி எண் 1913.`,
  };
}

const hoursAgo = (iso: string | null | undefined) => (iso ? (Date.now() - new Date(iso).getTime()) / 3_600_000 : Infinity);

/** Placeholder rule: high → watch, very_high → warning; no repeat unless it worsens. */
export function runAlertCheck(risk: RiskResponse, exercise = true): BroadcastAlert[] {
  const state = load();
  const created: BroadcastAlert[] = [];
  const candidates = risk.wards
    .filter((w) => w.risk_level === 'high' || w.risk_level === 'very_high')
    .sort((a, b) => b.risk_score - a.risk_score)
    .slice(0, MAX_WARDS_PER_RUN);

  for (const w of candidates) {
    const level: BroadcastLevel = w.risk_level === 'very_high' ? 'warning' : 'watch';
    // pending, sent or cancelled by an official: all count as "already decided" for this window
    const recent = state.alerts.filter((a) => a.ward_id === w.ward_id && hoursAgo(a.created_at) < REPEAT_HOURS);
    if (recent.some((a) => LEVEL_RANK[a.level] >= LEVEL_RANK[level])) continue;
    const alert: BroadcastAlert = {
      id: `mock-${w.ward_id}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`,
      ward_id: w.ward_id,
      ward_name: w.ward_name,
      level,
      risk_level: w.risk_level,
      risk_score: w.risk_score,
      rainfall_mm: risk.scenario.rainfall_mm,
      duration_hours: risk.scenario.duration_hours,
      created_at: new Date().toISOString(),
      status: 'pending',
      exercise,
      messages: alertMessages(w.ward_name, level, risk.scenario.rainfall_mm, risk.scenario.duration_hours, exercise),
      approved_at: null,
      delivery: null,
    };
    created.push(alert);
  }
  save({ ...state, alerts: [...created, ...state.alerts].slice(0, 500) });
  return created;
}

export function listPending(): BroadcastAlert[] {
  return load().alerts.filter((a) => a.status === 'pending');
}

export function listActive(wardId: number): BroadcastAlert[] {
  return load().alerts.filter(
    (a) => a.ward_id === wardId && a.status === 'approved' && hoursAgo(a.approved_at) < ACTIVE_HOURS
  );
}

export function getAlert(id: string): BroadcastAlert | null {
  return load().alerts.find((a) => a.id === id) ?? null;
}

function setStatus(id: string, status: 'approved' | 'cancelled'): BroadcastAlert {
  const state = load();
  const alert = state.alerts.find((a) => a.id === id);
  if (!alert) throw new Error('Alert not found');
  if (alert.status !== 'pending') throw new Error(`Alert already ${alert.status}`);
  const subs = state.subscriptions.filter((s) => s.ward_id === alert.ward_id);
  const updated: BroadcastAlert =
    status === 'approved'
      ? {
          ...alert,
          status,
          approved_at: new Date().toISOString(),
          delivery: {
            push_sent: subs.filter((s) => s.push).length,
            whatsapp_queued: subs.filter((s) => s.channels.includes('whatsapp')).length,
          },
        }
      : { ...alert, status };
  save({ ...state, alerts: state.alerts.map((a) => (a.id === id ? updated : a)) });
  return updated;
}

export const approveAlert = (id: string) => setStatus(id, 'approved');
export const cancelAlert = (id: string) => setStatus(id, 'cancelled');

const toPublic = (s: Subscription): Subscription => ({ id: s.id, ward_id: s.ward_id, language: s.language, channels: s.channels });

export function createSubscription(req: SubscriptionRequest): Subscription {
  const state = load();
  const sub = {
    id: `sub-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    ward_id: req.ward_id,
    language: req.language,
    channels: (req.push ? ['push'] : []) as SubscriptionChannel[],
    push: req.push !== null,
  };
  save({ ...state, subscriptions: [...state.subscriptions, sub].slice(-1000) });
  return toPublic(sub);
}

export function updateSubscription(id: string, wardId: number): Subscription {
  const state = load();
  const sub = state.subscriptions.find((s) => s.id === id);
  if (!sub) throw new Error('Subscription not found');
  const next = { ...sub, ward_id: wardId };
  save({ ...state, subscriptions: state.subscriptions.map((s) => (s.id === id ? next : s)) });
  return toPublic(next);
}

export function deleteSubscription(id: string): void {
  const state = load();
  save({ ...state, subscriptions: state.subscriptions.filter((s) => s.id !== id) });
}

export function subscriberCount(wardId: number): number {
  return load().subscriptions.filter((s) => s.ward_id === wardId).length;
}
