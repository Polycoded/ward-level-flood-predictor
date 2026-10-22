import { describe, expect, it } from 'vitest';
import { baseSusceptibility, factorContributions, toFactorInputs } from './explain';
import { scoreWard } from '../api/mock';
import pythonCases from '../test/python_engine_cases.json';
import type { WardFeature } from '../types';

// Expected values were produced by running model/risk_engine.py score_ward() on these inputs,
// so the frontend's explanation and offline mode stay faithful to the real model.
const toWard = (features: Record<string, number>) =>
  ({ ward_id: 1, ward_number: '1', ward_name: 'W', area_sqkm: 1, vegetation_frac: 0, flood_prone_index: 0, ...features }) as WardFeature;

// risk_engine.py uses `low <= score < high` with very_high = (0.75, 1.0), so a score capped at
// exactly 1.0 matches no band and falls back to VERY_LOW. The frontend treats 1.0 as very_high.
const pythonCapBug = (c: (typeof pythonCases)[number]) => c.risk_score >= 1;

describe('parity with model/risk_engine.py', () => {
  it.each(pythonCases.filter((c) => !pythonCapBug(c)).map((c) => [`${c.rainfall_mm}mm +${c.builtup}% elev ${c.features.elevation_mean}`, c] as const))(
    '%s',
    (_, c) => {
      const r = scoreWard(toWard(c.features), c.rainfall_mm, c.builtup);
      expect(r.risk_score).toBeCloseTo(c.risk_score, 9);
      expect(r.risk_level).toBe(c.risk_level);
      expect(r.depth_band).toBe(c.depth_band);
      expect(r.peak_window_hours).toBe(c.peak);
    }
  );

  it('classifies a maxed-out score as very_high (Python returns very_low: known engine bug)', () => {
    const capped = pythonCases.filter(pythonCapBug);
    expect(capped.length).toBeGreaterThan(0);
    for (const c of capped) {
      expect(c.risk_level).toBe('very_low'); // documents the backend behaviour this test caught
      const r = scoreWard(toWard(c.features), c.rainfall_mm, c.builtup);
      expect(r.risk_score).toBe(1);
      expect(r.risk_level).toBe('very_high');
      expect(r.depth_band).toBe(c.depth_band);
    }
  });
});

describe('factorContributions', () => {
  const inputs = toFactorInputs({ elevation_mean: 2, slope_mean: 1, impervious_frac: 0.9, dist_to_water_m: 100, road_density: 18, underpass_count: 1 });

  it('sums to the base susceptibility score and never exceeds the weights', () => {
    const rows = factorContributions(inputs);
    const total = rows.reduce((s, r) => s + r.contribution, 0);
    expect(total).toBeCloseTo(baseSusceptibility(inputs), 12);
    for (const r of rows) {
      expect(r.contribution).toBeGreaterThanOrEqual(0);
      expect(r.contribution).toBeLessThanOrEqual(r.weight);
    }
  });

  it('applies the built-up scenario to impervious surface only', () => {
    const now = factorContributions({ ...inputs, impervious_frac: 0.5 });
    const future = factorContributions({ ...inputs, impervious_frac: 0.5 }, 30);
    const get = (rows: typeof now, key: string) => rows.find((r) => r.key === key)!.contribution;
    expect(get(future, 'impervious')).toBeGreaterThan(get(now, 'impervious'));
    expect(get(future, 'elevation')).toBe(get(now, 'elevation'));
  });

  it('accepts both feature naming schemes from the API', () => {
    expect(toFactorInputs({ road_density_km_per_sqkm: 12 }).road_density).toBe(12);
    expect(toFactorInputs({ road_density: 7 }).road_density).toBe(7);
  });
});
