import { describe, expect, it } from 'vitest';
import { baseSusceptibility, durationFactor, factorContributions, rainfallFactor, toFactorInputs } from './explain';
import { scoreWard } from '../api/mock';
import pythonCases from '../test/python_engine_cases.json';
import type { WardFeature } from '../types';

// Expected values were produced by running model/risk_engine.py score_ward() on these inputs,
// so the frontend's explanation and offline mode stay faithful to the real model.
const toWard = (features: Record<string, number>) =>
  ({ ward_id: 1, ward_number: '1', ward_name: 'W', area_sqkm: 1, vegetation_frac: 0, flood_prone_index: 0, ...features }) as WardFeature;

describe('parity with model/risk_engine.py', () => {
  it.each(
    pythonCases.map((c) => [`${c.rainfall_mm} mm / ${c.duration_hours} h +${c.builtup}% elev ${c.features.elevation_mean}`, c] as const)
  )('%s', (_, c) => {
    const r = scoreWard(toWard(c.features), c.rainfall_mm, c.builtup, c.duration_hours);
    expect(r.risk_score).toBeCloseTo(c.risk_score, 9);
    expect(r.risk_level).toBe(c.risk_level);
    expect(r.depth_band).toBe(c.depth_band);
    expect(r.peak_window_hours).toBe(c.peak);
  });

  it('covers a capped score, so the old "1.0 is very_low" engine bug would be caught', () => {
    expect(pythonCases.some((c) => c.risk_score === 1 && c.risk_level === 'very_high')).toBe(true);
  });
});

describe('duration factor', () => {
  it('is anchored at 3 h and bounded to [0.5, 1.5]', () => {
    expect(durationFactor(3)).toBe(1);
    expect(durationFactor(12)).toBe(0.5);
    expect(durationFactor(24)).toBe(0.5);
    expect(durationFactor(1)).toBe(1.5); // sqrt(3) = 1.73, clamped
    expect(durationFactor(2)).toBeCloseTo(Math.sqrt(1.5), 12);
  });

  it('the same rain over a longer window scores lower, never higher', () => {
    expect(rainfallFactor(150, 1)).toBeGreaterThan(rainfallFactor(150, 3));
    expect(rainfallFactor(150, 3)).toBeGreaterThan(rainfallFactor(150, 12));
    expect(rainfallFactor(500, 1)).toBe(1.5);
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
