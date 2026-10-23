import { escapeHtml } from './safe';
import { getRiskColor, getRiskLabel } from './utils';
import type { WardRisk } from '../types';

/** Tooltip markup for a ward. Ward names come from OSM, so everything is escaped. */
export function wardTooltipHtml(
  props: { ward_name: string; ward_number: string; area_sqkm: number },
  risk?: WardRisk
): string {
  let html = `<strong>${escapeHtml(props.ward_name)}</strong><br/>Ward ${escapeHtml(props.ward_number)} • ${Number(props.area_sqkm).toFixed(2)} km²`;
  if (risk) {
    html +=
      `<br/><span style="color:${getRiskColor(risk.risk_level)};font-weight:600">${escapeHtml(getRiskLabel(risk.risk_level))}</span>` +
      ` • Uncalibrated index ${Math.round(risk.risk_score * 100)} / 100`;
  }
  return html;
}
