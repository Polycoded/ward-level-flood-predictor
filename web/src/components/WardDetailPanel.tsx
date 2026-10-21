import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useFloodStore } from '../lib/store';
import { api } from '../api/client';
import { cn, getRiskColor, getRiskLabel, getDepthLabel, getDepthColor, formatPercent, formatDistance } from '../lib/utils';
import { RiskBadge } from './RiskBadge';
import type { WardFeature, WardRisk } from '../types';

interface WardDetailPanelProps {
  wardId: number;
}

export function WardDetailPanel({ wardId }: WardDetailPanelProps) {
  const { riskData, setSelectedWard, setDetailWard, ui } = useFloodStore();
  const [wardDetail, setWardDetail] = useState<WardFeature | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadWardDetail();
  }, [wardId]);

  const loadWardDetail = async () => {
    try {
      const detail = await api.getWard(wardId);
      setWardDetail(detail);
      setSelectedWard(detail);
    } catch (error) {
      console.error('Failed to load ward detail:', error);
    } finally {
      setLoading(false);
    }
  };

  const riskWard = riskData?.wards.find((w) => w.ward_id === wardId);
  const isOpen = ui.detailWardId === wardId;

  if (!isOpen || loading) {
    return null;
  }

  const content = (
    <div className="fixed inset-0 z-40 flex lg:hidden">
      <div className="absolute inset-0 bg-black/50" onClick={() => setDetailWard(null)} />
      <div className="relative w-full max-w-md ml-auto bg-white shadow-xl flex flex-col h-full animate-in">
        <DetailContent wardDetail={wardDetail} riskWard={riskWard} onClose={() => setDetailWard(null)} />
      </div>
    </div>
  );

  return createPortal(content, document.body);
}

function DetailContent({
  wardDetail,
  riskWard,
  onClose,
}: {
  wardDetail: WardFeature | null;
  riskWard: WardRisk | null;
  onClose: () => void;
}) {
  if (!wardDetail) return null;

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">{wardDetail.ward_name}</h2>
          <p className="text-sm text-gray-500">Ward {wardDetail.ward_number} • {wardDetail.area_sqkm.toFixed(2)} km²</p>
        </div>
        <button onClick={onClose} className="p-2 rounded-lg hover:bg-gray-100 text-gray-500">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {riskWard && (
          <RiskSummaryCard ward={riskWard} />
        )}

        <ReasonsPanel reasons={riskWard?.reasons || []} />

        <FeatureMetricsPanel ward={wardDetail} />

        <AlertActionsPanel wardId={wardDetail.ward_id} wardName={wardDetail.ward_name} riskWard={riskWard} />
      </div>
    </div>
  );
}

function RiskSummaryCard({ ward }: { ward: WardRisk }) {
  const color = getRiskColor(ward.risk_level);
  const depthColor = getDepthColor(ward.depth_band);

  return (
    <div className="card p-4 border-l-4" style={{ borderLeftColor: color }}>
      <div className="flex items-center justify-between mb-3">
        <RiskBadge level={ward.risk_level} size="lg" showIcon />
        <div className="text-right">
          <p className="text-3xl font-bold text-gray-900">{(ward.risk_score * 100).toFixed(0)}%</p>
          <p className="text-xs text-gray-500">Risk Score</p>
        </div>
      </div>
      
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-gray-500">Flood Depth</p>
          <p className="font-medium text-gray-900 flex items-center gap-1">
            <span className="w-2 h-2 rounded" style={{ backgroundColor: depthColor }}></span>
            {getDepthLabel(ward.depth_band)}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Peak Window</p>
          <p className="font-medium text-gray-900">{ward.peak_window_hours} hours</p>
        </div>
      </div>
    </div>
  );
}

function ReasonsPanel({ reasons }: { reasons: string[] }) {
  if (reasons.length === 0) return null;

  return (
    <div className="card p-4">
      <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
        <svg className="w-5 h-5 text-flood-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        Key Risk Factors
      </h3>
      <ul className="space-y-2">
        {reasons.map((reason, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
            <span className="w-1.5 h-1.5 rounded-full bg-flood-500 mt-1.5 flex-shrink-0" />
            {reason}
          </li>
        ))}
      </ul>
    </div>
  );
}

function FeatureMetricsPanel({ ward }: { ward: WardFeature }) {
  const metrics = [
    { label: 'Elevation', value: `${ward.elevation_mean.toFixed(1)} m`, icon: '⛰️' },
    { label: 'Slope', value: `${ward.slope_mean.toFixed(1)}°`, icon: '📐' },
    { label: 'Impervious', value: formatPercent(ward.impervious_frac), icon: '🏢' },
    { label: 'Water Bodies', value: formatPercent(ward.water_frac), icon: '💧' },
    { label: 'Vegetation', value: formatPercent(ward.vegetation_frac), icon: '🌳' },
    { label: 'Dist. to Water', value: formatDistance(ward.dist_to_water_m), icon: '📏' },
    { label: 'Road Density', value: `${ward.road_density_km_per_sqkm.toFixed(1)} km/km²`, icon: '🛣️' },
    { label: 'Underpasses', value: ward.underpass_count.toString(), icon: '🚇' },
  ];

  return (
    <div className="card p-4">
      <h3 className="font-semibold text-gray-900 mb-3">Ward Characteristics</h3>
      <div className="grid grid-cols-2 gap-3">
        {metrics.map((m, i) => (
          <div key={i} className="p-3 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-500 flex items-center gap-1">{m.icon} {m.label}</p>
            <p className="font-mono text-lg font-semibold text-gray-900">{m.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function AlertActionsPanel({ wardId, wardName, riskWard }: { wardId: number; wardName: string; riskWard: WardRisk | null }) {
  const { ui, setAlertsOpen } = useFloodStore();

  return (
    <div className="card p-4 border-t border-gray-100">
      <h3 className="font-semibold text-gray-900 mb-3">Actions</h3>
      <div className="space-y-2">
        <button
          onClick={() => setAlertsOpen(true)}
          className="w-full btn-primary justify-center"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          Send Alerts
        </button>
        <button className="w-full btn-secondary justify-center">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.761 19.239a2 2 0 002.476 0l6-6a2 2 0 00-2.476-2.476L8 15.527V5a2 2 0 00-2-2H6a2 2 0 00-2 2v10.527L2.476 10.761A2 2 0 000 13.243l6 6a2 2 0 002.476 0z" />
          </svg>
          Navigate to Shelter
        </button>
        <button className="w-full btn-ghost justify-center text-flood-600">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          View Road Risk
        </button>
      </div>
    </div>
  );
}