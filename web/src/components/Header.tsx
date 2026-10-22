import { useState } from 'react';
import { useFloodStore } from '../lib/store';
import { getRiskLabel, getRiskColor } from '../lib/utils';
import type { RiskResponse } from '../types';

interface HeaderProps {
  onAnalyze: (rainfall: number, builtupIncrease?: number) => void;
  onClear: () => void;
  hasRiskData: boolean;
  scenario: { rainfall_mm: number; duration_hours: number; builtup_increase_pct: number };
}

export function Header({ onAnalyze, onClear, hasRiskData, scenario }: HeaderProps) {
  const { ui, riskData, validationData, dataSource, setLanguage, setAlertsOpen, setValidationOpen } = useFloodStore();
  const [rainfall, setRainfall] = useState(scenario.rainfall_mm);
  const { builtup_increase_pct } = scenario;

  return (
    <header className="bg-white border-b border-gray-200 z-20">
      <div className="max-w-full mx-auto px-4">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 py-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-flood-600 flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3.5c-3 4-6 7.2-6 10.5a6 6 0 0012 0c0-3.3-3-6.5-6-10.5z" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                Chennai Flood Predictor
                <DataSourceBadge source={dataSource} />
              </h1>
              <p className="text-xs text-gray-500">Ward-level risk assessment • 200 wards</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 rounded-lg border border-gray-200">
              <label htmlFor="rainfall" className="text-sm font-medium text-gray-700">Rainfall:</label>
              <select
                id="rainfall"
                className="bg-transparent border-none outline-none text-sm font-medium text-gray-900 cursor-pointer"
                value={rainfall}
                onChange={(e) => {
                  const mm = Number(e.target.value);
                  setRainfall(mm);
                  onAnalyze(mm, builtup_increase_pct);
                }}
              >
                <option value={25}>25 mm (Light)</option>
                <option value={50}>50 mm</option>
                <option value={75}>75 mm (Moderate)</option>
                <option value={100}>100 mm</option>
                <option value={150}>150 mm (Heavy)</option>
                <option value={200}>200 mm</option>
                <option value={250}>250 mm (Extreme)</option>
                <option value={300}>300 mm (Dec 2023)</option>
              </select>
              <span className="text-sm text-gray-500">/ 3hr</span>
            </div>

            <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 rounded-lg border border-gray-200">
              <label htmlFor="scenario" className="text-sm font-medium text-gray-700">Scenario:</label>
              <select
                id="scenario"
                className="bg-transparent border-none outline-none text-sm font-medium text-gray-900 cursor-pointer"
                value={builtup_increase_pct}
                onChange={(e) => onAnalyze(rainfall, Number(e.target.value))}
              >
                <option value={0}>Current</option>
                <option value={15}>+15% Built-up</option>
                <option value={30}>+30% Built-up</option>
              </select>
            </div>

            <button onClick={() => onAnalyze(rainfall, builtup_increase_pct)} className="btn-primary">
              {hasRiskData ? 'Re-run' : 'Analyze'}
            </button>

            {hasRiskData && (
              <button onClick={() => setAlertsOpen(true)} className="btn-secondary">
                Alerts
              </button>
            )}

            {validationData && (
              <button onClick={() => setValidationOpen(!ui.validationOpen)} className="btn-secondary">
                Validation
              </button>
            )}

            <button
              onClick={() => setLanguage(ui.language === 'en' ? 'ta' : 'en')}
              className="btn-secondary hidden sm:flex"
              aria-label="Toggle language"
            >
              {ui.language === 'en' ? 'தமிழ்' : 'English'}
            </button>

            {hasRiskData && (
              <button onClick={onClear} className="btn-ghost text-red-600 hover:text-red-700">
                Clear
              </button>
            )}

            <button
              onClick={() => useFloodStore.getState().toggleSidebar()}
              className="lg:hidden btn-ghost"
              aria-label="Toggle sidebar"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>
        </div>

        {riskData && (
          <div className="pb-3">
            <RiskSummaryBar riskData={riskData} />
          </div>
        )}
      </div>
    </header>
  );
}

function DataSourceBadge({ source }: { source: 'unknown' | 'live' | 'mock' }) {
  if (source === 'unknown') return null;
  const live = source === 'live';
  return (
    <span
      className={live
        ? 'px-2 py-0.5 rounded-full text-xs font-medium bg-green-50 text-green-700 border border-green-200'
        : 'px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200'}
      title={live ? 'Connected to the FastAPI backend' : 'Backend unavailable: showing synthetic mock data'}
    >
      {live ? 'Live API' : 'Mock data'}
    </span>
  );
}

function RiskSummaryBar({ riskData }: { riskData: RiskResponse }) {
  const { wards } = riskData;
  const total = wards.length;
  const highRisk = wards.filter((w) => w.risk_level === 'high' || w.risk_level === 'very_high').length;
  const moderateRisk = wards.filter((w) => w.risk_level === 'moderate').length;
  const topWard = wards[0];
  const topColor = getRiskColor(topWard?.risk_level || 'moderate');

  return (
    <div className="flex flex-wrap items-center gap-4 text-sm">
      <div className="flex items-center gap-2">
        <span className="font-medium text-gray-700">Top Risk:</span>
        <span className="font-semibold text-gray-900">{topWard?.ward_name}</span>
        <span
          className="px-2 py-0.5 rounded-full text-xs font-medium"
          style={{ backgroundColor: `${topColor}1a`, color: topColor }}
        >
          {getRiskLabel(topWard?.risk_level || 'moderate')}
        </span>
      </div>
      <div className="flex items-center gap-4 text-gray-600">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: '#ef4444' }}></span>
          {highRisk} High+
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: '#f59e0b' }}></span>
          {moderateRisk} Moderate
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: '#10b981' }}></span>
          {total - highRisk - moderateRisk} Low
        </span>
      </div>
      <div className="text-gray-500">
        {wards.length} wards analyzed • {new Date(riskData.generated_at).toLocaleTimeString()}
      </div>
    </div>
  );
}
