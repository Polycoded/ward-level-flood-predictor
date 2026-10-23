import { useFloodStore } from '../lib/store';
import { parseValidation } from '../lib/validation';
import type { EvidenceMetric, ValidationMetrics } from '../types';

export function ValidationPanel({ data }: { data?: ValidationMetrics }) {
  const { validationData, setValidationOpen } = useFloodStore();
  const validation = parseValidation(data ?? validationData);
  const metadata = validation.event_metadata;
  const eventName = typeof metadata?.event_name === 'string' ? metadata.event_name : null;
  const eventDate = typeof metadata?.event_date === 'string' ? metadata.event_date : null;
  return (
    <section aria-label="Evaluation evidence" className="fixed bottom-0 left-0 right-0 z-40 bg-white border-t border-gray-200 rounded-t-2xl shadow-xl max-h-[70vh] flex flex-col lg:bottom-4 lg:left-4 lg:top-20 lg:right-auto lg:w-[26rem] lg:rounded-xl lg:max-h-none lg:shadow-2xl">
      <header className="p-4 border-b border-gray-200 flex items-center justify-between">
        <h2 className="font-semibold text-gray-900">Evaluation evidence</h2>
        <button onClick={() => setValidationOpen(false)} aria-label="Close validation">Close</button>
      </header>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <p className="font-medium">Status: {validation.status}</p>
        {validation.status_reason && <p>{validation.status_reason}</p>}
        {eventName && <p>Event: {eventName}</p>}
        {eventDate && <p>Event date: {eventDate}</p>}
        <p className="text-sm text-gray-600">The index is uncalibrated. Caller-supplied observations and alignment are not independently verified; observed-sample metrics do not establish city-wide accuracy.</p>
        {validation.coverage && <div>
          <h3 className="font-medium">Observation coverage</h3>
          <EvidenceValue label="Prediction universe" metric={validation.coverage.prediction_universe} />
          <EvidenceValue label="Selected wards" metric={validation.coverage.selected} />
        </div>}
        {validation.metrics && <div className="space-y-3">
          <h3 className="font-medium">{validation.status === 'unavailable' ? 'Metric availability' : 'Observed-sample metrics'}</h3>
          {Object.entries(validation.metrics).map(([name, metric]) => (
            <EvidenceValue key={name} label={name.replace(/_/g, ' ')} metric={metric} suppressValue={validation.status === 'unavailable'} />
          ))}
        </div>}
        {validation.warnings.map((warning, index) => <p className="text-sm text-gray-600" key={index}>{warning}</p>)}
      </div>
    </section>
  );
}

function EvidenceValue({ label, metric, suppressValue = false }: { label: string; metric?: EvidenceMetric; suppressValue?: boolean }) {
  if (!metric) return <p>{label}: unavailable</p>;
  return <div className="text-sm border border-gray-100 rounded p-2">
    <p>{label}: {suppressValue || metric.value === null ? 'Unavailable' : `${(metric.value * 100).toFixed(1)}%`}</p>
    <p>Numerator: {metric.numerator}; denominator: {metric.denominator}</p>
    {metric.unavailable_reason && <p>{metric.unavailable_reason}</p>}
  </div>;
}
