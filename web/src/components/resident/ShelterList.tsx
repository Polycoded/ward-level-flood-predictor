import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { useT } from '../../lib/i18n';
import { geometryCenter, osmWalkingDirectionsUrl } from '../../lib/geo';
import type { Shelter, WardLite } from '../../types';

/** Nearest shelters from the ward centre, with a walking-directions link for the phone's maps app. */
export function ShelterList({ ward }: { ward: WardLite }) {
  const t = useT();
  const [state, setState] = useState<{ status: 'loading' } | { status: 'error' } | { status: 'ready'; shelters: Shelter[] }>({ status: 'loading' });
  const centre = geometryCenter(ward.geometry);

  useEffect(() => {
    if (!centre) return;
    let cancelled = false;
    setState({ status: 'loading' });
    api
      .findShelters(centre.lat, centre.lng, 10, 5)
      .then((shelters) => !cancelled && setState({ status: 'ready', shelters }))
      .catch(() => !cancelled && setState({ status: 'error' }));
    return () => {
      cancelled = true;
    };
  }, [ward.ward_id]); // eslint-disable-line react-hooks/exhaustive-deps -- centre derives from the ward

  return (
    <section className="card p-4" aria-labelledby="shelter-list-title">
      <h2 id="shelter-list-title" className="text-lg font-semibold text-gray-900 mb-2">{t('shelter.title')}</h2>
      {state.status === 'loading' && <p className="text-gray-700" role="status">…</p>}
      {state.status === 'error' && <p className="text-gray-800" role="alert">{t('shelter.error')}</p>}
      {state.status === 'ready' && state.shelters.length === 0 && <p className="text-gray-800">{t('shelter.none')}</p>}
      {state.status === 'ready' && state.shelters.length > 0 && (
        <ul className="divide-y divide-gray-100">
          {state.shelters.map((s) => (
            <li key={s.shelter_id} className="py-3 flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <p className="font-medium text-gray-900">{s.name}</p>
                <p className="text-sm text-gray-700">
                  {t('shelter.walk', { min: s.walking_time_min })} · {s.distance_km.toFixed(1)} km
                  <span className="text-gray-600"> ({t('shelter.straight')})</span>
                </p>
              </div>
              {centre && (
                <a
                  href={osmWalkingDirectionsUrl(centre, { lat: s.latitude, lng: s.longitude })}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-secondary min-h-11 flex-shrink-0"
                >
                  {t('shelter.directions')}
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
