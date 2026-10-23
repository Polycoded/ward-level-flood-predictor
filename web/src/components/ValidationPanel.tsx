import { useFloodStore } from '../lib/store';
import { cn } from '../lib/utils';
import type { ValidationMetrics } from '../types';
import { isPlaceholderValidation } from '../lib/validation';

interface ValidationPanelProps {
  data?: ValidationMetrics;
}

export function ValidationPanel({ data }: ValidationPanelProps) {
  const { validationData, dataSource, setValidationOpen } = useFloodStore();
  const validation = data || validationData;
  
  if (!validation) return null;

  const { precision_at_20, recall, false_positive_rate, true_positives, false_positives, false_negatives, total_flooded_wards, total_wards, notes } = validation;
  const placeholder = isPlaceholderValidation(validation, dataSource);

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 bg-white border-t border-gray-200 rounded-t-2xl shadow-xl max-h-[70vh] flex flex-col lg:bottom-4 lg:left-4 lg:top-20 lg:right-auto lg:w-[26rem] lg:rounded-xl lg:max-h-none lg:shadow-2xl">
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <h2 className="font-semibold text-gray-900 flex items-center gap-2">
          <svg className="w-5 h-5 text-flood-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Dec 2023 Validation
        </h2>
        <button onClick={() => setValidationOpen(false)} className="p-2 rounded-lg hover:bg-gray-100 text-gray-500" aria-label="Close validation">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {placeholder && (
          <div role="alert" className="text-sm text-amber-900 bg-amber-50 border border-amber-300 rounded-lg p-3">
            <p className="font-semibold">Placeholder numbers, not a validation result</p>
            <p className="mt-1">
              These metrics are not from an evidence-backed Dec 2023 evaluation. Do not quote them. The real
              figures come from the model owner's evaluation run (docs/validation.md).
            </p>
          </div>
        )}
        <div className={cn('grid grid-cols-3 gap-3', placeholder && 'opacity-50')}>
          <MetricCard
            label="Precision@20"
            value={`${(precision_at_20 * 100).toFixed(1)}%`}
            color="flood"
            description={`TP: ${true_positives} / 20`}
          />
          <MetricCard
            label="Recall"
            value={`${(recall * 100).toFixed(1)}%`}
            color="green"
            description={`TP: ${true_positives} / ${total_flooded_wards}`}
          />
          <MetricCard
            label="False Positive Rate"
            value={`${(false_positive_rate * 100).toFixed(1)}%`}
            color="red"
            description={`FP: ${false_positives}`}
          />
        </div>

        <div className="border-t border-gray-100 pt-4">
          <h3 className="font-medium text-gray-900 mb-3">Confusion Matrix</h3>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="p-3 bg-green-50 rounded-lg border border-green-100">
              <p className="text-green-800 font-medium">True Positives</p>
              <p className="text-2xl font-bold text-green-900">{true_positives}</p>
            </div>
            <div className="p-3 bg-red-50 rounded-lg border border-red-100">
              <p className="text-red-800 font-medium">False Positives</p>
              <p className="text-2xl font-bold text-red-900">{false_positives}</p>
            </div>
            <div className="p-3 bg-yellow-50 rounded-lg border border-yellow-100">
              <p className="text-yellow-800 font-medium">False Negatives</p>
              <p className="text-2xl font-bold text-yellow-900">{false_negatives}</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
              <p className="text-gray-800 font-medium">Total Wards</p>
              <p className="text-2xl font-bold text-gray-900">{total_wards}</p>
            </div>
          </div>
        </div>

        <div className="border-t border-gray-100 pt-4">
          <h3 className="font-medium text-gray-900 mb-3">Details</h3>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Event Date</dt>
              <dd className="font-medium text-gray-900">{validation.event_date}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Total Flooded Wards</dt>
              <dd className="font-medium text-gray-900">{total_flooded_wards}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Total Wards Analyzed</dt>
              <dd className="font-medium text-gray-900">{total_wards}</dd>
            </div>
          </dl>
        </div>

        {notes && (
          <div className="border-t border-gray-100 pt-4">
            <h3 className="font-medium text-gray-900 mb-2">Notes</h3>
            <p className="text-sm text-gray-600">{notes}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function MetricCard({ label, value, color, description }: { label: string; value: string; color: 'flood' | 'green' | 'red'; description: string }) {
  const colors = {
    flood: { bg: 'bg-flood-50', border: 'border-flood-100', text: 'text-flood-900', label: 'text-flood-700' },
    green: { bg: 'bg-green-50', border: 'border-green-100', text: 'text-green-900', label: 'text-green-700' },
    red: { bg: 'bg-red-50', border: 'border-red-100', text: 'text-red-900', label: 'text-red-700' },
  };
  
  const c = colors[color];

  return (
    <div className={cn('p-3 rounded-lg border', c.bg, c.border)}>
      <p className={cn('text-xs font-medium', c.label)}>{label}</p>
      <p className={cn('text-2xl font-bold', c.text)}>{value}</p>
      <p className="text-xs text-gray-500 mt-1">{description}</p>
    </div>
  );
}