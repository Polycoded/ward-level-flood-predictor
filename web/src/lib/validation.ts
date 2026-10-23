import type { ValidationMetrics } from '../types';
import type { DataSource } from './store';

const PLACEHOLDER_MARKERS = /\b(mock|placeholder|template|incomplete|synthetic|dummy|example)\b/i;

/**
 * True when the metrics must not be presented as a real evaluation: the app is in mock
 * mode, or the file says so itself (main currently ships the frontend's mock numbers in
 * data/processed/validation_metrics.json with "MOCK NUMBERS" in notes).
 */
export function isPlaceholderValidation(v: ValidationMetrics, source: DataSource): boolean {
  return source === 'mock' || PLACEHOLDER_MARKERS.test(v.notes ?? '');
}
