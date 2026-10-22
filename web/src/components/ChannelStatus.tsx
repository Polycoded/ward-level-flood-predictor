import { cn } from '../lib/utils';
import type { AlertChannel } from '../types';

type Readiness = 'ready' | 'manual' | 'not_connected';

const CHANNELS: Record<AlertChannel, { label: string; readiness: Readiness; detail: string }> = {
  sms: { label: 'SMS', readiness: 'manual', detail: 'Copy text (≤160 chars) into the SMS gateway' },
  whatsapp: { label: 'WhatsApp', readiness: 'ready', detail: 'Opens WhatsApp with the alert pre-filled' },
  voice: { label: 'Voice call', readiness: 'not_connected', detail: 'Twilio voice fallback is configured server-side' },
  livekit: { label: 'LiveKit agent', readiness: 'not_connected', detail: 'Household voice room, server-side' },
};

const STYLES: Record<Readiness, { dot: string; text: string; label: string }> = {
  ready: { dot: 'bg-green-500', text: 'text-green-800', label: 'Ready' },
  manual: { dot: 'bg-sky-500', text: 'text-sky-800', label: 'Copy & send' },
  not_connected: { dot: 'bg-gray-400', text: 'text-gray-700', label: 'Text only here' },
};

/**
 * How each selected channel will actually reach people from this dashboard.
 * The /alerts endpoint drafts messages; delivery is by WhatsApp deep-link or copy,
 * while voice channels run from the backend.
 */
export function ChannelStatus({ selected }: { selected: AlertChannel[] }) {
  return (
    <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2" aria-label="Alert channel status">
      {(Object.keys(CHANNELS) as AlertChannel[]).map((channel) => {
        const c = CHANNELS[channel];
        const s = STYLES[c.readiness];
        const active = selected.includes(channel);
        return (
          <li
            key={channel}
            className={cn('p-2.5 rounded-lg border text-sm', active ? 'border-gray-300 bg-white' : 'border-gray-200 bg-gray-50 opacity-70')}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium text-gray-900">{c.label}</span>
              <span className={cn('flex items-center gap-1 text-xs font-medium', s.text)}>
                <span className={cn('w-2 h-2 rounded-full', s.dot)} aria-hidden="true" />
                {active ? s.label : 'Off'}
              </span>
            </div>
            <p className="text-xs text-gray-600 mt-0.5">{c.detail}</p>
          </li>
        );
      })}
    </ul>
  );
}
