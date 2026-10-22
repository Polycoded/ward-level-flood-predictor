import { useEffect, useRef, useState } from 'react';
import { cn } from '../lib/utils';
import {
  MAX_CSV_BYTES,
  MAX_RAINFALL_MM,
  RainfallInputError,
  clampDuration,
  clampRainfall,
  fetchOpenMeteoForecast,
  parseRainfallCsv,
  type RainfallReading,
} from '../lib/rainfall';

type Mode = 'manual' | 'csv' | 'live';

// Blob.text() is missing in older Safari; FileReader works everywhere.
function readFileText(file: File): Promise<string> {
  if (typeof file.text === 'function') return file.text();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ''));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

const PRESETS = [
  { mm: 50, label: '50' },
  { mm: 100, label: '100' },
  { mm: 200, label: '200' },
  { mm: 300, label: '300 · Dec 2023' },
];
const DURATIONS = [1, 3, 6, 12, 24];

interface RainfallControlProps {
  onAnalyze: (reading: RainfallReading) => void;
  busy: boolean;
}

/** Rainfall input in the three forms the problem statement asks for: manual, CSV, live forecast. */
export function RainfallControl({ onAnalyze, busy }: RainfallControlProps) {
  const [mode, setMode] = useState<Mode>('manual');
  // kept as text so the box can be emptied and retyped; clamped as you type and on blur
  const [mmText, setMmText] = useState('100');
  const [hours, setHours] = useState(3);
  const [csvReading, setCsvReading] = useState<RainfallReading | null>(null);
  const [liveHours, setLiveHours] = useState(24);
  const [liveReading, setLiveReading] = useState<RainfallReading | null>(null);
  const [liveLoading, setLiveLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const fetchingRef = useRef(false);

  useEffect(() => () => abortRef.current?.abort(), []);

  const mm = clampRainfall(Number(mmText));
  const manualReading: RainfallReading | null =
    mmText.trim() === ''
      ? null
      : {
          rainfall_mm: mm,
          duration_hours: clampDuration(hours),
          source: 'manual',
          label: `${mm} mm in ${clampDuration(hours)} h (manual)`,
        };

  const handleAmount = (raw: string) => {
    if (raw.trim() === '') return setMmText('');
    const n = Number(raw);
    if (!Number.isFinite(n)) return;
    if (n > MAX_RAINFALL_MM) return setMmText(String(MAX_RAINFALL_MM));
    if (n < 0) return setMmText('0');
    setMmText(raw);
  };
  const setMm = (n: number) => setMmText(String(n));

  const current = mode === 'manual' ? manualReading : mode === 'csv' ? csvReading : liveReading;

  const switchMode = (next: Mode) => {
    setMode(next);
    setError(null);
  };

  const handleFile = async (file: File | undefined) => {
    setError(null);
    setCsvReading(null);
    if (!file) return;
    if (file.size > MAX_CSV_BYTES) {
      setError('CSV is too large (max 64 KB).');
      return;
    }
    try {
      setCsvReading(parseRainfallCsv(await readFileText(file), file.name));
    } catch (e) {
      setError(e instanceof RainfallInputError ? e.message : 'Could not read that file.');
    }
  };

  const loadForecast = async () => {
    // ignore repeat clicks (auto-clickers) instead of firing one request each
    if (fetchingRef.current) return;
    fetchingRef.current = true;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLiveLoading(true);
    setError(null);
    try {
      setLiveReading(await fetchOpenMeteoForecast(liveHours, controller.signal));
    } catch (e) {
      if (controller.signal.aborted) return;
      setError(e instanceof RainfallInputError ? e.message : 'Weather service unreachable. Use manual input instead.');
    } finally {
      if (abortRef.current === controller) setLiveLoading(false);
      fetchingRef.current = false;
    }
  };

  return (
    <section className="p-4 border-b border-gray-200 space-y-3" aria-labelledby="rainfall-heading">
      <div className="flex items-center justify-between">
        <h2 id="rainfall-heading" className="text-sm font-semibold text-gray-900 uppercase tracking-wide">
          Rainfall
        </h2>
        <div className="flex rounded-lg border border-gray-300 overflow-hidden text-xs" role="tablist" aria-label="Rainfall source">
          {(['manual', 'csv', 'live'] as Mode[]).map((m) => (
            <button
              key={m}
              role="tab"
              aria-selected={mode === m}
              onClick={() => switchMode(m)}
              className={cn(
                'px-2.5 py-1 font-medium',
                mode === m ? 'bg-flood-700 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'
              )}
            >
              {m === 'manual' ? 'Manual' : m === 'csv' ? 'CSV' : 'Forecast'}
            </button>
          ))}
        </div>
      </div>

      {mode === 'manual' && (
        <div className="space-y-2.5">
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <label htmlFor="rain-mm" className="label">Amount (mm)</label>
              <input
                id="rain-mm"
                type="number"
                inputMode="decimal"
                min={0}
                max={MAX_RAINFALL_MM}
                step={5}
                value={mmText}
                onChange={(e) => handleAmount(e.target.value)}
                onBlur={() => mmText.trim() !== '' && setMmText(String(mm))}
                aria-invalid={mmText.trim() === ''}
                className="input"
              />
            </div>
            <div className="w-28">
              <label htmlFor="rain-hours" className="label">Over</label>
              <select id="rain-hours" value={hours} onChange={(e) => setHours(Number(e.target.value))} className="input">
                {DURATIONS.map((h) => (
                  <option key={h} value={h}>{h} hour{h > 1 ? 's' : ''}</option>
                ))}
              </select>
            </div>
          </div>
          <input
            type="range"
            min={0}
            max={300}
            step={5}
            value={Math.min(mm, 300)}
            onChange={(e) => setMm(Number(e.target.value))}
            className="w-full accent-flood-600"
            aria-label="Rainfall amount slider"
          />
          <div className="flex flex-wrap gap-1.5" aria-label="Rainfall presets">
            {PRESETS.map((p) => (
              <button
                key={p.mm}
                onClick={() => {
                  setMm(p.mm);
                  setHours(3);
                }}
                aria-pressed={mm === p.mm && hours === 3}
                className={cn(
                  'px-2 py-0.5 rounded-full text-xs border',
                  mm === p.mm && hours === 3 ? 'bg-flood-50 border-flood-300 text-flood-800' : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                )}
              >
                {p.label} mm
              </button>
            ))}
          </div>
        </div>
      )}

      {mode === 'csv' && (
        <div className="space-y-2">
          <label htmlFor="rain-csv" className="label">Hourly rainfall CSV</label>
          <input
            id="rain-csv"
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => handleFile(e.target.files?.[0])}
            className="block w-full text-sm text-gray-700 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-gray-100 file:text-gray-900 hover:file:bg-gray-200"
          />
          <p className="text-xs text-gray-600">
            One value in mm per row (optionally <code>time,rainfall_mm</code>), up to 24 rows.
          </p>
        </div>
      )}

      {mode === 'live' && (
        <div className="flex items-end gap-2">
          <div className="flex-1">
            <label htmlFor="live-hours" className="label">Open-Meteo forecast, Chennai</label>
            <select id="live-hours" value={liveHours} onChange={(e) => setLiveHours(Number(e.target.value))} className="input">
              {[6, 12, 24].map((h) => (
                <option key={h} value={h}>Next {h} hours</option>
              ))}
            </select>
          </div>
          <button onClick={loadForecast} disabled={liveLoading} className="btn-secondary">
            {liveLoading ? 'Loading…' : 'Fetch'}
          </button>
        </div>
      )}

      {mode === 'manual' && !manualReading && (
        <p className="text-xs text-gray-700">Enter a rainfall amount between 0 and {MAX_RAINFALL_MM} mm.</p>
      )}

      {error && (
        <p role="alert" className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg p-2">
          {error}
        </p>
      )}

      {current && mode !== 'manual' && (
        <p className="text-sm text-gray-800" aria-live="polite">
          <strong>{current.rainfall_mm} mm</strong> over {current.duration_hours} h
          <span className="text-gray-600"> · {current.label}</span>
        </p>
      )}

      <button
        onClick={() => current && onAnalyze(current)}
        disabled={!current || busy}
        className="btn-primary w-full"
      >
        {busy ? 'Scoring wards…' : 'Analyze'}
      </button>
    </section>
  );
}
