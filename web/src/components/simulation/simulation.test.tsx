import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from '../../App';
import { useFloodStore } from '../../lib/store';
import * as mockAlerts from '../../api/mockAlerts';

vi.mock('../MapView', () => ({ MapView: () => <div data-testid="map" /> }));

const initial = useFloodStore.getState();

beforeEach(() => {
  localStorage.clear();
  mockAlerts.resetMockAlerts();
  // reduced motion: the simulation jumps straight to its end state
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('reduce'), media: q, addEventListener() {}, removeEventListener() {} }));  useFloodStore.setState({ ...initial, dataSource: 'mock', ui: { ...initial.ui, mode: 'official', simulation: null } }, true);
});

async function analyze300(user: ReturnType<typeof userEvent.setup>) {
  render(<App />);
  await screen.findByText(/200 wards loaded/);
  await user.click(screen.getByRole('button', { name: /300 · Hypothetical/ }));
  await user.click(screen.getByRole('button', { name: 'Analyze' }));
  await screen.findByText(/200 wards, highest risk first/);
}

it('approving an alert plays the delivery simulation for that ward', async () => {
  const user = userEvent.setup();
  await analyze300(user);
  await user.click(screen.getByRole('button', { name: 'Approve alerts' }));
  const queue = await screen.findByRole('dialog', { name: 'Approve alerts' });
  await user.click(within(queue).getByRole('button', { name: 'Check wards for alerts' }));
  await within(queue).findByText(/new alert\(s\) proposed/);
  await user.click(within(queue).getAllByRole('button', { name: 'Approve & send' })[0]);

  const sim = await screen.findByRole('dialog', { name: 'Alert delivery simulation' }, { timeout: 5000 });
  expect(sim).toHaveTextContent('Simulation: synthetic towers & phones');
  expect(sim).toHaveTextContent(/(WARNING|WATCH) · .+\(exercise\)/);
  expect(await within(sim).findByText(/Delivery complete: \d+ of \d+ phones in the area/, {}, { timeout: 5000 })).toBeInTheDocument();
  expect(within(sim).getByText(/towers start cell broadcast/)).toBeInTheDocument();
  expect(within(sim).getByText('Phones in alert area reached').nextSibling?.textContent).toMatch(/\d+ \/ \d+ \(\d+%\)/);

  await user.click(within(sim).getByRole('button', { name: 'Close simulation' }));
  expect(screen.queryByRole('dialog', { name: 'Alert delivery simulation' })).toBeNull();
});

it('can simulate straight from the current analysis and switch delivery paths', async () => {
  const user = userEvent.setup();
  await analyze300(user);
  await user.click(screen.getByRole('button', { name: 'Simulate delivery' }));
  const sim = await screen.findByRole('dialog', { name: 'Alert delivery simulation' }, { timeout: 5000 });
  await within(sim).findByText(/Delivery complete/, {}, { timeout: 5000 });
  const reached = () => within(sim).getByText('Phones in alert area reached').nextSibling?.textContent ?? '';
  const both = reached();
  await user.click(within(sim).getByRole('button', { name: 'App + WhatsApp' }));
  const appOnly = reached();
  // app-only reaches fewer phones than cell broadcast + app together
  const n = (s: string) => Number(s.split(' ')[0].replace(/,/g, ''));
  expect(n(appOnly)).toBeLessThan(n(both));
  // the timeline follows the chosen path: no tower step, and the total matches the counter
  expect(within(sim).queryByText(/towers start cell broadcast/)).toBeNull();
  expect(within(sim).getByText(/Delivery complete/).textContent).toContain(`${n(appOnly)} of`);
  expect(within(sim).getByText('Towers broadcasting').nextSibling?.textContent).toMatch(/^0 \//);
});

it('the simulate button waits for an analysis', async () => {
  render(<App />);
  await screen.findByText(/200 wards loaded/);
  expect(screen.getByRole('button', { name: 'Simulate delivery' })).toBeDisabled();
});
