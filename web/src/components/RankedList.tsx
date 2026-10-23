import { useMemo, useState } from 'react';
import { useFloodStore } from '../lib/store';
import { cn, getRiskColor, getDepthColor, getDepthLabel } from '../lib/utils';
import type { RiskLevel, WardRisk } from '../types';
import { RiskBadge } from './RiskBadge';

const LEVEL_FILTERS: { value: 'all' | 'high_plus' | RiskLevel; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'high_plus', label: 'High+' },
  { value: 'moderate', label: 'Moderate' },
];

const MAX_QUERY = 60;

export function RankedList() {
  const { wards, riskData, ui, setDetailWard, setMapView, setSidebarOpen } = useFloodStore();
  const [query, setQuery] = useState('');
  const [level, setLevel] = useState<(typeof LEVEL_FILTERS)[number]['value']>('all');

  const ranked = useMemo(
    () => (riskData ? [...riskData.wards].sort((a, b) => b.risk_score - a.risk_score) : []),
    [riskData]
  );

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return ranked
      .map((ward, i) => ({ ward, rank: i + 1 }))
      .filter(({ ward }) => {
        if (level === 'high_plus' && ward.risk_level !== 'high' && ward.risk_level !== 'very_high') return false;
        if (level !== 'all' && level !== 'high_plus' && ward.risk_level !== level) return false;
        return !q || ward.ward_name.toLowerCase().includes(q) || ward.ward_number.toLowerCase() === q;
      });
  }, [ranked, query, level]);

  const open = (wardId: number) => {
    setDetailWard(wardId);
    setMapView('risk');
    if (window.innerWidth < 1024) setSidebarOpen(false);
  };

  return (
    <div className="flex flex-col min-h-0 flex-1">
      <div className="px-4 pt-4 pb-3 border-b border-gray-200 space-y-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Ward Risk Ranking</h2>
          <p className="text-xs text-gray-600 mt-0.5">
            {riskData
              ? `${ranked.length} wards, highest risk first`
              : `${wards.length} wards loaded. Set rainfall and press Analyze.`}
          </p>
        </div>

        {riskData && (
          <>
            <label className="sr-only" htmlFor="ward-search">Search wards</label>
            <input
              id="ward-search"
              type="search"
              className="input"
              placeholder="Search ward name or number"
              value={query}
              maxLength={MAX_QUERY}
              onChange={(e) => setQuery(e.target.value.slice(0, MAX_QUERY))}
            />
            <div className="flex gap-1.5" role="group" aria-label="Filter by risk level">
              {LEVEL_FILTERS.map((f) => (
                <button
                  key={f.value}
                  onClick={() => setLevel(f.value)}
                  aria-pressed={level === f.value}
                  className={cn(
                    'px-2.5 py-1 rounded-full text-xs font-medium border transition-colors',
                    level === f.value
                      ? 'bg-flood-700 text-white border-flood-700'
                      : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                  )}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      <ol className="flex-1 overflow-y-auto p-3 space-y-2" aria-label="Wards ranked by flood risk">
        {!riskData && <EmptyState />}
        {riskData && visible.length === 0 && (
          <li className="text-sm text-gray-600 text-center py-8">No wards match this filter.</li>
        )}
        {visible.map(({ ward, rank }) => (
          <li key={ward.ward_id}>
            <WardRow ward={ward} rank={rank} selected={ui.detailWardId === ward.ward_id} onClick={() => open(ward.ward_id)} />
          </li>
        ))}
      </ol>
    </div>
  );
}

function EmptyState() {
  return (
    <li className="text-sm text-gray-600 p-4 rounded-lg border border-dashed border-gray-300 bg-gray-50">
      <p className="font-medium text-gray-800 mb-1">No analysis yet</p>
      Pick a rainfall amount (try 100 mm in 3 h, or 300 mm for the Dec 2023 event) and press <strong>Analyze</strong> to
      rank every ward.
    </li>
  );
}

function WardRow({ ward, rank, selected, onClick }: { ward: WardRisk; rank: number; selected: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-current={selected ? 'true' : undefined}
      className={cn(
        'w-full text-left p-3 rounded-lg border transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-flood-500',
        selected ? 'bg-flood-50 border-flood-300' : 'bg-white border-gray-200 hover:bg-gray-50'
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white flex-shrink-0"
          style={{ backgroundColor: getRiskColor(ward.risk_level) }}
          aria-label={`Rank ${rank}`}
        >
          {rank}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-gray-900 truncate">{ward.ward_name}</span>
            <RiskBadge level={ward.risk_level} size="sm" />
          </div>
          <p className="text-xs text-gray-600">Ward {ward.ward_number}</p>
          <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-700">
            <span className="flex items-center gap-1" title="Indicative depth band (proxy from the risk index, not a hydraulic prediction)">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: getDepthColor(ward.depth_band) }} />
              ≈ {getDepthLabel(ward.depth_band)}
            </span>
            <span title="Indicative peak window (proxy from the risk index)">peak ≈ {ward.peak_window_hours}h</span>
            <span className="font-mono ml-auto">{Math.round(ward.risk_score * 100)}</span>
          </div>
        </div>
      </div>
    </button>
  );
}
