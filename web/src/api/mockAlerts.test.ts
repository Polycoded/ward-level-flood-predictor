import { beforeEach, describe, expect, it } from 'vitest';
import * as alerts from './mockAlerts';
import { mockApi } from './mock';

beforeEach(() => alerts.resetMockAlerts());

const heavy = () => mockApi.getScenarioRisk({ rainfall_mm: 300, duration_hours: 3, builtup_increase_pct: 0 });

describe('mock alert engine', () => {
  it('proposes watch/warning alerts only for high and very high wards, capped per run', () => {
    const created = alerts.runAlertCheck(heavy());
    expect(created.length).toBeGreaterThan(0);
    expect(created.length).toBeLessThanOrEqual(25);
    for (const a of created) {
      expect(a.status).toBe('pending');
      expect(a.level).toBe(a.risk_level === 'very_high' ? 'warning' : 'watch');
      expect(a.exercise).toBe(true);
    }
    const light = mockApi.getScenarioRisk({ rainfall_mm: 20, duration_hours: 3, builtup_increase_pct: 0 });
    alerts.resetMockAlerts();
    expect(alerts.runAlertCheck(light)).toEqual([]);
  });

  it('does not repeat an alert for the same ward unless it gets worse', () => {
    const first = alerts.runAlertCheck(heavy());
    expect(alerts.runAlertCheck(heavy())).toEqual([]);
    expect(alerts.listPending()).toHaveLength(first.length);
  });

  it('approval makes an alert active for its ward only, with delivery counts', () => {
    const [a] = alerts.runAlertCheck(heavy());
    alerts.createSubscription({ ward_id: a.ward_id, language: 'ta', push: { endpoint: 'local-preview' } });
    alerts.createSubscription({ ward_id: a.ward_id + 1, language: 'en', push: { endpoint: 'local-preview' } });
    expect(alerts.listActive(a.ward_id)).toEqual([]);
    const approved = alerts.approveAlert(a.id);
    expect(approved.delivery).toEqual({ push_sent: 1, whatsapp_queued: 0 });
    expect(alerts.listActive(a.ward_id).map((x) => x.id)).toEqual([a.id]);
    expect(alerts.listActive(a.ward_id + 1)).toEqual([]);
    expect(() => alerts.approveAlert(a.id)).toThrow(/already approved/);
  });

  it('cancelled alerts never become active, and are not re-proposed straight away', () => {
    const [a] = alerts.runAlertCheck(heavy());
    alerts.cancelAlert(a.id);
    expect(alerts.listActive(a.ward_id)).toEqual([]);
    expect(alerts.listPending().find((x) => x.id === a.id)).toBeUndefined();
    expect(alerts.runAlertCheck(heavy()).find((x) => x.ward_id === a.ward_id)).toBeUndefined();
  });

  it('messages are honest: drill label, uncalibrated, no depth or timing', () => {
    const m = alerts.alertMessages('Ward 168', 'warning', 120, 6, true);
    expect(m.en).toMatch(/^EXERCISE/);
    expect(m.en).toMatch(/uncalibrated, not a flood forecast/);
    expect(m.ta).toMatch(/^பயிற்சி/);
    for (const text of [m.en, m.ta]) expect(text).not.toMatch(/deep|peak|up to|metre|\d+(\.\d+)?m\b/);
  });

  it('subscriptions can move ward and be deleted', () => {
    const sub = alerts.createSubscription({ ward_id: 5, language: 'en', push: null });
    expect(sub.channels).toEqual([]);
    expect(alerts.updateSubscription(sub.id, 9).ward_id).toBe(9);
    expect(alerts.subscriberCount(9)).toBe(1);
    alerts.deleteSubscription(sub.id);
    expect(alerts.subscriberCount(9)).toBe(0);
    expect(() => alerts.updateSubscription(sub.id, 1)).toThrow();
  });
});
