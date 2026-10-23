import { useEffect, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useFloodStore } from '../lib/store';
import { api } from '../api/client';
import { getRiskColor, getDepthLabel, getDepthColor, formatPercent, formatDistance } from '../lib/utils';
import { geometryCenter } from '../lib/geo';
import { RiskBadge } from './RiskBadge';
import { ExplainabilityPanel } from './ExplainabilityPanel';
import type { WardFeature, WardRisk } from '../types';

interface WardDetailPanelProps {
  wardId: number;
}

export function WardDetailPanel({ wardId }: WardDetailPanelProps) {
  const { riskData, scenario, setSelectedWard, setDetailWard } = useFloodStore();
  const [wardDetail, setWardDetail] = useState<WardFeature | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');

  useEffect(() => {
    let cancelled = false;
    setStatus('loading');
    api
      .getWard(wardId)
      .then((detail) => {
        if (cancelled) return;
        setWardDetail(detail);
        setSelectedWard(detail);
        setStatus('ready');
      })
      .catch(() => !cancelled && setStatus('error'));
    return () => {
      cancelled = true;
    };
  }, [wardId, setSelectedWard]);

  useEffect(() => {
    // an open dialog on top owns Escape; only close the drawer when it is the top layer
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !document.querySelector('[aria-modal="true"]')) setDetailWard(null);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [setDetailWard]);

  const riskWard = riskData?.wards.find((w) => w.ward_id === wardId) ?? null;
  const close = () => setDetailWard(null);

  // Mobile: modal drawer with backdrop. Desktop: side drawer that leaves the map
  // clickable so you can hop between wards.
  return createPortal(
    <>
      <div className="fixed inset-0 z-40 bg-black/50 lg:hidden" onClick={close} aria-hidden="true" />
      <aside
        aria-label="Ward details"
        className="fixed inset-y-0 right-0 z-40 w-full max-w-md bg-white shadow-xl flex flex-col animate-in"
      >
        {status === 'loading' && <PanelMessage onClose={close}>Loading ward…</PanelMessage>}
        {status === 'error' && <PanelMessage onClose={close}>Could not load this ward. Try again in a moment.</PanelMessage>}
        {status === 'ready' && wardDetail && (
          <DetailContent
            wardDetail={wardDetail}
            riskWard={riskWard}
            rainfallMm={riskData?.scenario.rainfall_mm ?? null}
            durationHours={riskData?.scenario.duration_hours ?? 3}
            builtupIncreasePct={scenario.builtup_increase_pct}
            onClose={close}
          />
        )}
      </aside>
    </>,
    document.body
  );
}

function CloseButton({ onClose }: { onClose: () => void }) {
  return (
    <button onClick={onClose} className="p-2 rounded-lg hover:bg-gray-100 text-gray-600" aria-label="Close ward details">
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      </svg>
    </button>
  );
}

function PanelMessage({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  return (
    <div className="p-4 flex items-start justify-between gap-2">
      <p className="text-gray-700" role="status">{children}</p>
      <CloseButton onClose={onClose} />
    </div>
  );
}

function DetailContent({
  wardDetail,
  riskWard,
  rainfallMm,
  durationHours,
  builtupIncreasePct,
  onClose,
}: {
  wardDetail: WardFeature;
  riskWard: WardRisk | null;
  rainfallMm: number | null;
  durationHours: number;
  builtupIncreasePct: number;
  onClose: () => void;
}) {
  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">{wardDetail.ward_name}</h2>
          <p className="text-sm text-gray-600">Ward {wardDetail.ward_number} • {wardDetail.area_sqkm.toFixed(2)} km²</p>
        </div>
        <CloseButton onClose={onClose} />
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {riskWard ? (
          <RiskSummaryCard ward={riskWard} rainfallMm={rainfallMm} durationHours={durationHours} />
        ) : (
          <p className="text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded-lg p-3">
            Run a rainfall analysis to see this ward's flood risk. Its terrain profile is below.
          </p>
        )}

        <ExplainabilityPanel
          ward={wardDetail}
          riskWard={riskWard}
          rainfallMm={rainfallMm}
          durationHours={durationHours}
          builtupIncreasePct={builtupIncreasePct}
        />

        <OtherFeatures ward={wardDetail} />

        <ActionsPanel ward={wardDetail} hasRisk={riskWard !== null} />
      </div>
    </div>
  );
}

function RiskSummaryCard({ ward, rainfallMm, durationHours }: { ward: WardRisk; rainfallMm: number | null; durationHours: number }) {
  return (
    <div className="card p-4 border-l-4" style={{ borderLeftColor: getRiskColor(ward.risk_level) }}>
      <div className="flex items-center justify-between mb-3">
        <RiskBadge level={ward.risk_level} size="lg" showIcon />
        <div className="text-right">
          <p className="text-3xl font-bold text-gray-900">{Math.round(ward.risk_score * 100)}</p>
          <p className="text-xs text-gray-600">risk score / 100</p>
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-xs text-gray-600">Indicative depth band</dt>
          <dd className="font-medium text-gray-900 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded" style={{ backgroundColor: getDepthColor(ward.depth_band) }} aria-hidden="true" />
            ≈ {getDepthLabel(ward.depth_band)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-gray-600">Indicative peak window</dt>
          <dd className="font-medium text-gray-900">≈ {ward.peak_window_hours} h</dd>
        </div>
        {rainfallMm !== null && (
          <div className="col-span-2">
            <dt className="text-xs text-gray-600">Scenario</dt>
            <dd className="font-medium text-gray-900">{rainfallMm} mm in {durationHours} h</dd>
          </div>
        )}
      </dl>
      <p className="text-xs text-gray-600 mt-3 border-t border-gray-100 pt-2">
        Depth and peak are display proxies derived from the risk index, not hydraulic predictions
        (see docs/model_logic.md). Use the risk level for decisions.
      </p>
    </div>
  );
}

function OtherFeatures({ ward }: { ward: WardFeature }) {
  const rows = [
    { label: 'Water bodies', value: formatPercent(ward.water_frac) },
    { label: 'Vegetation', value: formatPercent(ward.vegetation_frac) },
    { label: 'Nearest water', value: formatDistance(ward.dist_to_water_m) },
    { label: 'Static flood-prone index', value: `${Math.round(ward.flood_prone_index * 100)} / 100` },
  ];
  return (
    <details className="card p-4">
      <summary className="font-semibold text-gray-900 cursor-pointer">More ward data</summary>
      <dl className="grid grid-cols-2 gap-3 mt-3">
        {rows.map((r) => (
          <div key={r.label} className="p-2.5 bg-gray-50 rounded-lg">
            <dt className="text-xs text-gray-600">{r.label}</dt>
            <dd className="font-mono font-semibold text-gray-900">{r.value}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

function ActionsPanel({ ward, hasRisk }: { ward: WardFeature; hasRisk: boolean }) {
  const { setAlertsOpen, setMapView, setShelterOrigin, setDetailWard } = useFloodStore();

  const showShelters = () => {
    const centre = geometryCenter(ward.geometry);
    if (centre) setShelterOrigin({ ...centre, label: `Centre of ${ward.ward_name}` });
    setMapView('shelters');
    setDetailWard(null);
  };

  return (
    <div className="card p-4">
      <h3 className="font-semibold text-gray-900 mb-3">Actions</h3>
      <div className="space-y-2">
        <button
          onClick={() => setAlertsOpen(true)}
          disabled={!hasRisk}
          title={hasRisk ? undefined : 'Run a rainfall analysis first'}
          className="w-full btn-primary"
        >
          Draft alerts for this ward
        </button>
        <button onClick={showShelters} className="w-full btn-secondary">Nearest shelters</button>
        <button
          onClick={() => {
            setMapView('roads');
            setDetailWard(null);
          }}
          disabled={!hasRisk}
          className="w-full btn-ghost text-flood-700"
        >
          Roads &amp; underpasses
        </button>
      </div>
    </div>
  );
}
