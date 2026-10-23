// Per-factor breakdown of a ward's static susceptibility score.
// Mirrors WEIGHTS / normalize() in model/risk_engine.py — keep the two in sync.

export interface FactorInputs {
  elevation_mean: number;
  slope_mean: number;
  impervious_frac: number;
  dist_to_water_m: number;
  road_density: number;
  underpass_count: number;
}

export interface FactorContribution {
  key: keyof typeof WEIGHTS;
  label: string;
  rawValue: string;
  /** 0..1, higher = worse for flooding */
  normalized: number;
  weight: number;
  /** weight * normalized, the points this factor adds to the 0..1 base score */
  contribution: number;
  direction: string;
}

export const WEIGHTS = {
  elevation: 0.25,
  slope: 0.15,
  impervious: 0.25,
  water_proximity: 0.15,
  road_density: 0.1,
  underpass: 0.1,
} as const;

export function normalize(value: number, min: number, max: number, invert = false): number {
  if (max === min) return 0.5;
  const n = Math.min(1, Math.max(0, (value - min) / (max - min)));
  return invert ? 1 - n : n;
}

/** Feature dicts come in two shapes: WardRisk.features uses `road_density`, WardFeature uses `road_density_km_per_sqkm`. */
export function toFactorInputs(features: Record<string, number | undefined>): FactorInputs {
  return {
    elevation_mean: features.elevation_mean ?? 10,
    slope_mean: features.slope_mean ?? 2,
    impervious_frac: features.impervious_frac ?? 0.5,
    dist_to_water_m: features.dist_to_water_m ?? 1000,
    road_density: features.road_density ?? features.road_density_km_per_sqkm ?? 5,
    underpass_count: features.underpass_count ?? 0,
  };
}

export function factorContributions(f: FactorInputs, builtupIncreasePct = 0): FactorContribution[] {
  const impervious = Math.min(f.impervious_frac * (1 + builtupIncreasePct / 100), 1);
  const rows: Omit<FactorContribution, 'contribution'>[] = [
    {
      key: 'elevation',
      label: 'Low elevation',
      rawValue: `${f.elevation_mean.toFixed(1)} m mean`,
      normalized: normalize(f.elevation_mean, 0, 50, true),
      weight: WEIGHTS.elevation,
      direction: 'Lower ground collects runoff',
    },
    {
      key: 'impervious',
      label: 'Paved / built-up surface',
      rawValue: `${Math.round(impervious * 100)}%`,
      normalized: normalize(impervious, 0, 1),
      weight: WEIGHTS.impervious,
      direction: 'Less rain soaks into the ground',
    },
    {
      key: 'slope',
      label: 'Flat terrain',
      rawValue: `${f.slope_mean.toFixed(1)}° mean slope`,
      normalized: normalize(f.slope_mean, 0, 15, true),
      weight: WEIGHTS.slope,
      direction: 'Water drains away slowly',
    },
    {
      key: 'water_proximity',
      label: 'Near river / canal / lake',
      rawValue: `${Math.round(f.dist_to_water_m)} m away`,
      normalized: normalize(f.dist_to_water_m, 0, 5000, true),
      weight: WEIGHTS.water_proximity,
      direction: 'Overflow and drain backflow',
    },
    {
      key: 'road_density',
      label: 'Dense road network',
      rawValue: `${f.road_density.toFixed(1)} km/km²`,
      normalized: normalize(f.road_density, 0, 20),
      weight: WEIGHTS.road_density,
      direction: 'Proxy for dense urbanisation',
    },
    {
      key: 'underpass',
      label: 'Underpasses',
      rawValue: `${f.underpass_count}`,
      normalized: f.underpass_count > 0 ? 1 : 0,
      weight: WEIGHTS.underpass,
      direction: 'Known waterlogging points',
    },
  ];
  return rows.map((r) => ({ ...r, contribution: r.weight * r.normalized }));
}

export function baseSusceptibility(f: FactorInputs, builtupIncreasePct = 0): number {
  return factorContributions(f, builtupIncreasePct).reduce((sum, c) => sum + c.contribution, 0);
}

/**
 * Bounded duration heuristic from model/risk_engine.py: the same rain over a shorter
 * window counts more, anchored to 3 h. sqrt(3 / h) clamped to [0.5, 1.5].
 */
export function durationFactor(durationHours = 3): number {
  return Math.min(1.5, Math.max(0.5, Math.sqrt(3 / durationHours)));
}

/** Rainfall scaling applied to the susceptibility score: (mm / 200) × duration factor, capped at 1.5. */
/** Same bands as RISK_THRESHOLDS in model/risk_engine.py; a score of exactly 1 is very_high. */
export function classifyRisk(score: number): 'very_low' | 'low' | 'moderate' | 'high' | 'very_high' {
  if (score < 0.2) return 'very_low';
  if (score < 0.35) return 'low';
  if (score < 0.55) return 'moderate';
  if (score < 0.75) return 'high';
  return 'very_high';
}

export function rainfallFactor(rainfallMm: number, durationHours = 3): number {
  return Math.min((rainfallMm / 200) * durationFactor(durationHours), 1.5);
}
