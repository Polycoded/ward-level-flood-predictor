import { useFloodStore } from '../lib/store';
import { cn, getRiskColor, getDepthColor } from '../lib/utils';
import type { WardRisk } from '../types';
import { RiskBadge } from './RiskBadge';

export function Sidebar() {
  const { wards, riskData, ui, setDetailWard, setMapView, setSidebarOpen } = useFloodStore();

  const sortedWards = riskData
    ? [...riskData.wards].sort((a, b) => b.risk_score - a.risk_score)
    : wards.map((w) => ({
        ward_id: w.ward_id,
        ward_number: w.ward_number,
        ward_name: w.ward_name,
        risk_score: 0,
        risk_level: 'very_low' as const,
        depth_band: 'none' as const,
        peak_window_hours: 0,
        reasons: [],
        features: {},
      }));

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="p-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-flood-500"></span>
          Ward Risk Ranking
        </h2>
        <p className="text-xs text-gray-500 mt-1">
          {riskData ? 'Sorted by risk score (highest first)' : 'No analysis run yet'}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {sortedWards.map((ward, index) => (
          <WardListItem
            key={ward.ward_id}
            ward={ward}
            rank={index + 1}
            isSelected={ui.detailWardId === ward.ward_id}
            onClick={() => {
              setDetailWard(ward.ward_id);
              setMapView('risk');
              if (window.innerWidth < 1024) setSidebarOpen(false);
            }}
          />
        ))}
      </div>

      <div className="p-4 border-t border-gray-200">
        <div className="flex gap-2">
          <button
            onClick={() => setMapView('roads')}
            className={cn(
              'flex-1 btn text-sm',
              ui.mapView === 'roads' ? 'btn-primary' : 'btn-secondary'
            )}
          >
            Road Risk
          </button>
          <button
            onClick={() => setMapView(ui.mapView === 'shelters' ? 'risk' : 'shelters')}
            className={cn(
              'flex-1 btn text-sm',
              ui.mapView === 'shelters' ? 'btn-primary' : 'btn-secondary'
            )}
          >
            Shelters
          </button>
        </div>
      </div>
    </div>
  );
}

function WardListItem({
  ward,
  rank,
  isSelected,
  onClick,
}: {
  ward: WardRisk;
  rank: number;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full text-left p-3 rounded-lg transition-all',
        isSelected
          ? 'bg-flood-50 border border-flood-200 ring-2 ring-flood-500/20'
          : 'bg-white border border-gray-100 hover:bg-gray-50 hover:border-gray-200'
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white flex-shrink-0"
          style={{ backgroundColor: getRiskColor(ward.risk_level) }}
        >
          {rank}
        </span>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-medium text-gray-900 truncate">{ward.ward_name}</h3>
            <RiskBadge level={ward.risk_level} size="sm" />
          </div>
          <p className="text-xs text-gray-500">Ward {ward.ward_number}</p>
          
          <div className="flex items-center gap-3 mt-2 text-xs text-gray-600">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: getDepthColor(ward.depth_band) }}></span>
              {ward.depth_band}
            </span>
            <span className="flex items-center gap-1">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {ward.peak_window_hours}h
            </span>
            <span className="font-mono text-flood-600">
              {(ward.risk_score * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      </div>
    </button>
  );
}