import { describe, expect, it } from 'vitest';
import { isPlaceholderValidation } from './validation';
import type { ValidationMetrics } from '../types';

const metrics = (notes: string): ValidationMetrics => ({
  precision_at_20: 0.65, recall: 0.72, false_positive_rate: 0.04, true_positives: 13,
  false_positives: 7, false_negatives: 5, total_flooded_wards: 18, total_wards: 200,
  event_date: '2023-12-04', notes,
});

describe('isPlaceholderValidation', () => {
  it('flags the file currently on main', () => {
    expect(isPlaceholderValidation(metrics('MOCK NUMBERS: placeholder until validation_metrics.json from the real Dec 2023 run is committed.'), 'live')).toBe(true);
  });

  it.each(['template values', 'INCOMPLETE event metadata', 'synthetic labels', 'dummy run'])('flags notes saying "%s"', (n) => {
    expect(isPlaceholderValidation(metrics(n), 'live')).toBe(true);
  });

  it('always flags metrics shown in mock mode', () => {
    expect(isPlaceholderValidation(metrics('Evaluated on 18 SAR-labelled wards'), 'mock')).toBe(true);
  });

  it('does not flag a real evaluation from the live API', () => {
    expect(isPlaceholderValidation(metrics('Evaluated on 18 wards labelled from Sentinel-1 SAR and GCC reports'), 'live')).toBe(false);
  });

  it('does not trip on words that merely contain a marker', () => {
    expect(isPlaceholderValidation(metrics('Examples of misses discussed in docs; templated report layout'), 'live')).toBe(false);
  });
});
