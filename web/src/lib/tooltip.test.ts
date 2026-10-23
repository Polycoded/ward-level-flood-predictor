import { describe, expect, it } from 'vitest';
import { wardTooltipHtml } from './tooltip';

describe('wardTooltipHtml', () => {
  it('renders hostile ward names as text, not markup', () => {
    const html = wardTooltipHtml({ ward_name: '<img src=x onerror="alert(1)">', ward_number: '<b>1</b>', area_sqkm: 2 });
    const host = document.createElement('div');
    host.innerHTML = html;
    expect(host.querySelector('img')).toBeNull();
    expect(host.querySelector('b')).toBeNull();
    expect(host.textContent).toContain('<img src=x onerror="alert(1)">');
  });

  it('includes risk details when available', () => {
    const html = wardTooltipHtml(
      { ward_name: 'Velachery', ward_number: '177', area_sqkm: 3.14159 },
      { ward_id: 1, ward_number: '177', ward_name: 'Velachery', risk_score: 0.81, risk_level: 'very_high', depth_band: '1.0m+', peak_window_hours: 5, reasons: [], features: {} }
    );
    expect(html).toContain('Very High');
    expect(html).toContain('Uncalibrated index 81');
    expect(html).not.toContain('1.0m+');
    expect(html).not.toContain('peak');
    expect(html).toContain('3.14 km²');
  });
});
