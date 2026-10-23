import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';
import { api } from './api/client';
import { useFloodStore } from './lib/store';
import { validateRiskResponse } from './api/validate';

// Leaflet needs a real layout engine; the map is covered by the browser test pass instead.
vi.mock('./components/MapView', () => ({ MapView: () => <div data-testid="map" /> }));

const initialState = useFloodStore.getState();

beforeEach(() => {
  // the api singleton decides its source once per page load; mirror that after resetting the store
  useFloodStore.setState({ ...initialState, dataSource: 'mock' }, true);
  vi.spyOn(console, 'warn').mockImplementation(() => {});
});

async function renderLoaded() {
  const user = userEvent.setup();
  render(<App />);
  await screen.findByText(/200 wards loaded/);
  return user;
}

async function analyze(user: ReturnType<typeof userEvent.setup>, preset = /300 · Hypothetical/) {
  await user.click(screen.getByRole('button', { name: preset }));
  await user.click(screen.getByRole('button', { name: 'Analyze' }));
  await screen.findByText(/200 wards, highest risk first/);
}

const rankedItems = () => within(screen.getByRole('list', { name: /ranked by flood risk/i })).getAllByRole('listitem');

describe('official runs a rainfall scenario', () => {
  it('starts with an explanatory empty state and an honest data-source badge', async () => {
    await renderLoaded();
    expect(screen.getByText('Mock data')).toBeInTheDocument();
    expect(screen.getByText(/No analysis yet/)).toBeInTheDocument();
  });

  it('ranks every ward from highest to lowest risk', async () => {
    const user = await renderLoaded();
    await analyze(user);
    const items = rankedItems();
    expect(items).toHaveLength(200);
    const scores = items.map((li) => Number(li.textContent!.match(/(\d+)$/)![1]));
    expect([...scores].sort((a, b) => b - a)).toEqual(scores);
    expect(screen.getByText(/Top risk:/)).toBeInTheDocument();
  });

  it('more rain never lowers any ward risk score', async () => {
    const user = await renderLoaded();
    await analyze(user, /^50 mm$/);
    const low = new Map(useFloodStore.getState().riskData!.wards.map((w) => [w.ward_id, w.risk_score]));
    await analyze(user, /300 · Hypothetical/);
    for (const w of useFloodStore.getState().riskData!.wards) expect(w.risk_score).toBeGreaterThanOrEqual(low.get(w.ward_id)!);
  });

  it('clamps out-of-range manual input to what the API accepts', async () => {
    const user = await renderLoaded();
    const amount = screen.getByLabelText('Amount (mm)');
    await user.clear(amount);
    await user.type(amount, '99999');
    expect(amount).toHaveValue(500);
    fireEvent.change(amount, { target: { value: '-40' } });
    expect(amount).toHaveValue(0);
  });

  it('lets you empty the amount box and type a new value without a stray leading zero', async () => {
    const user = await renderLoaded();
    const amount = screen.getByLabelText('Amount (mm)');
    await user.clear(amount);
    expect(amount).toHaveValue(null);
    expect(screen.getByRole('button', { name: 'Analyze' })).toBeDisabled();
    expect(screen.getByText(/Enter a rainfall amount/)).toBeInTheDocument();
    await user.type(amount, '150');
    expect((amount as HTMLInputElement).value).toBe('150');
    await user.click(screen.getByRole('button', { name: 'Analyze' }));
    await screen.findByText(/200 wards, highest risk first/);
    expect(useFloodStore.getState().riskData!.scenario.rainfall_mm).toBe(150);
  });

  it('runs one analysis when Analyze is hammered by an auto-clicker', async () => {
    await renderLoaded();
    const spy = vi.spyOn(api, 'getScenarioRisk');
    const button = screen.getByRole('button', { name: 'Analyze' });
    for (let i = 0; i < 20; i++) fireEvent.click(button);
    await screen.findByText(/200 wards, highest risk first/);
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('filters the ranking by search text and risk level, and copes with hostile input', async () => {
    const user = await renderLoaded();
    await analyze(user);
    const search = screen.getByLabelText('Search wards');
    await user.type(search, 'Adyar');
    expect(rankedItems().every((li) => /Adyar/.test(li.textContent!))).toBe(true);
    await user.clear(search);
    await user.type(search, '<script>alert(1)</script>');
    expect(screen.getByText('No wards match this filter.')).toBeInTheDocument();
    expect(document.querySelector('script[src], ol script')).toBeNull();
    await user.clear(search);
    await user.click(screen.getByRole('button', { name: 'High+' }));
    expect(rankedItems().every((li) => /High/.test(li.textContent!))).toBe(true);
  });

  it('shows how much a +30% built-up future worsens the same storm', async () => {
    const user = await renderLoaded();
    await analyze(user);
    await user.click(screen.getByRole('button', { name: '+30% built-up' }));
    expect(await screen.findByText(/move up a risk level; average score \+/)).toBeInTheDocument();
    expect(useFloodStore.getState().scenario.builtup_increase_pct).toBe(30);
  });

  it('uses one duration-aware formula for today and the built-up scenarios', async () => {
    const user = await renderLoaded();
    const spy = vi.spyOn(api, 'getScenarioRisk');
    const risk = vi.spyOn(api, 'getRisk');
    await user.selectOptions(screen.getByLabelText('Over'), '12');
    await user.click(screen.getByRole('button', { name: /^150$|^200 mm$/ }));
    await user.click(screen.getByRole('button', { name: 'Analyze' }));
    await screen.findByText(/200 wards, highest risk first/);
    expect(spy).toHaveBeenLastCalledWith({ rainfall_mm: 200, duration_hours: 3, builtup_increase_pct: 0 });
    expect(risk).not.toHaveBeenCalled();

    // a long storm: more paving must never look safer than today
    await user.selectOptions(screen.getByLabelText('Over'), '12');
    await user.click(screen.getByRole('button', { name: 'Analyze' }));
    await screen.findByText(/200 mm \/ 12 h/);
    const today = new Map(useFloodStore.getState().riskData!.wards.map((w) => [w.ward_id, w.risk_score]));
    await user.click(screen.getByRole('button', { name: '+15% built-up' }));
    await screen.findByText(/move up a risk level/);
    for (const w of useFloodStore.getState().riskData!.wards) expect(w.risk_score).toBeGreaterThanOrEqual(today.get(w.ward_id)!);
    expect(spy).toHaveBeenCalledWith({ rainfall_mm: 200, duration_hours: 12, builtup_increase_pct: 15 });
    expect(spy).toHaveBeenCalledWith({ rainfall_mm: 200, duration_hours: 12, builtup_increase_pct: 0 });
  });

  it('clears the analysis', async () => {
    const user = await renderLoaded();
    await analyze(user);
    await user.click(screen.getByRole('button', { name: 'Clear' }));
    expect(screen.getByText(/No analysis yet/)).toBeInTheDocument();
  });
});

describe('ward detail and explainability', () => {
  it('explains a ward with weighted factors and the model reasons, and closes on Escape', async () => {
    const user = await renderLoaded();
    await analyze(user);
    await user.click(within(rankedItems()[0]).getByRole('button'));
    const panel = await screen.findByRole('complementary', { name: 'Ward details' });
    expect(within(panel).getByText('Why this ward?')).toBeInTheDocument();
    expect(within(panel).getAllByRole('row').length).toBeGreaterThanOrEqual(7);
    expect(within(panel).getByText('Model reasons')).toBeInTheDocument();
    // Unsupported physical outputs remain suppressed after integration.
    expect(within(panel).queryByText('Indicative depth band')).not.toBeInTheDocument();
    expect(within(panel).queryByText('Indicative peak window')).not.toBeInTheDocument();
    expect(within(panel).getByText(/Uncalibrated index, not a prediction/)).toBeInTheDocument();
    expect(within(panel).queryByText(/from now/)).toBeNull();
    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('complementary', { name: 'Ward details' })).toBeNull());
  });

  it('shows a clear error when a ward cannot be loaded', async () => {
    const user = await renderLoaded();
    vi.spyOn(api, 'getWard').mockRejectedValueOnce(new Error('boom'));
    await analyze(user);
    await user.click(within(rankedItems()[0]).getByRole('button'));
    expect(await screen.findByText(/Could not load this ward/)).toBeInTheDocument();
  });
});

describe('alerts', () => {
  it('drafts a Tamil alert for the open ward with copy and WhatsApp actions', async () => {
    const user = await renderLoaded();
    await analyze(user);
    await user.click(within(rankedItems()[0]).getByRole('button'));
    await user.click(await screen.findByRole('button', { name: 'Draft alerts for this ward' }));

    const dialog = await screen.findByRole('dialog', { name: 'Generate alerts' });
    await user.click(within(dialog).getByRole('button', { name: /Tamil/ }));
    await user.click(within(dialog).getByRole('button', { name: /Generate alerts for 1 ward$/ }));

    const generated = await within(dialog).findByRole('region', { name: 'Generated alerts' });
    const messages = within(generated).getAllByRole('listitem');
    expect(messages).toHaveLength(2); // SMS + WhatsApp
    expect(messages[0].textContent).toMatch(/வெள்ள/);

    const wa = within(generated).getByRole('link', { name: 'Open in WhatsApp' });
    expect(wa.getAttribute('href')).toMatch(/^https:\/\/wa\.me\/\?text=/);
    expect(wa).toHaveAttribute('rel', 'noopener noreferrer');

    await user.click(within(generated).getAllByRole('button', { name: 'Copy text' })[0]);
    expect(await navigator.clipboard.readText()).toMatch(/வெள்ள/);
    expect(await within(generated).findByText('Copied ✓')).toBeInTheDocument();

    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    // one Escape closes only the top layer; the ward drawer underneath stays open
    expect(screen.getByRole('complementary', { name: 'Ward details' })).toBeInTheDocument();
    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('complementary', { name: 'Ward details' })).toBeNull());
  });

  it('counts Tamil SMS in 70-character parts', async () => {
    const user = await renderLoaded();
    await analyze(user);
    await user.click(screen.getByRole('button', { name: 'Draft messages' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Select top 10' }));
    await user.click(within(dialog).getByRole('button', { name: /Tamil/ }));
    await user.click(within(dialog).getByRole('button', { name: /Generate alerts/ }));
    const generated = await within(dialog).findByRole('region', { name: 'Generated alerts' });
    expect(within(generated).getAllByText(/\/70 · \d SMS parts/).length).toBeGreaterThan(0);
  });

  it('refuses dangerous or pre-addressed links from the API and renders hostile names as text', async () => {
    const user = await renderLoaded();
    await analyze(user);
    vi.spyOn(api, 'generateAlerts').mockResolvedValue({
      sent_at: '',
      alerts: [
        { ward_id: 1, ward_name: '<img src=x onerror=alert(1)>', channel: 'whatsapp', language: 'en', message: 'Flood <b>now</b>', whatsapp_deeplink: 'javascript:alert(document.cookie)' },
        { ward_id: 1, ward_name: 'W', channel: 'whatsapp', language: 'en', message: 'm2', whatsapp_deeplink: 'https://wa.me/919876543210?text=m2' },
      ],
    });
    await user.click(screen.getByRole('button', { name: 'Draft messages' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Select top 10' }));
    await user.click(within(dialog).getByRole('button', { name: /Generate alerts for 10 wards/ }));
    await within(dialog).findByText('Generated alerts');

    const links = within(dialog).getAllByRole('link', { name: 'Open in WhatsApp' });
    for (const link of links) {
      expect(link.getAttribute('href')).toMatch(/^https:\/\/wa\.me\/\?text=/);
    }
    expect(dialog.querySelector('img')).toBeNull();
    expect(dialog.querySelector('b')).toBeNull();
    expect(within(dialog).getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
  });

  it('reports a failed generation instead of failing silently', async () => {
    const user = await renderLoaded();
    await analyze(user);
    vi.spyOn(api, 'generateAlerts').mockRejectedValue(new Error('500'));
    await user.click(screen.getByRole('button', { name: 'Draft messages' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Select top 10' }));
    await user.click(within(dialog).getByRole('button', { name: /Generate alerts/ }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(/Could not generate alerts/);
  });
});

describe('rainfall from a CSV upload', () => {
  it('rejects a malformed file and accepts a valid hourly series', async () => {
    const user = await renderLoaded();
    await user.click(screen.getByRole('tab', { name: 'CSV' }));
    const input = screen.getByLabelText('Hourly rainfall CSV');

    await user.upload(input, new File(['time,mm\n00:00,ten\n'], 'bad.csv', { type: 'text/csv' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/not a number/);
    expect(screen.getByRole('button', { name: 'Analyze' })).toBeDisabled();

    await user.upload(input, new File(['mm\n60\n80\n70\n'], 'dec2023.csv', { type: 'text/csv' }));
    expect(await screen.findByText('210 mm')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Analyze' }));
    await screen.findByText(/200 wards, highest risk first/);
    expect(useFloodStore.getState().riskData!.scenario.rainfall_mm).toBe(210);
    expect(screen.getByText('CSV rainfall')).toBeInTheDocument();
  });

  it('rejects an oversized file without reading it', async () => {
    const user = await renderLoaded();
    await user.click(screen.getByRole('tab', { name: 'CSV' }));
    const huge = new File(['1\n'.repeat(70_000)], 'huge.csv', { type: 'text/csv' });
    await user.upload(screen.getByLabelText('Hourly rainfall CSV'), huge);
    expect(await screen.findByRole('alert')).toHaveTextContent(/too large/);
  });
});

describe('live forecast', () => {
  it('uses Open-Meteo hourly precipitation and shows the provider', async () => {
    const now = new Date();
    const hours = Array.from({ length: 48 }, (_, i) => new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), i)).toISOString().slice(0, 16));
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ hourly: { time: hours, precipitation: hours.map(() => 2) } }), { status: 200 })
    );
    const user = await renderLoaded();
    await user.click(screen.getByRole('tab', { name: 'Forecast' }));
    await user.selectOptions(screen.getByLabelText(/Open-Meteo forecast/), '6');
    await user.click(screen.getByRole('button', { name: 'Fetch' }));
    expect(await screen.findByText('12 mm')).toBeInTheDocument();
    expect(String(fetchMock.mock.calls[0][0])).toContain('api.open-meteo.com');
    await user.click(screen.getByRole('button', { name: 'Analyze' }));
    await screen.findByText(/200 wards, highest risk first/);
    expect(await screen.findByText('Open-Meteo forecast')).toBeInTheDocument();
  });

  it('sends one forecast request when Fetch is hammered', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve(new Response('{}', { status: 200 })), 50))
    );
    const user = await renderLoaded();
    await user.click(screen.getByRole('tab', { name: 'Forecast' }));
    const fetchButton = screen.getByRole('button', { name: 'Fetch' });
    for (let i = 0; i < 10; i++) fireEvent.click(fetchButton);
    await screen.findByRole('alert');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('explains when the weather service is down', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));
    const user = await renderLoaded();
    await user.click(screen.getByRole('tab', { name: 'Forecast' }));
    await user.click(screen.getByRole('button', { name: 'Fetch' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/unreachable/);
  });
});

describe('top bar', () => {
  it('has no Validation tab and does not fetch validation data for it', async () => {
    const validation = vi.spyOn(api, 'getValidation');
    const user = await renderLoaded();
    await analyze(user);
    expect(screen.queryByRole('button', { name: /Validation/ })).toBeNull();
    expect(screen.queryByRole('region', { name: 'Evaluation evidence' })).toBeNull();
    expect(validation).not.toHaveBeenCalled();
  });
});

describe('hostile or broken backend', () => {
  it.each([
    ['an HTML page with status 200', '<!doctype html><html><body>index</body></html>'],
    ['wards: null', { scenario: { rainfall_mm: 100, duration_hours: 3 }, wards: null, generated_at: 'x', model_version: '1' }],
  ])('shows an error instead of crashing when /scenario returns %s', async (_, body) => {
    const user = await renderLoaded();
    await analyze(user);
    vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.spyOn(api, 'getScenarioRisk').mockImplementation(async () => validateRiskResponse(body));
    await user.click(screen.getByRole('button', { name: 'Analyze' }));
    expect(await screen.findByText(/server returned invalid risk data/)).toBeInTheDocument();
    expect(rankedItems()).toHaveLength(200); // previous result still on screen
  });

  it('opens a ward whose reasons and features are corrupt without crashing', async () => {
    const user = await renderLoaded();
    vi.spyOn(api, 'getScenarioRisk').mockImplementation(async () =>
      validateRiskResponse({
        scenario: { rainfall_mm: 100, duration_hours: 3 }, generated_at: 'not a date', model_version: '1',
        wards: [{ ward_id: 2, ward_number: '2', ward_name: 'B', risk_score: 57, risk_level: 'catastrophic', depth_band: '9m', peak_window_hours: -3, reasons: null, features: null }],
      })
    );
    await user.click(screen.getByRole('button', { name: 'Analyze' }));
    await screen.findByText(/1 wards, highest risk first/);
    expect(rankedItems()[0]).toHaveTextContent('Very High');
    expect(rankedItems()[0]).toHaveTextContent(/100$/);
    await user.click(within(rankedItems()[0]).getByRole('button'));
    expect(await screen.findByText('Why this ward?')).toBeInTheDocument();
    expect(screen.queryByText(/Something went wrong/)).toBeNull();
  });
});

describe('failure handling', () => {
  it('keeps the previous result and shows an error when analysis fails', async () => {
    const user = await renderLoaded();
    await analyze(user);
    vi.spyOn(api, 'getScenarioRisk').mockRejectedValueOnce(new Error('timeout'));
    vi.spyOn(console, 'error').mockImplementation(() => {});
    await user.click(screen.getByRole('button', { name: 'Analyze' }));
    expect(await screen.findByText(/Risk analysis failed/)).toBeInTheDocument();
    expect(rankedItems()).toHaveLength(200);
  });
});
