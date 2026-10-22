import { useState, type FormEvent } from 'react';
import { useFloodStore } from '../lib/store';
import { sanitizeText } from '../lib/safe';
import { getDepthLabel } from '../lib/utils';
import type { DepthBand } from '../types';
import { Modal } from './Modal';


const NOTE_LIMIT = 280;
const MAX_REPORTS = 20;
const DEPTHS: DepthBand[] = ['0-0.15m', '0.15-0.5m', '0.5-1.0m', '1.0m+'];

interface CrowdReport {
  wardId: number;
  wardName: string;
  depth: DepthBand;
  note: string;
  at: string;
}

/**
 * Tier 3 shell (off by default, VITE_ENABLE_CROWD_REPORTS=true to show).
 * Reports stay in this browser tab: nothing is sent until the moderated
 * /reports backend exists, and they never change the model's scores.
 */
export function CrowdReportPanel({ onClose }: { onClose: () => void }) {
  const { wards } = useFloodStore();
  const [wardId, setWardId] = useState('');
  const [depth, setDepth] = useState<DepthBand>('0.15-0.5m');
  const [note, setNote] = useState('');
  const [reports, setReports] = useState<CrowdReport[]>([]);
  const [error, setError] = useState<string | null>(null);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const ward = wards.find((w) => String(w.ward_id) === wardId);
    if (!ward) {
      setError('Choose the ward where you saw flooding.');
      return;
    }
    if (!DEPTHS.includes(depth)) {
      setError('Choose a water depth.');
      return;
    }
    if (reports.length >= MAX_REPORTS) {
      setError(`At most ${MAX_REPORTS} reports per session.`);
      return;
    }
    setReports((r) => [
      { wardId: ward.ward_id, wardName: ward.ward_name, depth, note: sanitizeText(note, NOTE_LIMIT), at: new Date().toLocaleTimeString() },
      ...r,
    ]);
    setNote('');
    setError(null);
  };

  return (
    <Modal title="Report flooding (preview)" onClose={onClose}>
      <form onSubmit={submit} className="p-4 space-y-3 overflow-y-auto" noValidate>
        <p className="text-xs text-amber-900 bg-amber-50 border border-amber-200 rounded-lg p-2">
          Preview only: reports are kept in this tab and not sent anywhere. Once connected they will be moderated and
          shown as advisory, never changing a ward's risk score.
        </p>
        <div>
          <label htmlFor="report-ward" className="label">Ward</label>
          <select id="report-ward" value={wardId} onChange={(e) => setWardId(e.target.value)} className="input" required>
            <option value="">Select a ward…</option>
            {wards.map((w) => (
              <option key={w.ward_id} value={w.ward_id}>{w.ward_name} (Ward {w.ward_number})</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="report-depth" className="label">Water depth</label>
          <select id="report-depth" value={depth} onChange={(e) => setDepth(e.target.value as DepthBand)} className="input">
            {DEPTHS.map((d) => (
              <option key={d} value={d}>{getDepthLabel(d)}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="report-note" className="label">What did you see? (optional)</label>
          <textarea
            id="report-note"
            value={note}
            maxLength={NOTE_LIMIT}
            onChange={(e) => setNote(e.target.value.slice(0, NOTE_LIMIT))}
            rows={2}
            className="input"
          />
          <p className="text-xs text-gray-600 text-right">{note.length}/{NOTE_LIMIT}</p>
        </div>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <button type="submit" className="btn-primary w-full">Save report</button>

        {reports.length > 0 && (
          <ul className="border-t border-gray-200 pt-3 space-y-2" aria-label="Reports this session">
            {reports.map((r, i) => (
              <li key={i} className="text-sm text-gray-800">
                <strong>{r.wardName}</strong> · {getDepthLabel(r.depth)} · {r.at}
                {r.note && <span className="block text-gray-700 break-words">{r.note}</span>}
              </li>
            ))}
          </ul>
        )}
      </form>
    </Modal>
  );
}
