import { useFloodStore } from '../lib/store';
import { cn } from '../lib/utils';
import { scenarioDelta } from '../lib/scenario';

const OPTIONS = [
  { value: 0, label: 'Today' },
  { value: 15, label: '+15% built-up' },
  { value: 30, label: '+30% built-up' },
];

/** Planning view (Demo Act 5): same rain, more paved city. */
export function FutureScenarioToggle({ onChange, busy }: { onChange: (builtupPct: number) => void; busy: boolean }) {
  const { riskData, baselineRisk, scenario } = useFloodStore();
  if (!riskData) return null;

  const delta = baselineRisk && scenario.builtup_increase_pct > 0 ? scenarioDelta(riskData, baselineRisk) : null;

  return (
    <div className="absolute top-3 right-3 z-10 card p-2 sm:p-3 shadow-lg w-56 sm:w-64 max-w-[calc(100%-1.5rem)]">
      <p className="hidden sm:block text-xs font-semibold text-gray-900 uppercase tracking-wide mb-2">Land-use scenario</p>
      <div className="grid grid-cols-3 gap-1" role="group" aria-label="Future land-use scenario">
        {OPTIONS.map((o) => (
          <button
            key={o.value}
            disabled={busy}
            onClick={() => onChange(o.value)}
            aria-pressed={scenario.builtup_increase_pct === o.value}
            className={cn(
              'px-1.5 py-1.5 rounded-md text-xs font-medium border leading-tight',
              scenario.builtup_increase_pct === o.value
                ? 'bg-flood-700 text-white border-flood-700'
                : 'bg-white text-gray-800 border-gray-300 hover:bg-gray-50'
            )}
          >
            {o.label}
          </button>
        ))}
      </div>
      <p className={delta ? 'text-xs text-gray-700 mt-2' : 'hidden sm:block text-xs text-gray-700 mt-2'} aria-live="polite">
        {delta
          ? `${delta.worse} ward${delta.worse === 1 ? '' : 's'} move up a risk level; average score +${(delta.avgScoreChange * 100).toFixed(1)} vs today.`
          : 'Compare the same rainfall with more paved surface.'}
      </p>
    </div>
  );
}
