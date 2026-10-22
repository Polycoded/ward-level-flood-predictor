import { useEffect, useState } from 'react';
import { useFloodStore } from '../lib/store';
import { api } from '../api/client';
import { cn, formatDistance, formatTime } from '../lib/utils';
import { geometryCenter, isStraightLine, osmWalkingDirectionsUrl } from '../lib/geo';
import { CHENNAI } from '../lib/rainfall';
import type { Shelter } from '../types';

const SEARCH_RADIUS_KM = 10;
const MAX_RESULTS = 8;

export function ShelterPanel() {
  const {
    wards, ui, shelters, selectedShelterId, shelterOrigin,
    setMapView, setShelters, setSelectedShelter, setShelterOrigin,
  } = useFloodStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Start from the ward the user is looking at; otherwise the city centre until they share location.
  useEffect(() => {
    if (shelterOrigin) return;
    const ward = wards.find((w) => w.ward_id === ui.detailWardId);
    const centre = geometryCenter(ward?.geometry);
    setShelterOrigin(
      ward && centre
        ? { ...centre, label: `Centre of ${ward.ward_name}` }
        : { lat: CHENNAI.latitude, lng: CHENNAI.longitude, label: 'Chennai city centre' }
    );
  }, [shelterOrigin, wards, ui.detailWardId, setShelterOrigin]);

  useEffect(() => {
    if (!shelterOrigin) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .findShelters(shelterOrigin.lat, shelterOrigin.lng, SEARCH_RADIUS_KM, MAX_RESULTS)
      .then((data) => {
        if (cancelled) return;
        setShelters(data);
        setSelectedShelter(data[0]?.shelter_id ?? null);
      })
      .catch(() => !cancelled && setError('Could not load shelters.'))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [shelterOrigin, setShelters, setSelectedShelter]);

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setError('Location is not available in this browser.');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => setShelterOrigin({ lat: pos.coords.latitude, lng: pos.coords.longitude, label: 'Your location' }),
      () => setError('Location permission denied. Showing shelters near the selected point instead.'),
      { enableHighAccuracy: false, timeout: 10_000 }
    );
  };

  const close = () => {
    setMapView('risk');
    setSelectedShelter(null);
    setShelterOrigin(null);
  };

  return (
    <aside
      aria-label="Nearby shelters"
      className="fixed bottom-0 left-0 right-0 z-[45] bg-white border-t border-gray-200 rounded-t-2xl shadow-xl max-h-[60vh] flex flex-col lg:bottom-4 lg:left-auto lg:right-4 lg:top-20 lg:w-96 lg:rounded-xl lg:max-h-none"
    >
      <div className="p-4 border-b border-gray-200 flex items-start justify-between gap-2">
        <div>
          <h2 className="font-semibold text-gray-900">Nearest shelters</h2>
          {shelterOrigin && <p className="text-xs text-gray-600 mt-0.5">From: {shelterOrigin.label}</p>}
        </div>
        <button onClick={close} className="p-2 rounded-lg hover:bg-gray-100 text-gray-600" aria-label="Close shelters">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="px-4 pt-3">
        <button onClick={useMyLocation} className="btn-secondary w-full text-sm">Use my location</button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
        {error && <p role="alert" className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg p-2">{error}</p>}
        {loading ? (
          [1, 2, 3].map((i) => <div key={i} className="h-20 bg-gray-100 rounded-lg animate-pulse" />)
        ) : shelters.length === 0 ? (
          <p className="text-center py-8 text-sm text-gray-600">No shelters within {SEARCH_RADIUS_KM} km.</p>
        ) : (
          <ul className="space-y-2.5">
            {shelters.map((shelter) => (
              <li key={shelter.shelter_id}>
                <ShelterCard
                  shelter={shelter}
                  selected={selectedShelterId === shelter.shelter_id}
                  origin={shelterOrigin}
                  onSelect={() => setSelectedShelter(shelter.shelter_id)}
                />
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}

function ShelterCard({
  shelter,
  selected,
  origin,
  onSelect,
}: {
  shelter: Shelter;
  selected: boolean;
  origin: { lat: number; lng: number } | null;
  onSelect: () => void;
}) {
  const approx = isStraightLine(shelter.route_geometry);
  return (
    <div className={cn('rounded-lg border p-3', selected ? 'border-flood-400 bg-flood-50' : 'border-gray-200 bg-white')}>
      <button onClick={onSelect} className="w-full text-left" aria-pressed={selected}>
        <span className="block font-medium text-gray-900">{shelter.name}</span>
        <span className="block text-xs text-gray-600">Capacity ~{shelter.capacity} people</span>
        <span className="flex items-center gap-3 mt-1.5 text-sm text-gray-800">
          <span>{formatDistance(shelter.distance_km * 1000)}</span>
          <span>~{formatTime(shelter.walking_time_min)} walk</span>
          {approx && <span className="text-xs text-gray-600">(straight-line estimate)</span>}
        </span>
      </button>
      {origin && (
        <a
          href={osmWalkingDirectionsUrl(origin, { lat: shelter.latitude, lng: shelter.longitude })}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-block mt-2 text-xs font-medium text-flood-700 hover:text-flood-800"
        >
          Walking directions (OpenStreetMap) ↗
        </a>
      )}
    </div>
  );
}
