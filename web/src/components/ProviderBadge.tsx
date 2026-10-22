import { useFloodStore } from '../lib/store';
import { cn } from '../lib/utils';

const RAINFALL_LABELS = {
  manual: 'Manual rainfall',
  csv: 'CSV rainfall',
  'open-meteo': 'Open-Meteo forecast',
} as const;

/** Where the numbers on screen come from: backend vs offline mock, and the rainfall provider. */
export function ProviderBadge({ className }: { className?: string }) {
  const { dataSource, rainfall } = useFloodStore();
  if (dataSource === 'unknown') return null;

  const live = dataSource === 'live';
  return (
    <div className={cn('flex flex-wrap items-center gap-1.5', className)}>
      <span
        className={cn(
          'px-2 py-0.5 rounded-full text-xs font-medium border',
          live ? 'bg-green-50 text-green-800 border-green-200' : 'bg-amber-50 text-amber-800 border-amber-200'
        )}
        title={live ? 'Connected to the FastAPI backend' : 'Backend unavailable: synthetic demo data, not real wards'}
      >
        {live ? 'Live API' : 'Mock data'}
      </span>
      <span
        className="px-2 py-0.5 rounded-full text-xs font-medium border bg-sky-50 text-sky-800 border-sky-200"
        title={rainfall.label}
      >
        {RAINFALL_LABELS[rainfall.source]}
      </span>
    </div>
  );
}
