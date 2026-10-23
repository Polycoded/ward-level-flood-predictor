import { useCallback, useEffect, useState } from 'react';
import { api, isAuthError } from '../api/client';
import { getOperatorKey, setOperatorKey } from '../lib/operatorKey';
import { useFloodStore } from '../lib/store';
import { cn, getRiskLabel } from '../lib/utils';
import type { BroadcastAlert } from '../types';
import { Modal } from './Modal';

/**
 * Human-in-the-loop broadcast: the alert engine proposes ward alerts, an official reads the
 * exact EN/TA text and approves or cancels each one. Nothing reaches phones without approval.
 */
export function AlertQueuePanel({ onClose }: { onClose: () => void }) {
  const { riskData, alertsPreview, setSimulation } = useFloodStore();
  const [animate, setAnimate] = useState(true);
  const [pending, setPending] = useState<BroadcastAlert[]>([]);
  const [sent, setSent] = useState<BroadcastAlert[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [busyId, setBusyId] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [operatorKey, setKey] = useState(getOperatorKey);

  const saveOperatorKey = (value: string) => {
    setKey(value);
    setOperatorKey(value);
  };

  const refresh = useCallback(() => {
    api
      .getPendingAlerts()
      .then((list) => {
        setPending(list);
        setStatus('ready');
      })
      .catch(() => setStatus('error'));
  }, []);

  useEffect(refresh, [refresh]);

  const check = async () => {
    if (!riskData) return;
    setChecking(true);
    setNote(null);
    try {
      const created = await api.runAlertCheck({
        rainfall_mm: riskData.scenario.rainfall_mm,
        duration_hours: riskData.scenario.duration_hours,
      });
      setNote(
        created === null
          ? 'This server proposes alerts automatically every 15 minutes from the live forecast. Showing its current queue.'
          : created.length
            ? `${created.length} new alert(s) proposed.`
            : 'No new alerts: no ward newly reached the alert threshold.'
      );
      refresh();
    } catch {
      setNote('Could not run the alert check.');
    } finally {
      setChecking(false);
    }
  };

  const simulate = (alerts: BroadcastAlert[]) => {
    if (!alerts.length) return;
    const warning = alerts.some((a) => a.level === 'warning');
    setSimulation({
      wardIds: alerts.map((a) => a.ward_id),
      level: warning ? 'warning' : 'watch',
      title: alerts.length === 1
        ? `${alerts[0].level.toUpperCase()} · ${alerts[0].ward_name}${alerts[0].exercise ? ' (exercise)' : ''}`
        : `${alerts.length} wards · ${warning ? 'WARNING' : 'WATCH'} (exercise)`,
    });
  };

  const decide = async (alert: BroadcastAlert, action: 'approve' | 'cancel') => {
    setBusyId(alert.id);
    try {
      const updated = action === 'approve' ? await api.approveAlert(alert.id) : await api.cancelAlert(alert.id);
      setPending((list) => list.filter((a) => a.id !== alert.id));
      if (updated.status === 'approved') {
        setSent((list) => [updated, ...list]);
        if (animate) simulate([updated]);
      }
    } catch (e) {
      setNote(
        isAuthError(e)
          ? `${action === 'approve' ? 'Approving' : 'Cancelling'} needs a valid operator key. Enter it above, then try again.`
          : `Could not ${action} the alert for ${alert.ward_name}. It may already have been handled.`
      );
      refresh();
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Modal title="Approve alerts" onClose={onClose}>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div className="text-sm text-gray-800 bg-amber-50 border border-amber-200 rounded-lg p-3 space-y-1">
          <p><strong>Exercise mode.</strong> Alerts are labelled as drills. Uncalibrated index: review each ward before approving.</p>
          {alertsPreview && <p>Preview: delivery is simulated in this browser until the backend alert endpoints are live.</p>}
        </div>

        <label className="block text-sm">
          <span className="font-medium text-gray-900">Operator key</span>
          <input
            type="password"
            value={operatorKey}
            onChange={(e) => saveOperatorKey(e.target.value)}
            autoComplete="off"
            placeholder="Required to approve or cancel"
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-flood-600 focus:outline-none focus:ring-1 focus:ring-flood-600"
          />
          <span className="text-xs text-gray-600">Kept on this device only and sent with approvals. Ask the server admin for the key (ADMIN_API_TOKEN).</span>
        </label>

        <div className="flex flex-wrap items-center gap-2">
          <button onClick={check} disabled={!riskData || checking} className="btn-primary">
            {checking ? 'Checking…' : 'Check wards for alerts'}
          </button>
          <span className="text-sm text-gray-700">
            {riskData
              ? `Uses ${riskData.scenario.rainfall_mm} mm over ${riskData.scenario.duration_hours} h at today's land use.`
              : 'Run an analysis first.'}
          </span>
        </div>
        {note && <p role="status" className="text-sm text-gray-800">{note}</p>}
        <label className="flex items-center gap-2 text-sm text-gray-800">
          <input type="checkbox" className="w-4 h-4 accent-flood-600" checked={animate} onChange={(e) => setAnimate(e.target.checked)} />
          Show the delivery simulation after approving
        </label>

        <section aria-labelledby="pending-title">
          <h3 id="pending-title" className="font-semibold text-gray-900 mb-2">Waiting for approval ({pending.length})</h3>
          {status === 'loading' && <p className="text-sm text-gray-700" role="status">Loading…</p>}
          {status === 'error' && <p className="text-sm text-red-800" role="alert">Could not load pending alerts.</p>}
          {status === 'ready' && pending.length === 0 && <p className="text-sm text-gray-700">No alerts waiting.</p>}
          <ul className="space-y-3">
            {pending.map((a) => (
              <li key={a.id} className="border border-gray-200 rounded-lg p-3 bg-white">
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <span className={cn('px-2 py-0.5 rounded text-xs font-bold uppercase', a.level === 'warning' ? 'bg-red-700 text-white' : 'bg-amber-400 text-gray-950')}>
                    {a.level}
                  </span>
                  <span className="font-semibold text-gray-900">{a.ward_name}</span>
                  <span className="text-xs text-gray-700">
                    {getRiskLabel(a.risk_level)} · index {Math.round(a.risk_score * 100)}/100 · {a.rainfall_mm} mm / {a.duration_hours} h
                  </span>
                  {a.exercise && <span className="text-xs font-semibold text-gray-700 border border-gray-300 rounded px-1.5">EXERCISE</span>}
                </div>
                <p className="text-sm text-gray-900 break-words">{a.messages.en}</p>
                <p className="text-sm text-gray-900 break-words mt-1" lang="ta">{a.messages.ta}</p>
                <div className="flex gap-2 mt-3">
                  <button onClick={() => decide(a, 'approve')} disabled={busyId === a.id} className="btn-primary">
                    Approve &amp; send
                  </button>
                  <button onClick={() => decide(a, 'cancel')} disabled={busyId === a.id} className="btn-secondary">
                    Cancel
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>

        {sent.length > 0 && (
          <section aria-labelledby="sent-title" className="border-t border-gray-200 pt-4">
            <div className="flex items-center justify-between gap-2 mb-2">
              <h3 id="sent-title" className="font-semibold text-gray-900">Sent this session</h3>
              {sent.length > 1 && (
                <button onClick={() => simulate(sent)} className="btn-secondary text-xs">▶ Simulate all {sent.length}</button>
              )}
            </div>
            <ul className="space-y-1 text-sm text-gray-800">
              {sent.map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-2">
                  <span>
                    ✓ {a.ward_name} ({a.level}): {a.delivery?.push_sent ?? 0} phone notification(s),{' '}
                    {a.delivery?.whatsapp_queued ?? 0} WhatsApp message(s) queued
                  </span>
                  <button onClick={() => simulate([a])} className="text-xs font-medium text-flood-700 underline flex-shrink-0">▶ Simulate</button>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </Modal>
  );
}
