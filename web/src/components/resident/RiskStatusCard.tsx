import { useT, type MessageKey } from '../../lib/i18n';
import { getRiskColor } from '../../lib/utils';
import type { RiskLevel } from '../../types';
import { useWardForecast } from './hooks';

const ADVICE: Record<RiskLevel, MessageKey> = {
  very_low: 'advice.calm',
  low: 'advice.calm',
  moderate: 'advice.prepare',
  high: 'advice.act',
  very_high: 'advice.act',
};

/** The model's estimate for my ward from the live rain forecast. Never presented as an official warning. */
export function RiskStatusCard({ wardId }: { wardId: number }) {
  const t = useT();
  const { state: forecast, retry } = useWardForecast(wardId);

  if (forecast.status === 'loading' || forecast.status === 'idle') {
    return <div className="card p-4 text-gray-700" role="status">{t('status.loading')}</div>;
  }
  if (forecast.status === 'error' || !forecast.ward) {
    return (
      <div className="card p-4 space-y-2">
        <p className="text-gray-800">{t('status.error')}</p>
        <button onClick={retry} className="btn-secondary min-h-11">{t('status.retry')}</button>
      </div>
    );
  }

  const { ward } = forecast;
  const color = getRiskColor(ward.risk_level);
  return (
    <section className="card p-4 border-l-8" style={{ borderLeftColor: color }} aria-labelledby="risk-status-title">
      <h2 id="risk-status-title" className="text-sm font-medium text-gray-700">{t('status.title')}</h2>
      <p className="text-3xl font-bold text-gray-900 mt-1 flex items-center gap-2">
        <span className="w-4 h-4 rounded-full flex-shrink-0" style={{ backgroundColor: color }} aria-hidden="true" />
        {t(`level.${ward.risk_level}` as MessageKey)}
      </p>
      <p className="text-base text-gray-900 mt-3">{t(ADVICE[ward.risk_level])}</p>
      <p className="text-sm text-gray-700 mt-3">
        {t('status.basis', { mm: Math.round(forecast.rainfall_mm * 10) / 10, h: forecast.duration_hours })}
      </p>
      <p className="text-xs text-gray-600 mt-1">{t('status.disclaimer')}</p>
    </section>
  );
}
