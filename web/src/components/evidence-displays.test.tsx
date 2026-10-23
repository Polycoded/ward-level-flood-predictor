import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { mockApi } from '../api/mock';
import { api } from '../api/client';
import { useFloodStore } from '../lib/store';
import { RankedList } from './RankedList';
import { AlertPanel } from './AlertPanel';
import { WardDetailPanel } from './WardDetailPanel';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('keeps compatibility fields but never renders physical proxies in ward displays', async () => {
  const risk = mockApi.getRisk({ rainfall_mm: 100, duration_hours: 3 });
  const ward = risk.wards[0];
  ward.depth_band = '1.0m+';
  ward.peak_window_hours = 987;
  useFloodStore.setState({ riskData: risk });
  vi.spyOn(api, 'getWard').mockResolvedValue(mockApi.getWard(ward.ward_id));
  render(<><RankedList /><AlertPanel onClose={() => {}} /><WardDetailPanel wardId={ward.ward_id} /></>);
  await screen.findByText('Uncalibrated index, not a prediction of flood probability, depth or timing.');
  expect(document.body.textContent).not.toMatch(/1\.0m\+|987|Likely water depth|Expected peak|Peak ~/);
  expect(document.body.textContent).toContain(ward.ward_name);
});

it('mock alert messages do not publish compatibility depth or timing', () => {
  for (const language of ['en', 'ta'] as const) {
    const response = mockApi.generateAlerts([1], 100, language, ['sms', 'whatsapp']);
    for (const alert of response.alerts) {
      expect(alert.message).not.toMatch(/deep|up to|peak|1\.0m|0\.15/);
      expect(alert.message).toContain(language === 'en' ? 'Uncalibrated index' : 'அளவுத்திருத்தம்');
    }
  }
});
