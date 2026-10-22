import type { RiskLevel, RiskResponse } from '../types';

const LEVEL_ORDER: RiskLevel[] = ['very_low', 'low', 'moderate', 'high', 'very_high'];

/** How a land-use scenario changes ward risk relative to today's land use at the same rainfall. */
export function scenarioDelta(current: RiskResponse, baseline: RiskResponse) {
  const before = new Map(baseline.wards.map((w) => [w.ward_id, w]));
  let worse = 0;
  let scoreChange = 0;
  for (const w of current.wards) {
    const b = before.get(w.ward_id);
    if (!b) continue;
    if (LEVEL_ORDER.indexOf(w.risk_level) > LEVEL_ORDER.indexOf(b.risk_level)) worse++;
    scoreChange += w.risk_score - b.risk_score;
  }
  return { worse, avgScoreChange: current.wards.length ? scoreChange / current.wards.length : 0 };
}
