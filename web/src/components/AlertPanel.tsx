import { useState } from 'react';
import { useFloodStore } from '../lib/store';
import { api } from '../api/client';
import { cn, getDepthLabel } from '../lib/utils';
import { safeWhatsAppUrl, whatsAppShareUrl } from '../lib/safe';
import { smsInfo } from '../lib/sms';
import type { AlertChannel, AlertMessage, Language } from '../types';
import { RiskBadge } from './RiskBadge';
import { ChannelStatus } from './ChannelStatus';
import { Modal } from './Modal';

interface AlertPanelProps {
  onClose: () => void;
}

const ALL_CHANNELS: AlertChannel[] = ['sms', 'whatsapp', 'voice', 'livekit'];
const CHANNEL_LABELS: Record<AlertChannel, string> = { sms: 'SMS', whatsapp: 'WhatsApp', voice: 'Voice', livekit: 'LiveKit' };

export function AlertPanel({ onClose }: AlertPanelProps) {
  const { riskData, ui } = useFloodStore();
  // pre-select the ward whose detail panel opened this dialog
  const [selectedWards, setSelectedWards] = useState<number[]>(ui.detailWardId !== null ? [ui.detailWardId] : []);
  const [language, setLanguage] = useState<Language>(ui.language);
  const [channels, setChannels] = useState<AlertChannel[]>(['sms', 'whatsapp']);
  const [alerts, setAlerts] = useState<AlertMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<number | null>(null);

  if (!riskData) return null;

  const topWards = riskData.wards.slice(0, 10);
  // keep a ward picked from the detail panel visible even if it is outside the top 10
  const detailWard = riskData.wards.find((w) => w.ward_id === ui.detailWardId);
  const listedWards = detailWard && !topWards.includes(detailWard) ? [detailWard, ...topWards] : topWards;

  const toggle = <T,>(list: T[], item: T) => (list.includes(item) ? list.filter((x) => x !== item) : [...list, item]);

  const handleGenerate = async () => {
    if (selectedWards.length === 0 || channels.length === 0) return;
    setSending(true);
    setError(null);
    try {
      const response = await api.generateAlerts(selectedWards, riskData.scenario.rainfall_mm, language, channels);
      setAlerts(response.alerts);
    } catch {
      setError('Could not generate alerts. Check the connection and try again.');
    } finally {
      setSending(false);
    }
  };

  const copyMessage = async (index: number, message: string) => {
    try {
      await navigator.clipboard.writeText(message);
      setCopied(index);
      setTimeout(() => setCopied((c) => (c === index ? null : c)), 2000);
    } catch {
      setError('Clipboard is blocked by the browser. Select the text and copy it manually.');
    }
  };

  return (
    <Modal title="Generate alerts" onClose={onClose}>
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        <fieldset>
          <legend className="font-medium text-gray-900 mb-2">Wards</legend>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {listedWards.map((ward) => (
              <label
                key={ward.ward_id}
                className="flex items-center gap-3 p-2.5 rounded-lg border border-gray-200 hover:bg-gray-50 cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={selectedWards.includes(ward.ward_id)}
                  onChange={() => setSelectedWards((prev) => toggle(prev, ward.ward_id))}
                  className="w-4 h-4 accent-flood-600"
                />
                <span className="flex-1 min-w-0">
                  <span className="flex items-center gap-2">
                    <span className="font-medium text-gray-900 truncate">{ward.ward_name}</span>
                    <RiskBadge level={ward.risk_level} size="sm" />
                  </span>
                  <span className="block text-xs text-gray-600">
                    Ward {ward.ward_number} • ≈ {getDepthLabel(ward.depth_band)}
                  </span>
                </span>
              </label>
            ))}
          </div>
          <button
            onClick={() => setSelectedWards(topWards.map((w) => w.ward_id))}
            className="mt-2 text-sm font-medium text-flood-700 hover:text-flood-800"
          >
            Select top 10
          </button>
        </fieldset>

        <fieldset>
          <legend className="font-medium text-gray-900 mb-2">Language</legend>
          <div className="flex gap-2">
            {(['en', 'ta'] as Language[]).map((lang) => (
              <button
                key={lang}
                onClick={() => setLanguage(lang)}
                aria-pressed={language === lang}
                className={cn(
                  'flex-1 px-3 py-2 rounded-lg border text-sm font-medium transition-colors',
                  language === lang
                    ? 'bg-flood-700 text-white border-flood-700'
                    : 'bg-white text-gray-800 border-gray-300 hover:bg-gray-50'
                )}
              >
                {lang === 'en' ? 'English' : 'தமிழ் (Tamil)'}
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend className="font-medium text-gray-900 mb-2">Channels</legend>
          <div className="flex flex-wrap gap-2 mb-3">
            {ALL_CHANNELS.map((channel) => (
              <label
                key={channel}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-gray-300 text-sm cursor-pointer hover:bg-gray-50"
              >
                <input
                  type="checkbox"
                  checked={channels.includes(channel)}
                  onChange={() => setChannels((prev) => toggle(prev, channel))}
                  className="w-4 h-4 accent-flood-600"
                />
                {CHANNEL_LABELS[channel]}
              </label>
            ))}
          </div>
          <ChannelStatus selected={channels} />
        </fieldset>

        <button
          onClick={handleGenerate}
          disabled={sending || selectedWards.length === 0 || channels.length === 0}
          className="w-full btn-primary py-3"
        >
          {sending ? 'Generating…' : `Generate alerts for ${selectedWards.length} ward${selectedWards.length === 1 ? '' : 's'}`}
        </button>

        {error && (
          <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-2.5">
            {error}
          </p>
        )}

        {alerts.length > 0 && (
          <section aria-labelledby="generated-heading" className="border-t border-gray-200 pt-4">
            <h3 id="generated-heading" className="font-medium text-gray-900 mb-3">Generated alerts</h3>
            <ul className="space-y-3">
              {alerts.map((alert, i) => {
                // never open a link the API sent unless it is a real WhatsApp share URL
                const waUrl =
                  alert.channel === 'whatsapp'
                    ? safeWhatsAppUrl(alert.whatsapp_deeplink) ?? whatsAppShareUrl(alert.message)
                    : null;
                const sms = alert.channel === 'sms' ? smsInfo(alert.message) : null;
                return (
                  <li key={i} className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                    <div className="flex items-center justify-between mb-1.5 text-xs">
                      <span className="font-medium text-gray-900 text-sm">{alert.ward_name}</span>
                      <span className="text-gray-700">
                        {CHANNEL_LABELS[alert.channel]} • {alert.language === 'ta' ? 'Tamil' : 'English'}
                        {sms && (
                          <span
                            className={cn('ml-1.5 font-mono', sms.segments > 1 ? 'text-amber-800' : 'text-gray-600')}
                            title={sms.encoding === 'UCS-2' ? 'Tamil and other non-Latin text: 70 characters per SMS' : 'Standard SMS: 160 characters'}
                          >
                            {sms.units}/{sms.singleLimit} · {sms.segments} SMS{sms.segments > 1 ? ' parts' : ''}
                          </span>
                        )}
                      </span>
                    </div>
                    <p className="text-sm text-gray-800 mb-2 whitespace-pre-wrap break-words" lang={alert.language}>
                      {alert.message}
                    </p>
                    <div className="flex gap-3">
                      <button
                        onClick={() => copyMessage(i, alert.message)}
                        className="text-xs font-medium text-flood-700 hover:text-flood-800"
                      >
                        {copied === i ? 'Copied ✓' : 'Copy text'}
                      </button>
                      {waUrl && (
                        <a
                          href={waUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs font-medium text-green-800 hover:text-green-900"
                        >
                          Open in WhatsApp
                        </a>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        )}
      </div>
    </Modal>
  );
}
