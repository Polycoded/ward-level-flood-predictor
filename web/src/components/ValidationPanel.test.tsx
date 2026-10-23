import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ValidationPanel } from './ValidationPanel';
import { parseValidation, unavailableValidation } from '../lib/validation';
import { useFloodStore } from '../lib/store';
import type { EvidenceMetric, ValidationMetrics } from '../types';

afterEach(cleanup);

const observed: EvidenceMetric = { value: 0.5, numerator: 1, denominator: 2, unavailable_reason: null };
const missing: EvidenceMetric = { value: null, numerator: 1, denominator: 2, unavailable_reason: 'Selected wards include unknown status' };
const partial: ValidationMetrics = {
  schema_version: '2.0', status: 'partial', status_reason: null,
  event_metadata: { event_name: 'Artificial test only', event_date: '2000-01-01', rainfall_mm: 100, duration_hours: 3 },
  metrics: { precision_at_k: missing, precision_among_observed_selected: observed,
    recall_among_observed_flooded: observed, false_positive_rate_among_observed_non_flooded: missing },
  coverage: { prediction_universe: observed, selected: observed },
  warnings: ['Artificial observations only'],
};

describe('evidence status presentation', () => {
  it('renders metadata missing a required measurement as unavailable without accuracy values', () => {
    render(<ValidationPanel data={{ ...partial, event_metadata: {
      event_name: 'Artificial test only', event_date: '2000-01-01', rainfall_mm: 100,
    } }} />);
    expect(screen.getByText('Status: unavailable')).toBeInTheDocument();
    expect(screen.getByText('Invalid event rainfall or duration.')).toBeInTheDocument();
    expect(screen.queryByText('Observed-sample metrics')).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/%|NaN|undefined/);
  });

  it('renders unavailable without accuracy cards or invented event', () => {
    render(<ValidationPanel data={unavailableValidation('Reviewed labels absent')} />);
    expect(screen.getByText('Status: unavailable')).toBeInTheDocument();
    expect(screen.getByText('Reviewed labels absent')).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/%|Dec 2023|NaN|undefined/);
    expect(screen.queryByText('Observed-sample metrics')).not.toBeInTheDocument();
  });

  it('renders partial coverage, null reasons and supplied event metadata', () => {
    render(<ValidationPanel data={partial} />);
    expect(screen.getByText('Status: partial')).toBeInTheDocument();
    expect(screen.getByText('Observation coverage')).toBeInTheDocument();
    expect(screen.getByText('Prediction universe: 50.0%')).toBeInTheDocument();
    expect(screen.getByText('precision at k: Unavailable')).toBeInTheDocument();
    expect(screen.getAllByText('Selected wards include unknown status')).toHaveLength(2);
    expect(screen.getByText('Event: Artificial test only')).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/NaN|undefined|: 0\.0%/);
  });

  it('does not promote schema-2 unavailable metrics to accuracy', () => {
    render(<ValidationPanel data={{ ...partial, status: 'unavailable', status_reason: 'No known observations' }} />);
    expect(screen.getByText('Metric availability')).toBeInTheDocument();
    expect(screen.getByText('precision among observed selected: Unavailable')).toBeInTheDocument();
  });

  it('renders evaluated with its observed-sample caveat', () => {
    render(<ValidationPanel data={{ ...partial, status: 'evaluated' }} />);
    expect(screen.getByText('Status: evaluated')).toBeInTheDocument();
    expect(screen.getByText(/do not establish city-wide accuracy/)).toBeInTheDocument();
  });

  it.each([
    { precision_at_20: 0.65, notes: 'MOCK NUMBERS' },
    { precision_at_20: 0.65 },
    { ...partial, notes: 'MOCK NUMBERS' },
    { ...partial, metrics: { ...partial.metrics, precision_at_k: { ...observed, value: NaN } } },
  ])('suppresses mock, legacy and invalid metric accuracy at all boundaries', (payload) => {
    const parsed = parseValidation(payload);
    expect(parsed.status).toBe('unavailable');
    useFloodStore.getState().setValidationData(payload as unknown as ValidationMetrics);
    expect(useFloodStore.getState().validationData?.status).toBe('unavailable');
    render(<ValidationPanel data={payload as unknown as ValidationMetrics} />);
    expect(document.body.textContent).not.toMatch(/65\.0%|NaN|undefined/);
    expect(screen.queryByText('Observed-sample metrics')).not.toBeInTheDocument();
  });
});
