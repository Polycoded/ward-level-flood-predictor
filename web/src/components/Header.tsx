import { useFloodStore } from '../lib/store';
import { getRiskLabel, getRiskColor } from '../lib/utils';
import type { RiskResponse } from '../types';
import { ProviderBadge } from './ProviderBadge';
import { CROWD_REPORTS_ENABLED } from '../lib/features';
import { parseValidation } from '../lib/validation';

interface HeaderProps {
  onClear: () => void;
  onOpenReports: () => void;
}

export function Header({ onClear, onOpenReports }: HeaderProps) {
  const { ui, riskData, validationData, setAlertsOpen, setValidationOpen, toggleSidebar } = useFloodStore();
  const validationUnavailable = validationData ? parseValidation(validationData).status === 'unavailable' : false;

  return (
    <header className="bg-white border-b border-gray-200 z-20">
      <div className="px-4 py-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="flex items-center gap-3 min-w-0">
          <button onClick={toggleSidebar} className="lg:hidden btn-ghost px-2" aria-label="Toggle ward list" aria-expanded={ui.sidebarOpen}>
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <div className="w-9 h-9 rounded-lg bg-flood-700 flex items-center justify-center flex-shrink-0" aria-hidden="true">
            <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3.5c-3 4-6 7.2-6 10.5a6 6 0 0012 0c0-3.3-3-6.5-6-10.5z" />
            </svg>
          </div>
          <div className="min-w-0">
            <h1 className="text-lg font-bold text-gray-900 leading-tight">Chennai Ward Flood Predictor</h1>
            <ProviderBadge className="mt-0.5" />
          </div>
        </div>

        <nav className="flex flex-wrap items-center gap-2 ml-auto" aria-label="Dashboard actions">
          {riskData && (
            <button onClick={() => setAlertsOpen(true)} className="btn-primary">Alerts</button>
          )}
          {validationData && (
            <button onClick={() => setValidationOpen(!ui.validationOpen)} aria-pressed={ui.validationOpen} className="btn-secondary">
              {validationUnavailable ? 'Validation (unavailable)' : 'Validation'}
            </button>
          )}
          {CROWD_REPORTS_ENABLED && (
            <button onClick={onOpenReports} className="btn-secondary">Report flooding</button>
          )}
          {riskData && (
            <button onClick={onClear} className="btn-ghost text-red-700 hover:text-red-800">Clear</button>
          )}
        </nav>
      </div>

      {riskData && (
        <div className="px-4 pb-2.5">
          <RiskSummaryBar riskData={riskData} />
        </div>
      )}
    </header>
  );
}

function RiskSummaryBar({ riskData }: { riskData: RiskResponse }) {
  const { wards } = riskData;
  const highRisk = wards.filter((w) => w.risk_level === 'high' || w.risk_level === 'very_high').length;
  const moderateRisk = wards.filter((w) => w.risk_level === 'moderate').length;
  const topWard = wards[0];
  const topColor = getRiskColor(topWard?.risk_level || 'moderate');

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm" aria-live="polite">
      {topWard && (
        <div className="flex items-center gap-2">
          <span className="text-gray-700">Top risk:</span>
          <span className="font-semibold text-gray-900">{topWard.ward_name}</span>
          <span className="px-2 py-0.5 rounded-full text-xs font-medium border" style={{ color: '#111827', borderColor: topColor, backgroundColor: `${topColor}22` }}>
            {getRiskLabel(topWard.risk_level)}
          </span>
        </div>
      )}
      <span className="text-gray-800"><strong>{highRisk}</strong> high+</span>
      <span className="text-gray-800"><strong>{moderateRisk}</strong> moderate</span>
      <span className="text-gray-800"><strong>{wards.length - highRisk - moderateRisk}</strong> low</span>
      <span className="text-gray-600">
        {riskData.scenario.rainfall_mm} mm / {riskData.scenario.duration_hours} h • {new Date(riskData.generated_at).toLocaleTimeString()}
      </span>
    </div>
  );
}
