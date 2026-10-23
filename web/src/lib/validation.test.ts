import { describe, expect, it } from 'vitest';
import { parseValidation, unavailableValidation } from './validation';

// Artificial parser fixtures only, not observations or accuracy evidence.
const fraction = (numerator = 1, denominator = 3) => ({
  value: numerator / denominator, numerator, denominator, unavailable_reason: null,
});
const nullMetric = (numerator = 0, denominator = 0) => ({
  value: null, numerator, denominator, unavailable_reason: 'No eligible observations',
});
const payload = () => ({
  schema_version: '2.0', status: 'evaluated', status_reason: null, warnings: [],
  event_metadata: { event_name: 'Artificial fixture', rainfall_mm: 100, duration_hours: 3 },
  metrics: {
    precision_at_k: fraction(), precision_among_observed_selected: fraction(),
    recall_among_observed_flooded: fraction(),
    false_positive_rate_among_observed_non_flooded: nullMetric(),
  },
  coverage: { prediction_universe: fraction(), selected: fraction() },
});

describe('validation parser boundaries', () => {
  it.each(['partial', 'evaluated', 'unavailable'])('preserves valid %s output and fractional/null metrics', status => {
    const input = { ...payload(), status, status_reason: status === 'unavailable' ? 'No known observations' : null };
    expect(parseValidation(input)).toBe(input);
  });

  it('keeps the minimal unavailable envelope valid without inventing metrics', () => {
    const input = unavailableValidation('Reviewed evidence absent');
    expect(parseValidation(input)).toBe(input);
    expect(parseValidation({ ...input, metrics: null, coverage: null, event_metadata: null })).toEqual({
      ...input, metrics: null, coverage: null, event_metadata: null,
    });
  });

  const entries = [
    ['metrics', 'precision_at_k'], ['metrics', 'precision_among_observed_selected'],
    ['metrics', 'recall_among_observed_flooded'], ['metrics', 'false_positive_rate_among_observed_non_flooded'],
    ['coverage', 'prediction_universe'], ['coverage', 'selected'],
  ] as const;

  it.each(entries)('rejects numerator > denominator in %s.%s, even with a null value', (section, key) => {
    const input = payload();
    Object.assign((input[section] as Record<string, object>)[key], nullMetric(4, 3));
    expect(parseValidation(input).status).toBe('unavailable');
    expect(parseValidation(input).metrics).toBeUndefined();
  });

  it.each(entries)('rejects inconsistent available arithmetic in %s.%s', (section, key) => {
    const input = payload();
    Object.assign((input[section] as Record<string, object>)[key], fraction(1, 1), { value: 0.25 });
    expect(parseValidation(input).status).toBe('unavailable');
  });

  it.each([
    ['rainfall_mm', -1], ['rainfall_mm', 501], ['rainfall_mm', true], ['rainfall_mm', false],
    ['rainfall_mm', NaN], ['rainfall_mm', Infinity], ['rainfall_mm', -Infinity], ['rainfall_mm', '100'],
    ['duration_hours', 0], ['duration_hours', 0.5], ['duration_hours', 25], ['duration_hours', 1000],
    ['duration_hours', true], ['duration_hours', false], ['duration_hours', NaN],
    ['duration_hours', Infinity], ['duration_hours', -Infinity], ['duration_hours', '3'],
  ])('rejects invalid event %s=%s independently', (field, invalid) => {
    const input = payload();
    Object.assign(input.event_metadata, { [String(field)]: invalid });
    expect(parseValidation(input).status).toBe('unavailable');
    expect(parseValidation(input).metrics).toBeUndefined();
  });

  it.each([[0, 1], [500, 24], [0.5, 1.5]])('accepts valid rainfall/duration %s/%s', (rainfall_mm, duration_hours) => {
    const input = payload();
    Object.assign(input.event_metadata, { rainfall_mm, duration_hours });
    expect(parseValidation(input)).toBe(input);
  });

  it.each([{ rainfall_mm: null, duration_hours: 3 }, {}, [], { duration_hours: 3 }, { rainfall_mm: 100 }])('rejects malformed present evaluator metadata: %s', metadata => {
    const input = { ...payload(), event_metadata: metadata };
    expect(parseValidation(input).status).toBe('unavailable');
  });

  it.each([5e-13, -5e-13])('accepts absolute roundoff %s without repairing it', delta => {
    const input = payload();
    input.metrics.precision_at_k.value += delta;
    expect(parseValidation(input)).toBe(input);
  });

  it.each([2e-12, -2e-12])('rejects arithmetic error %s beyond the absolute 1e-12 tolerance', delta => {
    const input = payload();
    input.coverage.selected.value += delta;
    expect(parseValidation(input).status).toBe('unavailable');
  });

  it('accepts legitimate null metrics with zero or nonzero denominators', () => {
    const input = payload();
    Object.assign(input.metrics.precision_at_k, nullMetric(1, 3));
    expect(parseValidation(input)).toBe(input);
  });

  it.each([
    { value: 0, numerator: 0, denominator: 0, unavailable_reason: null },
    { value: null, numerator: 0, denominator: 0, unavailable_reason: null },
    { value: 0.5, numerator: 1, denominator: 2, unavailable_reason: 'Unavailable' },
  ])('rejects invalid zero-denominator/availability combinations: %s', invalid => {
    const input = payload();
    Object.assign(input.metrics.precision_at_k, invalid);
    expect(parseValidation(input).status).toBe('unavailable');
  });

  it('does not bypass coverage validation on unavailable payloads', () => {
    const input = { ...unavailableValidation('No observations'), coverage: { selected: { ...fraction(1, 1), value: 0.25 } } };
    expect(parseValidation(input).coverage).toBeUndefined();
  });

  it.each([null, undefined, [], { precision_at_20: 0.65, notes: 'MOCK NUMBERS' }])('rejects malformed/legacy input: %s', input => {
    expect(parseValidation(input).status).toBe('unavailable');
    expect(parseValidation(input).metrics).toBeUndefined();
  });

  it('returns unavailable rather than throwing for non-JSON stored payloads', () => {
    const input: Record<string, unknown> = payload();
    input.circular = input;
    expect(parseValidation(input).status).toBe('unavailable');
  });
});
