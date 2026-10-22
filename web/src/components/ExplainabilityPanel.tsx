import { factorContributions, rainfallFactor, toFactorInputs } from '../lib/explain';
import type { WardFeature, WardRisk } from '../types';

interface ExplainabilityPanelProps {
  ward: WardFeature;
  riskWard: WardRisk | null;
  rainfallMm: number | null;
  builtupIncreasePct: number;
}

/**
 * Feature values and the model's reasons side by side (blueprint T2.5).
 * Bars show how many points each factor adds to the static susceptibility score;
 * rainfall then scales that score into the final risk.
 */
export function ExplainabilityPanel({ ward, riskWard, rainfallMm, builtupIncreasePct }: ExplainabilityPanelProps) {
  const inputs = toFactorInputs({ ...(ward as unknown as Record<string, number>), ...(riskWard?.features ?? {}) });
  const factors = factorContributions(inputs, builtupIncreasePct).sort((a, b) => b.contribution - a.contribution);
  const base = factors.reduce((s, f) => s + f.contribution, 0);
  const rf = rainfallMm !== null ? rainfallFactor(rainfallMm) : null;

  return (
    <section className="card p-4" aria-labelledby="why-heading">
      <h3 id="why-heading" className="font-semibold text-gray-900">Why this ward?</h3>
      <p className="text-xs text-gray-600 mt-0.5 mb-3">
        Terrain and land-use factors, weighted as in the risk model. Longer bar = bigger push towards flooding.
      </p>

      <div className="grid gap-4 md:grid-cols-1">
        <table className="w-full text-sm">
          <caption className="sr-only">Contribution of each factor to flood susceptibility</caption>
          <thead>
            <tr className="text-xs text-gray-600 text-left">
              <th scope="col" className="font-medium pb-1">Factor</th>
              <th scope="col" className="font-medium pb-1">Value</th>
              <th scope="col" className="font-medium pb-1 w-2/5">Contribution</th>
            </tr>
          </thead>
          <tbody>
            {factors.map((f) => (
              <tr key={f.key} className="border-t border-gray-100 align-top">
                <th scope="row" className="py-1.5 pr-2 font-normal text-gray-800">
                  {f.label}
                  <span className="block text-xs text-gray-500">{f.direction}</span>
                </th>
                <td className="py-1.5 pr-2 font-mono text-xs text-gray-800 whitespace-nowrap">{f.rawValue}</td>
                <td className="py-1.5">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 rounded bg-gray-100 overflow-hidden" aria-hidden="true">
                      <div className="h-full bg-flood-600" style={{ width: `${(f.contribution / 0.25) * 100}%` }} />
                    </div>
                    <span className="font-mono text-xs text-gray-700 w-9 text-right">
                      +{(f.contribution * 100).toFixed(0)}
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-gray-200 text-xs text-gray-700">
              <th scope="row" colSpan={2} className="pt-2 text-left font-medium">Susceptibility (out of 100)</th>
              <td className="pt-2 font-mono text-right">{(base * 100).toFixed(0)}</td>
            </tr>
            {rf !== null && riskWard && (
              <tr className="text-xs text-gray-700">
                <th scope="row" colSpan={2} className="pt-1 text-left font-medium">
                  × rainfall factor for {rainfallMm} mm ({rf.toFixed(2)}) = risk
                </th>
                <td className="pt-1 font-mono text-right">{Math.round(riskWard.risk_score * 100)}</td>
              </tr>
            )}
          </tfoot>
        </table>

        {riskWard && riskWard.reasons.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-1.5">Model reasons</h4>
            <ul className="space-y-1.5">
              {riskWard.reasons.map((reason, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-gray-800">
                  <span className="w-1.5 h-1.5 rounded-full bg-flood-600 mt-2 flex-shrink-0" aria-hidden="true" />
                  {reason}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
