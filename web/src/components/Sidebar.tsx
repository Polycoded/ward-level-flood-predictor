import { useFloodStore } from '../lib/store';
import { cn } from '../lib/utils';
import type { RainfallReading } from '../lib/rainfall';
import { RainfallControl } from './RainfallControl';
import { RankedList } from './RankedList';

interface SidebarProps {
  onAnalyze: (reading: RainfallReading) => void;
  busy: boolean;
}

export function Sidebar({ onAnalyze, busy }: SidebarProps) {
  const { riskData, ui, setMapView } = useFloodStore();

  const toggle = (view: 'roads' | 'shelters') => setMapView(ui.mapView === view ? 'risk' : view);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <RainfallControl onAnalyze={onAnalyze} busy={busy} />
      <RankedList />

      <div className="p-3 border-t border-gray-200 grid grid-cols-2 gap-2">
        <button
          onClick={() => toggle('roads')}
          disabled={!riskData}
          aria-pressed={ui.mapView === 'roads'}
          title={riskData ? 'Show roads and underpasses likely to waterlog' : 'Run an analysis first'}
          className={cn('btn text-sm', ui.mapView === 'roads' ? 'btn-primary' : 'btn-secondary')}
        >
          Roads &amp; underpasses
        </button>
        <button
          onClick={() => toggle('shelters')}
          aria-pressed={ui.mapView === 'shelters'}
          className={cn('btn text-sm', ui.mapView === 'shelters' ? 'btn-primary' : 'btn-secondary')}
        >
          Shelters
        </button>
      </div>
    </div>
  );
}
