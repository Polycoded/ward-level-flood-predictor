import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from '../../App';
import { useFloodStore } from '../../lib/store';
import { api } from '../../api/client';
import { mockApi } from '../../api/mock';
import * as mockAlerts from '../../api/mockAlerts';
import { geometryCenter } from '../../lib/geo';
import { resetForecastCache } from './hooks';
import type { BroadcastAlert } from '../../types';

// Map library is never needed on the resident screen; keep the official view light in tests too.
vi.mock('../MapView', () => ({ MapView: () => <div data-testid="map" /> }));

const initial = useFloodStore.getState();

function openMeteo(mmPerHour: number) {
  const now = new Date();
  const hours = Array.from({ length: 48 }, (_, i) => new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), i)).toISOString().slice(0, 16));
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify({ hourly: { time: hours, precipitation: hours.map(() => mmPerHour) } }), { status: 200 })
  );
}

function grantNotifications() {
  const NotificationMock = Object.assign(vi.fn(), { permission: 'granted', requestPermission: vi.fn().mockResolvedValue('granted') });
  vi.stubGlobal('Notification', NotificationMock);
  return NotificationMock;
}

function geolocationAt(lat: number, lng: number) {
  Object.defineProperty(navigator, 'geolocation', {
    configurable: true,
    value: {
      getCurrentPosition: (ok: PositionCallback) => ok({ coords: { latitude: lat, longitude: lng } } as GeolocationPosition),
      watchPosition: vi.fn(() => 1),
      clearWatch: vi.fn(),
    },
  });
}

beforeEach(() => {
  localStorage.clear();
  mockAlerts.resetMockAlerts();
  resetForecastCache();
  useFloodStore.setState({ ...initial, dataSource: 'mock', resident: { wardId: null, subscription: null }, ui: { ...initial.ui, mode: 'resident', language: 'en', openAlertId: null } }, true);
});
afterEach(() => {
  vi.unstubAllGlobals();
});

async function chooseWardFromList(user: ReturnType<typeof userEvent.setup>, name: string) {
  await user.click(await screen.findByRole('button', { name: 'Choose my ward' }));
  await user.type(screen.getByLabelText('Search ward name or number'), name);
  await user.click(within(screen.getByRole('list', { name: 'Choose my ward' })).getByRole('button', { name }));
}

describe('resident screen', () => {
  it('lets someone pick their ward and see a plain-language estimate without loading the map', async () => {
    openMeteo(10); // 60 mm in the next 6 h
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText('Which ward are you in?')).toBeInTheDocument();
    const name = mockApi.getWards()[4].ward_name;
    await chooseWardFromList(user, name);
    expect(screen.getByText(name)).toBeInTheDocument();
    const card = await screen.findByRole('region', { name: 'Flood-risk estimate' });
    expect(card).toHaveTextContent(/Based on 60 mm of rain forecast for the next 6 hours/);
    expect(card).toHaveTextContent(/An estimate, not an official warning/);
    expect(screen.queryByTestId('map')).toBeNull();
    // the choice survives a reload
    expect(JSON.parse(localStorage.getItem('flood-my-ward')!)).toBe(mockApi.getWards()[4].ward_id);
  });

  it('finds the ward from the phone location, matched on the device', async () => {
    openMeteo(0);
    const target = mockApi.getWards()[42];
    const c = geometryCenter(target.geometry)!;
    geolocationAt(c.lat, c.lng);
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole('button', { name: /Use my location/ }));
    expect(await screen.findByText(target.ward_name)).toBeInTheDocument();
  });

  it('explains when the person is outside Chennai and offers the list', async () => {
    geolocationAt(28.61, 77.2); // Delhi
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole('button', { name: /Use my location/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/outside Chennai/);
    expect(screen.getByLabelText('Search ward name or number')).toBeInTheDocument();
  });

  it('warns residents plainly when the data is the synthetic demo', async () => {
    render(<App />);
    expect(await screen.findByRole('note')).toHaveTextContent(/Demo data: the server is unavailable/);
  });

  it('switches the whole resident screen to Tamil and remembers it', async () => {
    openMeteo(0);
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole('button', { name: /Language: தமிழ்/ }));
    expect(await screen.findByText('நீங்கள் எந்த வார்டில் இருக்கிறீர்கள்?')).toBeInTheDocument();
    expect(document.documentElement.lang).toBe('ta');
    expect(JSON.parse(localStorage.getItem('flood-language')!)).toBe('ta');
  });

  it('shows nearest shelters with walking directions', async () => {
    openMeteo(0);
    const user = userEvent.setup();
    render(<App />);
    await chooseWardFromList(user, mockApi.getWards()[100].ward_name);
    await user.click(await screen.findByRole('button', { name: /Where do I go\?/ }));
    const list = await screen.findByRole('region', { name: 'Nearest shelters' });
    const links = await within(list).findAllByRole('link', { name: 'Directions' });
    expect(links[0].getAttribute('href')).toMatch(/^https:\/\/www\.openstreetmap\.org\/directions\?engine=fossgis_osrm_foot/);
    expect(links[0]).toHaveAttribute('rel', 'noopener noreferrer');
  });
});

describe('alerts end to end (in-browser preview)', () => {
  it('subscribes, an official approves, the phone shows the alert page', async () => {
    openMeteo(60); // heavy: 360 mm → many wards high
    grantNotifications();
    const user = userEvent.setup();
    render(<App />);

    // official proposes alerts at 300 mm; pick a ward that got one
    const proposed = mockAlerts.runAlertCheck(mockApi.getScenarioRisk({ rainfall_mm: 300, duration_hours: 3, builtup_increase_pct: 0 }));
    const target = proposed[0];

    await chooseWardFromList(user, target.ward_name);
    await user.click(screen.getByRole('button', { name: /Get alerts/ }));
    const sheet = await screen.findByRole('dialog', { name: 'Get flood alerts' });
    await user.click(within(sheet).getByRole('button', { name: 'Turn on alerts' }));
    expect(await within(sheet).findByText(/Alerts are on for/)).toBeInTheDocument();
    expect(useFloodStore.getState().resident.subscription?.ward_id).toBe(target.ward_id);
    await user.click(within(sheet).getByRole('button', { name: 'Done' }));

    // approval by the official (another tab in the demo) → storage event wakes this tab
    const approved = mockAlerts.approveAlert(target.id);
    expect(approved.delivery?.push_sent).toBe(1);
    await act(async () => {
      window.dispatchEvent(new StorageEvent('storage', { key: 'flood-mock-alerts-v1' }));
    });

    const page = await screen.findByRole('alertdialog');
    expect(page).toHaveTextContent(/Flood (WARNING|WATCH)/);
    expect(page).toHaveTextContent('EXERCISE: this is a drill, not a real alert');
    expect(page).toHaveTextContent(/What to do now/);
    await user.click(within(page).getByRole('button', { name: "I'm safe" }));
    expect(within(page).getByText(/Thank you. Stay alert./)).toBeInTheDocument();
    await user.click(within(page).getByRole('button', { name: 'Close' }));
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull());
    // banner stays so the alert can be reopened
    expect(screen.getByRole('button', { name: /Active alert for your ward/ })).toBeInTheDocument();
  });

  it('never shows an alert meant for another ward', async () => {
    openMeteo(60);
    const user = userEvent.setup();
    render(<App />);
    const [a, other] = mockAlerts.runAlertCheck(mockApi.getScenarioRisk({ rainfall_mm: 300, duration_hours: 3, builtup_increase_pct: 0 }));
    await chooseWardFromList(user, other.ward_name);
    mockAlerts.approveAlert(a.id);
    await act(async () => {
      window.dispatchEvent(new StorageEvent('storage', { key: 'flood-mock-alerts-v1' }));
    });
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByRole('alertdialog')).toBeNull();
  });

  it('opens the alert page from a notification link, and refuses unknown or hostile ids', async () => {
    const [a] = mockAlerts.runAlertCheck(mockApi.getScenarioRisk({ rainfall_mm: 300, duration_hours: 3, builtup_increase_pct: 0 }));
    mockAlerts.approveAlert(a.id);
    window.history.replaceState(null, '', `/?alert=${a.id}`);
    render(<App />);
    expect(await screen.findByRole('alertdialog')).toHaveTextContent(a.ward_name);
    window.history.replaceState(null, '', '/');
  });

  it('a hostile ?alert= value opens nothing', async () => {
    window.history.replaceState(null, '', '/?alert=%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E');
    render(<App />);
    await screen.findByText('Which ward are you in?');
    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(document.querySelector('img[src="x"]')).toBeNull();
    window.history.replaceState(null, '', '/');
  });

  it('turning alerts off deletes the subscription', async () => {
    openMeteo(0);
    grantNotifications();
    const user = userEvent.setup();
    render(<App />);
    await chooseWardFromList(user, mockApi.getWards()[3].ward_name);
    await user.click(screen.getByRole('button', { name: /Get alerts/ }));
    const sheet = await screen.findByRole('dialog');
    await user.click(within(sheet).getByRole('button', { name: 'Turn on alerts' }));
    await within(sheet).findByText(/Alerts are on/);
    await user.click(within(sheet).getByRole('button', { name: 'Turn off alerts' }));
    await within(sheet).findByRole('button', { name: 'Turn on alerts' });
    expect(useFloodStore.getState().resident.subscription).toBeNull();
    expect(mockAlerts.subscriberCount(mockApi.getWards()[3].ward_id)).toBe(0);
  });

  it('on a live server without push keys, says so instead of sending a subscription it would reject', async () => {
    openMeteo(0);
    grantNotifications();
    vi.spyOn(api, 'getVapidPublicKey').mockResolvedValue('');
    const create = vi.spyOn(api, 'createSubscription');
    const user = userEvent.setup();
    render(<App />);
    await chooseWardFromList(user, mockApi.getWards()[3].ward_name);
    useFloodStore.setState({ dataSource: 'live' });
    await user.click(screen.getByRole('button', { name: /Get alerts/ }));
    const sheet = await screen.findByRole('dialog');
    await user.click(within(sheet).getByRole('button', { name: 'Turn on alerts' }));
    expect(await within(sheet).findByRole('alert')).toHaveTextContent(/aren't switched on for this service yet/);
    expect(create).not.toHaveBeenCalled();
  });

  it('explains blocked notifications instead of failing silently', async () => {
    openMeteo(0);
    vi.stubGlobal('Notification', Object.assign(vi.fn(), { permission: 'default', requestPermission: vi.fn().mockResolvedValue('denied') }));
    const user = userEvent.setup();
    render(<App />);
    await chooseWardFromList(user, mockApi.getWards()[3].ward_name);
    await user.click(screen.getByRole('button', { name: /Get alerts/ }));
    const sheet = await screen.findByRole('dialog');
    await user.click(within(sheet).getByRole('button', { name: 'Turn on alerts' }));
    expect(await within(sheet).findByRole('alert')).toHaveTextContent(/Notifications are blocked/);
  });
});

describe('official approval queue', () => {
  it('proposes alerts from the current scenario and approves or cancels each one', async () => {
    useFloodStore.setState({ ui: { ...useFloodStore.getState().ui, mode: 'official' } });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText(/200 wards loaded/);
    await user.click(screen.getByRole('button', { name: /300 · Hypothetical/ }));
    await user.click(screen.getByRole('button', { name: 'Analyze' }));
    await screen.findByText(/200 wards, highest risk first/);

    await user.click(screen.getByRole('button', { name: 'Approve alerts' }));
    const dialog = await screen.findByRole('dialog', { name: 'Approve alerts' });
    await user.click(within(dialog).getByRole('button', { name: 'Check wards for alerts' }));
    expect(await within(dialog).findByText(/new alert\(s\) proposed/)).toBeInTheDocument();
    const before = within(dialog).getAllByRole('button', { name: 'Approve & send' }).length;
    expect(within(dialog).getAllByText('EXERCISE').length).toBe(before);

    await user.click(within(dialog).getAllByRole('button', { name: 'Approve & send' })[0]);
    expect(await within(dialog).findByText(/phone notification\(s\)/)).toBeInTheDocument();
    await user.click(within(dialog).getAllByRole('button', { name: 'Cancel' })[0]);
    await waitFor(() => expect(within(dialog).getAllByRole('button', { name: 'Approve & send' })).toHaveLength(before - 2));
    // a second check doesn't duplicate what's already proposed or sent
    await user.click(within(dialog).getByRole('button', { name: 'Check wards for alerts' }));
    expect(await within(dialog).findByText(/No new alerts/)).toBeInTheDocument();
  });

  it('shows hostile ward names from the server as text', async () => {
    useFloodStore.setState({ ui: { ...useFloodStore.getState().ui, mode: 'official' } });
    const evil: BroadcastAlert = {
      id: 'x1', ward_id: 1, ward_name: '<img src=x onerror=alert(1)>', level: 'warning', risk_level: 'very_high', risk_score: 0.9,
      rainfall_mm: 100, duration_hours: 3, created_at: '', status: 'pending', exercise: true,
      messages: { en: '<b>bold</b>', ta: '<script>x</script>' },
    };
    vi.spyOn(api, 'getPendingAlerts').mockResolvedValue([evil]);
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText(/200 wards loaded/);
    await user.click(screen.getByRole('button', { name: 'Approve alerts' }));
    const dialog = await screen.findByRole('dialog');
    expect(await within(dialog).findByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
    expect(dialog.querySelector('img, b, script')).toBeNull();
  });

  it('asks for the operator key when the server refuses an approval, and keeps the alert pending', async () => {
    useFloodStore.setState({ ui: { ...useFloodStore.getState().ui, mode: 'official' } });
    const pending: BroadcastAlert = {
      id: 'k1', ward_id: 1, ward_name: 'Ward 168', level: 'warning', risk_level: 'very_high', risk_score: 0.9,
      rainfall_mm: 100, duration_hours: 3, created_at: '', status: 'pending', exercise: true,
      messages: { en: 'EN', ta: 'TA' },
    };
    vi.spyOn(api, 'getPendingAlerts').mockResolvedValue([pending]);
    const approve = vi.spyOn(api, 'approveAlert').mockRejectedValue({ response: { status: 401 } });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText(/200 wards loaded/);
    await user.click(screen.getByRole('button', { name: 'Approve alerts' }));
    const dialog = await screen.findByRole('dialog', { name: 'Approve alerts' });

    await user.click(await within(dialog).findByRole('button', { name: 'Approve & send' }));
    expect(await within(dialog).findByText(/needs a valid operator key/)).toBeInTheDocument();
    expect(approve).toHaveBeenCalledWith('k1');
    // nothing was sent and no simulation pretended it was
    expect(within(dialog).queryByText(/Sent this session/)).toBeNull();
    expect(screen.queryByRole('dialog', { name: 'Alert delivery simulation' })).toBeNull();

    const key = within(dialog).getByLabelText(/Operator key/);
    expect(key).toHaveAttribute('type', 'password');
    await user.type(key, 'op-key');
    expect(localStorage.getItem('flood-operator-key')).toBe('"op-key"');
  });
});
