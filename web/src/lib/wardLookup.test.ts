import { describe, expect, it } from 'vitest';
import { NEAREST_WARD_TOLERANCE_M, WardIndex, pointInGeometry } from './wardLookup';
import { geometryCenter } from './geo';
import { mockApi } from '../api/mock';
import { validateWardsLite } from '../api/validate';
import type { WardLite } from '../types';

const square = (id: number, x0: number, y0: number, size = 0.01): WardLite => ({
  ward_id: id, ward_number: String(id), ward_name: `Ward ${id}`,
  geometry: { type: 'Polygon', coordinates: [[[x0, y0], [x0 + size, y0], [x0 + size, y0 + size], [x0, y0 + size], [x0, y0]]] },
});

describe('pointInGeometry', () => {
  it('handles inside, outside and holes', () => {
    const withHole: WardLite['geometry'] = {
      type: 'Polygon',
      coordinates: [
        [[80, 13], [80.1, 13], [80.1, 13.1], [80, 13.1], [80, 13]],
        [[80.04, 13.04], [80.06, 13.04], [80.06, 13.06], [80.04, 13.06], [80.04, 13.04]],
      ],
    };
    expect(pointInGeometry(80.02, 13.02, withHole)).toBe(true);
    expect(pointInGeometry(80.05, 13.05, withHole)).toBe(false); // in the hole
    expect(pointInGeometry(80.2, 13.05, withHole)).toBe(false);
  });

  it('handles multipolygons', () => {
    const multi: WardLite['geometry'] = {
      type: 'MultiPolygon',
      coordinates: [square(1, 80, 13).geometry.coordinates as number[][][], square(1, 80.5, 13.5).geometry.coordinates as number[][][]],
    };
    expect(pointInGeometry(80.505, 13.505, multi)).toBe(true);
    expect(pointInGeometry(80.3, 13.3, multi)).toBe(false);
  });
});

describe('WardIndex', () => {
  const index = new WardIndex([square(1, 80.0, 13.0), square(2, 80.01, 13.0), square(3, 80.0, 13.01)]);

  it('finds the containing ward', () => {
    expect(index.find(13.005, 80.005)?.ward.ward_id).toBe(1);
    expect(index.find(13.005, 80.015)?.ward.ward_id).toBe(2);
    expect(index.find(13.015, 80.005)).toMatchObject({ ward: { ward_id: 3 }, exact: true });
  });

  it('snaps to the nearest ward only within the tolerance', () => {
    // ~55 m east of ward 2's east edge (80.02)
    const near = index.find(13.005, 80.0205);
    expect(near).toMatchObject({ ward: { ward_id: 2 }, exact: false });
    expect(near!.distanceM).toBeLessThanOrEqual(NEAREST_WARD_TOLERANCE_M);
    // ~1 km away: outside Chennai as far as we know
    expect(index.find(13.005, 80.03)).toBeNull();
  });

  it('rejects junk coordinates', () => {
    expect(index.find(Number.NaN, 80)).toBeNull();
    expect(index.find(13, Number.POSITIVE_INFINITY)).toBeNull();
  });

  it('lists wards in ward-number order', () => {
    const shuffled = new WardIndex([square(10, 80, 13), square(2, 80.2, 13), square(1, 80.4, 13)]);
    expect(shuffled.list().map((w) => w.ward_number)).toEqual(['1', '2', '10']);
  });

  it('maps every ward centre back to its own ward (200 mock wards)', () => {
    const wards = validateWardsLite(mockApi.getWards());
    const all = new WardIndex(wards);
    for (const w of wards) {
      const c = geometryCenter(w.geometry)!;
      expect(all.find(c.lat, c.lng)?.ward.ward_id).toBe(w.ward_id);
    }
  });
});
