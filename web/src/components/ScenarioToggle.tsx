import { useFloodStore } from '../lib/store';
import { cn } from '../lib/utils';

export function ScenarioToggle() {
  const { scenario, setScenario } = useFloodStore();

  return (
    <div className="p-4 border-t border-gray-200">
      <h3 className="font-medium text-gray-900 mb-3">Future Scenario</h3>
      <p className="text-sm text-gray-500 mb-4">
        Simulate impact of increased built-up area on flood risk
      </p>
      
      <div className="space-y-4">
        {[
          { value: 0, label: 'Current', desc: 'Present-day land use' },
          { value: 15, label: '+15% Built-up', desc: 'Moderate urbanization' },
          { value: 30, label: '+30% Built-up', desc: 'High urbanization' },
        ].map(({ value, label, desc }) => (
          <button
            key={value}
            onClick={() => setScenario({ builtup_increase_pct: value })}
            className={cn(
              'w-full text-left p-3 rounded-lg border transition-all',
              scenario.builtup_increase_pct === value
                ? 'bg-flood-50 border-flood-200 ring-2 ring-flood-500/20'
                : 'bg-white border-gray-100 hover:bg-gray-50 hover:border-gray-200'
            )}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-gray-900">{label}</p>
                <p className="text-xs text-gray-500">{desc}</p>
              </div>
              {scenario.builtup_increase_pct === value && (
                <svg className="w-5 h-5 text-flood-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}