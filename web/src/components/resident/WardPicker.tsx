import { useMemo, useState } from 'react';
import { useT } from '../../lib/i18n';
import type { WardIndex } from '../../lib/wardLookup';
import { locate, type LocateError } from './hooks';

const MAX_SHOWN = 40;

interface WardPickerProps {
  index: WardIndex | null;
  wards: { ward_id: number; ward_number: string; ward_name: string }[];
  onPick: (wardId: number) => void;
}

/** "Use my location" (matched on the phone) or pick from the list. */
export function WardPicker({ index, wards, onPick }: WardPickerProps) {
  const t = useT();
  const [mode, setMode] = useState<'buttons' | 'list'>('buttons');
  const [query, setQuery] = useState('');
  const [locating, setLocating] = useState(false);
  const [problem, setProblem] = useState<LocateError | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = q ? wards.filter((w) => w.ward_name.toLowerCase().includes(q) || w.ward_number === q) : wards;
    return list.slice(0, MAX_SHOWN);
  }, [wards, query]);

  const useLocation = async () => {
    if (!index) return;
    setLocating(true);
    setProblem(null);
    try {
      const match = await locate(index);
      onPick(match.ward.ward_id);
    } catch (e) {
      setProblem(e as LocateError);
      setMode('list');
    } finally {
      setLocating(false);
    }
  };

  const problemText =
    problem === 'denied' ? t('ward.denied') : problem === 'outside' ? t('ward.outside') : problem ? t('ward.unavailable') : null;

  return (
    <div className="space-y-3">
      <p className="text-lg font-semibold text-gray-900">{t('ward.question')}</p>
      {!index && <p className="text-sm text-gray-700" role="status">{t('ward.loading')}</p>}
      {problemText && <p role="alert" className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded-lg p-2.5">{problemText}</p>}

      {mode === 'buttons' && (
        <div className="grid gap-2">
          <button onClick={useLocation} disabled={!index || locating} className="btn-primary min-h-12 text-base">
            {locating ? t('ward.locating') : `📍 ${t('ward.useLocation')}`}
          </button>
          <button onClick={() => setMode('list')} disabled={!index} className="btn-secondary min-h-12 text-base">
            {t('ward.choose')}
          </button>
        </div>
      )}

      {mode === 'list' && (
        <div className="space-y-2">
          <label htmlFor="ward-picker-search" className="sr-only">{t('ward.search')}</label>
          <input
            id="ward-picker-search"
            type="search"
            inputMode="search"
            className="input min-h-12 text-base"
            placeholder={t('ward.search')}
            value={query}
            maxLength={40}
            autoFocus
            onChange={(e) => setQuery(e.target.value)}
          />
          <ul className="max-h-72 overflow-y-auto divide-y divide-gray-100 border border-gray-200 rounded-lg bg-white" aria-label={t('ward.choose')}>
            {filtered.map((w) => (
              <li key={w.ward_id}>
                <button onClick={() => onPick(w.ward_id)} className="w-full text-left px-3 py-3 text-base hover:bg-gray-50 focus-visible:bg-gray-100">
                  {w.ward_name}
                </button>
              </li>
            ))}
            {filtered.length === 0 && <li className="px-3 py-3 text-sm text-gray-700">{t('ward.noMatch')}</li>}
          </ul>
          {index && mode === 'list' && (
            <button onClick={useLocation} disabled={locating} className="text-sm font-medium text-flood-700 underline underline-offset-2">
              {locating ? t('ward.locating') : t('ward.useLocation')}
            </button>
          )}
        </div>
      )}
      <p className="text-xs text-gray-600">{t('ward.privacy')}</p>
    </div>
  );
}
