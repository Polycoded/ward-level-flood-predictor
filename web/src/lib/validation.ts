import type { EvidenceMetric, ValidationMetrics } from '../types';

export const unavailableValidation = (reason: string): ValidationMetrics => ({
  schema_version: '2.0', status: 'unavailable', status_reason: reason, warnings: [],
});

const object = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);
// Match the API: absolute tolerance only, allowing floating-point roundoff, not rounding.
const METRIC_ABS_TOLERANCE = 1e-12;
const metric = (value: unknown): value is EvidenceMetric => object(value) &&
  Number.isInteger(value.numerator) && Number(value.numerator) >= 0 &&
  Number.isInteger(value.denominator) && Number(value.denominator) >= 0 &&
  Number(value.numerator) <= Number(value.denominator) &&
  (value.value === null ? typeof value.unavailable_reason === 'string' && !!value.unavailable_reason :
    typeof value.value === 'number' && Number.isFinite(value.value) && value.value >= 0 &&
    value.value <= 1 && Number(value.denominator) > 0 && value.unavailable_reason === null &&
    Math.abs(value.value - Number(value.numerator) / Number(value.denominator)) <= METRIC_ABS_TOLERANCE);

const measurement = (value: unknown, low: number, high: number): boolean =>
  typeof value === 'number' && Number.isFinite(value) && value >= low && value <= high;

/** Reject legacy/mock payloads even when bypassing the HTTP client (e.g. stored state). */
export function parseValidation(value: unknown): ValidationMetrics {
  if (!object(value)) {
    return unavailableValidation('Mock or invalid metrics are not accuracy evidence.');
  }
  let serialized: string;
  try {
    serialized = JSON.stringify(value);
  } catch {
    return unavailableValidation('Metrics must be a JSON-compatible object.');
  }
  if (/mock/i.test(serialized)) {
    return unavailableValidation('Mock or invalid metrics are not accuracy evidence.');
  }
  if (value.schema_version !== '2.0' || !['unavailable', 'partial', 'evaluated'].includes(String(value.status))) {
    return unavailableValidation('Unsupported legacy metrics; schema-2 evidence is required.');
  }
  if (value.status_reason !== null && typeof value.status_reason !== 'string') {
    return unavailableValidation('Invalid evidence status reason.');
  }
  if (!Array.isArray(value.warnings) || !value.warnings.every(warning => typeof warning === 'string')) {
    return unavailableValidation('Invalid evidence warnings.');
  }
  if (value.status === 'unavailable' && !value.status_reason) {
    return unavailableValidation('Evaluation evidence is unavailable.');
  }
  if (value.event_metadata !== null && value.event_metadata !== undefined &&
      (!object(value.event_metadata) ||
       !measurement(value.event_metadata.rainfall_mm, 0, 500) ||
       !measurement(value.event_metadata.duration_hours, 1, 24))) {
    return unavailableValidation('Invalid event rainfall or duration.');
  }
  const hasMetrics = value.metrics !== null && value.metrics !== undefined;
  const hasCoverage = value.coverage !== null && value.coverage !== undefined;
  if (hasMetrics || hasCoverage || value.status !== 'unavailable') {
    if (!object(value.metrics) || !object(value.coverage) ||
        !Object.values(value.metrics).every(metric) || !Object.values(value.coverage).every(metric) ||
        !['precision_at_k', 'precision_among_observed_selected', 'recall_among_observed_flooded',
          'false_positive_rate_among_observed_non_flooded'].every(key => metric((value.metrics as Record<string, unknown>)[key])) ||
        !['prediction_universe', 'selected'].every(key => metric((value.coverage as Record<string, unknown>)[key]))) {
      return unavailableValidation('Invalid schema-2 metrics or observation coverage.');
    }
  }
  return value as unknown as ValidationMetrics;
}
