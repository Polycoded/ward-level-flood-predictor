import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CrowdReportPanel } from './CrowdReportPanel';
import { ShelterPanel } from './ShelterPanel';
import { useFloodStore } from '../lib/store';
import { mockApi } from '../api/mock';

const initialState = useFloodStore.getState();

beforeEach(() => {
  useFloodStore.setState({ ...initialState, wards: mockApi.getWards(), dataSource: 'mock' }, true);
});

describe('CrowdReportPanel (preview shell)', () => {
  it('requires a ward and keeps nothing but sanitised, length-limited text', async () => {
    const user = userEvent.setup();
    render(<CrowdReportPanel onClose={() => {}} />);
    const dialog = screen.getByRole('dialog', { name: /Report flooding/ });

    await user.click(within(dialog).getByRole('button', { name: 'Save report' }));
    expect(within(dialog).getByRole('alert')).toHaveTextContent(/Choose the ward/);

    await user.selectOptions(within(dialog).getByLabelText('Ward'), '5');
    const note = within(dialog).getByLabelText(/What did you see/);
    await user.type(note, '<img src=x onerror=alert(1)> water at knee ' + 'x'.repeat(400));
    expect((note as HTMLTextAreaElement).value.length).toBeLessThanOrEqual(280);
    await user.click(within(dialog).getByRole('button', { name: 'Save report' }));

    const saved = within(dialog).getByRole('list', { name: 'Reports this session' });
    expect(within(saved).getAllByRole('listitem')).toHaveLength(1);
    expect(saved.querySelector('img')).toBeNull();
    expect(saved.textContent).toContain('<img src=x onerror=alert(1)>');
  });

  it('caps reports per session to limit spam', async () => {
    const user = userEvent.setup();
    render(<CrowdReportPanel onClose={() => {}} />);
    await user.selectOptions(screen.getByLabelText('Ward'), '1');
    const save = screen.getByRole('button', { name: 'Save report' });
    for (let i = 0; i < 21; i++) await user.click(save);
    expect(screen.getAllByRole('listitem')).toHaveLength(20);
    expect(screen.getByRole('alert')).toHaveTextContent(/At most 20/);
  });

  it('closes on Escape', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<CrowdReportPanel onClose={onClose} />);
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
  });
});

describe('ShelterPanel', () => {
  it('lists the nearest shelters from the city centre with safe outbound links', async () => {
    render(<ShelterPanel />);
    const items = await screen.findAllByRole('link', { name: /Walking directions/ });
    expect(items.length).toBeGreaterThan(0);
    for (const link of items) {
      expect(link.getAttribute('href')).toMatch(/^https:\/\/www\.openstreetmap\.org\/directions\?engine=fossgis_osrm_foot&route=/);
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    }
    expect(screen.getByText(/From: Chennai city centre/)).toBeInTheDocument();
    // distances are sorted nearest first
    const shelters = useFloodStore.getState().shelters;
    expect(shelters.map((s) => s.distance_km)).toEqual([...shelters.map((s) => s.distance_km)].sort((a, b) => a - b));
  });

  it('explains a denied location permission and keeps working', async () => {
    const user = userEvent.setup();
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: { getCurrentPosition: (_ok: unknown, fail: (e: unknown) => void) => fail({ code: 1 }) },
    });
    render(<ShelterPanel />);
    await screen.findAllByRole('link', { name: /Walking directions/ });
    await user.click(screen.getByRole('button', { name: 'Use my location' }));
    expect(screen.getByRole('alert')).toHaveTextContent(/permission denied/);
    expect(screen.getAllByRole('link', { name: /Walking directions/ }).length).toBeGreaterThan(0);
  });

  it('only asks for location when the user presses the button', async () => {
    const getCurrentPosition = vi.fn();
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition } });
    render(<ShelterPanel />);
    await screen.findAllByRole('link', { name: /Walking directions/ });
    expect(getCurrentPosition).not.toHaveBeenCalled();
  });
});
