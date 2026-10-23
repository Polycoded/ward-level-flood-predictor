import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { MapView } from './MapView';
import { RainfallControl } from './RainfallControl';
import { AlertPanel } from './AlertPanel';
import { api } from '../api/client';
import { mockApi, scoreWard } from '../api/mock';
import { useFloodStore } from '../lib/store';

// DOM-level text regression only: does not claim a rendered Leaflet/browser check.
vi.mock('react-leaflet', () => {
  const children = ({ children }: { children?: ReactNode }) => <div>{children}</div>;
  return { MapContainer: children, TileLayer: () => null, GeoJSON: () => null,
    CircleMarker: children, Polyline: children, Tooltip: children };
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('keeps 300 mm hypothetical, not a historical measurement', async () => {
  const onAnalyze = vi.fn();
  const user = userEvent.setup();
  render(<RainfallControl onAnalyze={onAnalyze} busy={false} />);
  await user.click(screen.getByRole('button', { name: '300 · Hypothetical mm' }));
  await user.click(screen.getByRole('button', { name: 'Analyze' }));
  expect(onAnalyze).toHaveBeenCalledWith(expect.objectContaining({ rainfall_mm: 300, duration_hours: 3, source: 'manual' }));
  expect(document.body.textContent).not.toContain('Dec 2023');
});

it('renders roads as screening only without physical depth or closure instructions', () => {
  useFloodStore.getState().setMapView('roads');
  useFloodStore.setState({ wards: [], roadRisks: [{ road_id: 'test', name: 'Artificial road',
    highway_type: 'primary', risk_score: 0.9, risk_level: 'very_high', is_underpass: false,
    flood_depth_estimate_m: 987, geometry: { type: 'LineString', coordinates: [[80, 13], [80.1, 13.1]] } }] });
  render(<MapView />);
  expect(screen.getByText(/Uncalibrated screening indication.*requires review/)).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/987|m water|Close \/ divert traffic|consider closing/);
});

it('forwards the analyzed interval from the alert panel, not an edited pending interval', async () => {
  const risk = mockApi.getRisk({ rainfall_mm: 100, duration_hours: 12 });
  useFloodStore.setState({ riskData: risk, scenario: { rainfall_mm: 200, duration_hours: 1, builtup_increase_pct: 0 } });
  useFloodStore.getState().setDetailWard(risk.wards[0].ward_id);
  const spy = vi.spyOn(api, 'generateAlerts').mockResolvedValue({ alerts: [], sent_at: '' });
  render(<AlertPanel onClose={() => {}} />);
  await userEvent.setup().click(screen.getByRole('button', { name: /Generate/ }));
  expect(spy).toHaveBeenCalledWith([risk.wards[0].ward_id], 100, expect.any(String), expect.any(Array), 12);
});

it.each([1, 3, 12])('mock alerts score and describe the same %sh interval', duration => {
  const ward = mockApi.getWard(1);
  const expected = scoreWard(ward, 100, 0, duration).risk_level.replace(/_/g, ' ');
  const result = mockApi.generateAlerts([1], 100, 'en', ['sms'], duration);
  expect(result.alerts[0].message).toContain(`Uncalibrated index: ${expected}.`);
  expect(result.alerts[0].message).toContain(`100mm/${duration}h`);
  expect(mockApi.generateAlerts([1], 100).alerts).toEqual(mockApi.generateAlerts([1], 100, 'en', ['sms', 'whatsapp'], 3).alerts);
});
