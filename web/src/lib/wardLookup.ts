// On-device "which ward am I in?" — the Where Is My Train idea: the phone works out its
// position against data it already holds, so the server never receives coordinates.

import type { WardLite } from '../types';

type Ring = number[][];

/** Ray casting; points exactly on an edge may land either side, which the nearest-ward fallback covers. */
export function pointInRing(lng: number, lat: number, ring: Ring): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > lat !== yj > lat && lng < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function pointInPolygon(lng: number, lat: number, rings: Ring[]): boolean {
  if (!rings.length || !pointInRing(lng, lat, rings[0])) return false;
  // holes (inner rings) are not part of the ward
  return !rings.slice(1).some((hole) => pointInRing(lng, lat, hole));
}

export function pointInGeometry(lng: number, lat: number, geometry: WardLite['geometry']): boolean {
  return geometry.type === 'Polygon'
    ? pointInPolygon(lng, lat, geometry.coordinates)
    : geometry.coordinates.some((poly) => pointInPolygon(lng, lat, poly));
}

const M_PER_DEG_LAT = 111_320;

/** Approximate metres from a point to a segment (equirectangular; fine at city scale). */
function distanceToSegmentM(lng: number, lat: number, a: number[], b: number[]): number {
  const kx = M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);
  const ax = (a[0] - lng) * kx, ay = (a[1] - lat) * M_PER_DEG_LAT;
  const bx = (b[0] - lng) * kx, by = (b[1] - lat) * M_PER_DEG_LAT;
  const dx = bx - ax, dy = by - ay;
  const len2 = dx * dx + dy * dy;
  const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, -(ax * dx + ay * dy) / len2));
  return Math.hypot(ax + t * dx, ay + t * dy);
}

function distanceToGeometryM(lng: number, lat: number, geometry: WardLite['geometry']): number {
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
  let best = Infinity;
  for (const rings of polygons) {
    for (const ring of rings) {
      for (let i = 1; i < ring.length; i++) best = Math.min(best, distanceToSegmentM(lng, lat, ring[i - 1], ring[i]));
    }
  }
  return best;
}

interface Bounds { minLng: number; minLat: number; maxLng: number; maxLat: number }

function bounds(geometry: WardLite['geometry']): Bounds {
  const b = { minLng: Infinity, minLat: Infinity, maxLng: -Infinity, maxLat: -Infinity };
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
  for (const rings of polygons) for (const [lng, lat] of rings[0]) {
    b.minLng = Math.min(b.minLng, lng); b.maxLng = Math.max(b.maxLng, lng);
    b.minLat = Math.min(b.minLat, lat); b.maxLat = Math.max(b.maxLat, lat);
  }
  return b;
}

export interface WardMatch {
  ward: WardLite;
  /** false when the point fell in a small gap between ward shapes and the nearest ward was used */
  exact: boolean;
  distanceM: number;
}

/** Points this close to a ward (gaps from shape simplification, GPS error) still match it. */
export const NEAREST_WARD_TOLERANCE_M = 150;

export class WardIndex {
  private entries: { ward: WardLite; box: Bounds }[];

  constructor(wards: WardLite[]) {
    this.entries = wards.map((ward) => ({ ward, box: bounds(ward.geometry) }));
  }

  get size(): number {
    return this.entries.length;
  }

  find(lat: number, lng: number): WardMatch | null {
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
    for (const { ward, box } of this.entries) {
      if (lng < box.minLng || lng > box.maxLng || lat < box.minLat || lat > box.maxLat) continue;
      if (pointInGeometry(lng, lat, ward.geometry)) return { ward, exact: true, distanceM: 0 };
    }
    // Not inside any shape: accept the nearest ward only if it is very close.
    const pad = NEAREST_WARD_TOLERANCE_M / M_PER_DEG_LAT;
    let best: WardMatch | null = null;
    for (const { ward, box } of this.entries) {
      if (lng < box.minLng - pad * 2 || lng > box.maxLng + pad * 2 || lat < box.minLat - pad || lat > box.maxLat + pad) continue;
      const d = distanceToGeometryM(lng, lat, ward.geometry);
      if (d <= NEAREST_WARD_TOLERANCE_M && (!best || d < best.distanceM)) best = { ward, exact: false, distanceM: d };
    }
    return best;
  }

  /** Wards in ward-number order, for the "choose my ward" list. */
  list(): WardLite[] {
    const num = (w: WardLite) => Number.parseInt(w.ward_number, 10);
    return this.entries
      .map((e) => e.ward)
      .sort((a, b) => (num(a) - num(b)) || a.ward_name.localeCompare(b.ward_name));
  }

  get(wardId: number): WardLite | undefined {
    return this.entries.find((e) => e.ward.ward_id === wardId)?.ward;
  }
}
