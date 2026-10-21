import { useState } from 'react';
import { createPortal } from 'react-dom';
import { useFloodStore } from '../lib/store';
import { api } from '../api/client';
import { cn, getRiskColor, getRiskLabel, getDepthLabel } from '../lib/utils';
import type { AlertChannel, Language, WardRisk } from '../types';
import { RiskBadge } from './RiskBadge';

interface AlertPanelProps {
  onClose: () => void;
}

export function AlertPanel({ onClose }: AlertPanelProps) {
  const { riskData, ui, setAlertsOpen } = useFloodStore();
  const [selectedWards, setSelectedWards] = useState<number[]>([]);
  const [language, setLanguage] = useState<Language>(ui.language);
  const [channels, setChannels] = useState<AlertChannel[]>(['sms', 'whatsapp']);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [sending, setSending] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  const topWards = riskData?.wards.slice(0, 10) || [];

  const handleSendAlerts = async () => {
    if (selectedWards.length === 0) return;
    
    setSending(true);
    try {
      const response = await api.generateAlerts(selectedWards, riskData!.scenario.rainfall_mm, language, channels);
      setAlerts(response.alerts);
    } catch (error) {
      console.error('Failed to send alerts:', error);
    } finally {
      setSending(false);
    }
  };

  const copyMessage = (message: string) => {
    navigator.clipboard.writeText(message);
    setCopied(message);
    setTimeout(() => setCopied(null), 2000);
  };

  const openWhatsApp = (deeplink: string) => {
    window.open(deeplink, '_blank');
  };

  if (!riskData) return null;

  const content = (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative w-full max-w-2xl max-h-[90vh] bg-white rounded-xl shadow-xl overflow-hidden flex flex-col animate-in">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Generate Alerts</h2>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-gray-100 text-gray-500">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          <div>
            <h3 className="font-medium text-gray-900 mb-3">Select Wards</h3>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {topWards.map((ward) => (
                <label key={ward.ward_id} className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 hover:bg-gray-50 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedWards.includes(ward.ward_id)}
                    onChange={() => setSelectedWards(prev =>
                      prev.includes(ward.ward_id)
                        ? prev.filter(w => w !== ward.ward_id)
                        : [...prev, ward.ward_id]
                    )}
                    className="w-4 h-4 text-flood-600 border-gray-300 rounded focus:ring-flood-500"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900 truncate">{ward.ward_name}</span>
                      <RiskBadge level={ward.risk_level} size="sm" />
                    </div>
                    <p className="text-xs text-gray-500">Ward {ward.ward_number} • {getDepthLabel(ward.depth_band)}</p>
                  </div>
                </label>
              ))}
            </div>
            <button
              onClick={() => setSelectedWards(topWards.map(w => w.ward_id))}
              className="mt-2 text-sm text-flood-600 hover:text-flood-700"
            >
              Select all top 10
            </button>
          </div>

          <div className="border-t border-gray-100 pt-4">
            <h3 className="font-medium text-gray-900 mb-3">Alert Settings</h3>
            
            <div className="space-y-4">
              <div>
                <label className="label">Language</label>
                <div className="flex gap-2">
                  <button
                    onClick={() => setLanguage('en')}
                    className={cn(
                      'flex-1 px-3 py-2 rounded-lg border text-sm font-medium transition-colors',
                      language === 'en'
                        ? 'bg-flood-600 text-white border-flood-600'
                        : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                    )}
                  >
                    English
                  </button>
                  <button
                    onClick={() => setLanguage('ta')}
                    className={cn(
                      'flex-1 px-3 py-2 rounded-lg border text-sm font-medium transition-colors',
                      language === 'ta'
                        ? 'bg-flood-600 text-white border-flood-600'
                        : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                    )}
                  >
                    தமிழ்
                  </button>
                </div>
              </div>

              <div>
                <label className="label">Channels</label>
                <div className="flex flex-wrap gap-2">
                  {(['sms', 'whatsapp', 'voice', 'livekit'] as AlertChannel[]).map((channel) => (
                    <label key={channel} className="flex items-center gap-2 px-3 py-2 rounded-lg border text-sm cursor-pointer hover:bg-gray-50 transition-colors">
                      <input
                        type="checkbox"
                        checked={channels.includes(channel)}
                        onChange={() => setChannels(prev =>
                          prev.includes(channel)
                            ? prev.filter(c => c !== channel)
                            : [...prev, channel]
                        )}
                        className="w-4 h-4 text-flood-600 border-gray-300 rounded focus:ring-flood-500"
                      />
                      <span className="capitalize">{channel}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <button
            onClick={handleSendAlerts}
            disabled={sending || selectedWards.length === 0}
            className="w-full btn-primary py-3 disabled:opacity-50"
          >
            {sending ? 'Sending...' : `Send Alerts to ${selectedWards.length} ward(s)`}
          </button>
        </div>

        {alerts.length > 0 && (
          <div className="border-t border-gray-100 pt-4">
            <h3 className="font-medium text-gray-900 mb-3">Generated Alerts</h3>
            <div className="max-h-64 overflow-y-auto space-y-3">
              {alerts.map((alert, i) => (
                <div key={i} className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-gray-900">{alert.ward_name}</span>
                    <span className="text-xs text-gray-500 capitalize">{alert.channel}</span>
                  </div>
                  <p className="text-sm text-gray-700 mb-2">{alert.message}</p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => copyMessage(alert.message)}
                      className="text-xs text-flood-600 hover:text-flood-700 flex items-center gap-1"
                    >
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                      </svg>
                      {copied === alert.message ? 'Copied!' : 'Copy'}
                    </button>
                    {alert.whatsapp_deeplink && (
                      <button
                        onClick={() => openWhatsApp(alert.whatsapp_deeplink)}
                        className="text-xs text-green-600 hover:text-green-700 flex items-center gap-1"
                      >
                        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.263.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378 3.474 3.474 0 01-1.64-5.72 3.37 3.37 0 011.563-1.786 11.925 11.925 0 015.242.034c1.99.39 2.997 1.881 3.302 3.622.316 1.814-.372 3.612-1.888 4.585-2.668 1.776-5.963 1.034-7.45.062a8.466 8.466 0 01-2.787-1.839c-.297-.298-.595-.398-.978-.272-.38.124-.57.417-.57.772 0 .297.115.653.272.916l.765 1.125c.324.473.499.972.499 1.491 0 .654-.38 1.105-.882 1.487-.502.38-1.218.635-2.01.825-.792.188-1.621.162-2.394-.118" />
                        </svg>
                        WhatsApp
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );

  return createPortal(content, document.body);
}