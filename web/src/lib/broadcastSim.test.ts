import { describe, expect, it } from 'vitest';
import { buildWorld, DEFAULTS, distanceKm, planBroadcast, TIMING } from './broadcastSim';
import { WardIndex } from './wardLookup';
import { validateWardsLite } from '../api/validate';
import { mockApi } from '../api/mock';

const wards = validateWardsLite(mockApi.getWards());
const world = buildWorld(wards, { phones: 2000 });
const index = new WardIndex(wards);

describe('buildWorld', () => {
  it('is deterministic for a seed', () => {
    const again = buildWorld(wards, { phones: 2000 });
    expect(again.towers).toEqual(world.towers);
    expect(again.phones).toEqual(world.phones);
    expect(buildWorld(wards, { phones: 2000, seed: 99 }).phones).not.toEqual(world.phones);
  });

  it('places every phone inside the ward it claims', () => {
    expect(world.phones).toHaveLength(2000);
    for (const p of world.phones.slice(0, 500)) expect(index.find(p.lat, p.lng)?.ward.ward_id).toBe(p.wardId);
  });

  it('spreads towers across the city and attaches phones only within range', () => {
    expect(world.towers.length).toBeGreaterThan(50);
    const byId = new Map(world.towers.map((t) => [t.id, t]));
    for (const p of world.phones) {
      if (p.towerId === null) continue;
      expect(distanceKm(p, byId.get(p.towerId)!)).toBeLessThanOrEqual(DEFAULTS.towerRangeKm);
    }
    // the realistic shares come out roughly as configured
    const share = (f: (p: (typeof world.phones)[number]) => boolean) => world.phones.filter(f).length / world.phones.length;
    expect(share((p) => p.push)).toBeCloseTo(DEFAULTS.pushShare, 1);
    expect(share((p) => p.whatsapp)).toBeCloseTo(DEFAULTS.whatsappShare, 1);
  });
});

describe('planBroadcast', () => {
  const target = world.phones[0].wardId;
  const plan = planBroadcast(world, [target]);
  const phone = new Map(world.phones.map((p) => [p.id, p]));

  it('only towers serving the target ward broadcast', () => {
    const serving = new Set(world.phones.filter((p) => p.wardId === target && p.towerId !== null).map((p) => p.towerId));
    expect(new Set(plan.broadcastingTowers.map((t) => t.towerId))).toEqual(serving);
  });

  it('app/WhatsApp reach only subscribed phones in the target ward', () => {
    for (const d of plan.deliveries.filter((x) => x.path === 'app')) {
      const p = phone.get(d.phoneId)!;
      expect(p.wardId).toBe(target);
      expect(p.push || p.whatsapp).toBe(true);
      expect(d.atMs).toBeGreaterThanOrEqual(TIMING.appMinMs);
    }
  });

  it('cell broadcast reaches everyone under the towers, including phones outside the ward', () => {
    for (const d of plan.deliveries.filter((x) => x.path === 'cell')) {
      const p = phone.get(d.phoneId)!;
      expect(plan.broadcastingTowers.some((t) => t.towerId === p.towerId)).toBe(true);
      expect(d.inTargetWard).toBe(p.wardId === target);
      expect(d.atMs).toBeGreaterThanOrEqual(TIMING.towerStartMs);
    }
    expect(plan.stats.cellReachedOutsideTarget).toBeGreaterThan(0);
  });

  it('never delivers to phones without signal', () => {
    const dead = new Set(world.phones.filter((p) => p.noSignal).map((p) => p.id));
    expect(plan.deliveries.some((d) => dead.has(d.phoneId))).toBe(false);
  });

  it('keeps the counts consistent', () => {
    const s = plan.stats;
    expect(s.reachedAnyInTarget).toBeLessThanOrEqual(s.phonesInTargetWards);
    expect(s.cellReached - s.cellReachedOutsideTarget + s.cellMissedInTarget).toBe(s.phonesInTargetWards);
    expect(s.appReached).toBeLessThanOrEqual(s.appEligibleInTarget);
    expect(plan.deliveries.map((d) => d.atMs)).toEqual([...plan.deliveries.map((d) => d.atMs)].sort((a, b) => a - b));
  });

  it('an empty target sends nothing', () => {
    const none = planBroadcast(world, []);
    expect(none.deliveries).toEqual([]);
    expect(none.broadcastingTowers).toEqual([]);
  });
});
