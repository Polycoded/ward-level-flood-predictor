// Alert-delivery simulation: synthetic cell towers and phones over the real ward map.
// Nothing here is real network or subscriber data; it exists to show how an approved
// alert travels (control room → towers → phones) and how cell broadcast compares with
// app push / WhatsApp. All randomness is seeded so a demo replays identically.

import type { WardLite } from '../types';
import { WardIndex } from './wardLookup';

export interface Tower {
  id: number;
  lat: number;
  lng: number;
}

export interface Phone {
  id: number;
  lat: number;
  lng: number;
  wardId: number;
  towerId: number | null;
  /** has the resident app with alerts on */
  push: boolean;
  /** opted in to WhatsApp alerts */
  whatsapp: boolean;
  /** basement, switched off, dead zone */
  noSignal: boolean;
}

export interface SimWorld {
  towers: Tower[];
  phones: Phone[];
  bounds: { minLat: number; maxLat: number; minLng: number; maxLng: number };
}

export interface WorldOptions {
  phones?: number;
  towerSpacingKm?: number;
  pushShare?: number;
  whatsappShare?: number;
  noSignalShare?: number;
  seed?: number;
}

export const DEFAULTS = {
  phones: 3000,
  towerSpacingKm: 1.6,
  pushShare: 0.3,
  whatsappShare: 0.2,
  noSignalShare: 0.03,
  /** a macro cell in a dense city reaches roughly this far */
  towerRangeKm: 1.6,
  seed: 7,
} as const;

const KM_PER_DEG_LAT = 111.32;
const kmPerDegLng = (lat: number) => KM_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);

export function distanceKm(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const dy = (a.lat - b.lat) * KM_PER_DEG_LAT;
  const dx = (a.lng - b.lng) * kmPerDegLng((a.lat + b.lat) / 2);
  return Math.hypot(dx, dy);
}

export function seededRandom(seed: number): () => number {
  let s = seed >>> 0 || 1;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function boundsOf(wards: WardLite[]) {
  const b = { minLat: Infinity, maxLat: -Infinity, minLng: Infinity, maxLng: -Infinity };
  for (const w of wards) {
    const polys = w.geometry.type === 'Polygon' ? [w.geometry.coordinates] : w.geometry.coordinates;
    for (const rings of polys) for (const [lng, lat] of rings[0]) {
      b.minLat = Math.min(b.minLat, lat); b.maxLat = Math.max(b.maxLat, lat);
      b.minLng = Math.min(b.minLng, lng); b.maxLng = Math.max(b.maxLng, lng);
    }
  }
  return b;
}

/** Build towers on a jittered grid over the city and drop phones inside real wards. */
export function buildWorld(wards: WardLite[], options: WorldOptions = {}): SimWorld {
  const o = { ...DEFAULTS, ...options };
  const rand = seededRandom(o.seed);
  const index = new WardIndex(wards);
  const bounds = boundsOf(wards);
  const midLat = (bounds.minLat + bounds.maxLat) / 2;
  const stepLat = o.towerSpacingKm / KM_PER_DEG_LAT;
  const stepLng = o.towerSpacingKm / kmPerDegLng(midLat);

  // Towers: keep grid points inside the city or just outside its edge.
  const towers: Tower[] = [];
  for (let lat = bounds.minLat; lat <= bounds.maxLat + stepLat / 2; lat += stepLat) {
    for (let lng = bounds.minLng; lng <= bounds.maxLng + stepLng / 2; lng += stepLng) {
      const t = { lat: lat + (rand() - 0.5) * stepLat * 0.5, lng: lng + (rand() - 0.5) * stepLng * 0.5 };
      if (index.find(t.lat, t.lng)) towers.push({ id: towers.length, ...t });
    }
  }

  // Phones: rejection-sample uniformly inside wards; each attaches to its nearest tower in range.
  const phones: Phone[] = [];
  let attempts = 0;
  while (phones.length < o.phones && attempts < o.phones * 50) {
    attempts++;
    const lat = bounds.minLat + rand() * (bounds.maxLat - bounds.minLat);
    const lng = bounds.minLng + rand() * (bounds.maxLng - bounds.minLng);
    const match = index.find(lat, lng);
    if (!match || !match.exact) continue;
    let best: { id: number; d: number } | null = null;
    for (const t of towers) {
      const d = distanceKm({ lat, lng }, t);
      if (d <= DEFAULTS.towerRangeKm && (!best || d < best.d)) best = { id: t.id, d };
    }
    phones.push({
      id: phones.length,
      lat,
      lng,
      wardId: match.ward.ward_id,
      towerId: best?.id ?? null,
      push: rand() < o.pushShare,
      whatsapp: rand() < o.whatsappShare,
      noSignal: rand() < o.noSignalShare,
    });
  }
  return { towers, phones, bounds };
}

export type DeliveryPath = 'cell' | 'app';

export interface Delivery {
  phoneId: number;
  path: DeliveryPath;
  /** ms after the alert is approved */
  atMs: number;
  inTargetWard: boolean;
}

export interface BroadcastPlan {
  targetWardIds: number[];
  broadcastingTowers: { towerId: number; startMs: number }[];
  deliveries: Delivery[];
  stats: {
    phonesInTargetWards: number;
    cellReached: number;
    cellReachedOutsideTarget: number;
    cellMissedInTarget: number;
    appReached: number;
    appEligibleInTarget: number;
    reachedAnyInTarget: number;
    lastDeliveryMs: number;
  };
}

export const TIMING = {
  /** control room → tower backhaul */
  towerStartMs: 900,
  towerJitterMs: 400,
  /** visual speed of the broadcast ring */
  ringKmPerSec: 1.2,
  /** server → push/WhatsApp providers → phone */
  appMinMs: 1200,
  appSpreadMs: 2600,
};

/**
 * Who gets the alert and when.
 * Cell broadcast: every tower serving a phone in a target ward broadcasts, and every phone
 * attached to those towers receives it — including phones just outside the ward.
 * App/WhatsApp: only subscribed phones whose ward is targeted.
 */
export function planBroadcast(world: SimWorld, targetWardIds: number[], seed = 11): BroadcastPlan {
  const rand = seededRandom(seed);
  const targets = new Set(targetWardIds);
  const towerById = new Map(world.towers.map((t) => [t.id, t]));
  const inTarget = (p: Phone) => targets.has(p.wardId);

  const towerIds = new Set<number>();
  for (const p of world.phones) if (inTarget(p) && p.towerId !== null) towerIds.add(p.towerId);
  const broadcastingTowers = [...towerIds].map((towerId) => ({
    towerId,
    startMs: TIMING.towerStartMs + Math.round(rand() * TIMING.towerJitterMs),
  }));
  const startByTower = new Map(broadcastingTowers.map((t) => [t.towerId, t.startMs]));

  const deliveries: Delivery[] = [];
  for (const p of world.phones) {
    const start = p.towerId !== null ? startByTower.get(p.towerId) : undefined;
    if (start !== undefined && !p.noSignal) {
      const tower = towerById.get(p.towerId!)!;
      const travel = (distanceKm(p, tower) / TIMING.ringKmPerSec) * 1000;
      deliveries.push({ phoneId: p.id, path: 'cell', atMs: Math.round(start + travel + rand() * 250), inTargetWard: inTarget(p) });
    }
    if (inTarget(p) && (p.push || p.whatsapp) && !p.noSignal) {
      deliveries.push({ phoneId: p.id, path: 'app', atMs: Math.round(TIMING.appMinMs + rand() * TIMING.appSpreadMs), inTargetWard: true });
    }
  }

  const cell = deliveries.filter((d) => d.path === 'cell');
  const app = deliveries.filter((d) => d.path === 'app');
  const targetPhones = world.phones.filter(inTarget);
  const reachedInTarget = new Set(deliveries.filter((d) => d.inTargetWard).map((d) => d.phoneId));
  const cellPhoneIds = new Set(cell.map((d) => d.phoneId));

  return {
    targetWardIds,
    broadcastingTowers,
    deliveries: deliveries.sort((a, b) => a.atMs - b.atMs),
    stats: {
      phonesInTargetWards: targetPhones.length,
      cellReached: cell.length,
      cellReachedOutsideTarget: cell.filter((d) => !d.inTargetWard).length,
      cellMissedInTarget: targetPhones.filter((p) => !cellPhoneIds.has(p.id)).length,
      appReached: app.length,
      appEligibleInTarget: targetPhones.filter((p) => p.push || p.whatsapp).length,
      reachedAnyInTarget: reachedInTarget.size,
      lastDeliveryMs: deliveries.reduce((m, d) => Math.max(m, d.atMs), 0),
    },
  };
}
